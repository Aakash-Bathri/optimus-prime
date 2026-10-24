"""Typed LocalStack operations over the official server's LangChain MCP tool."""

import asyncio
from contextlib import asynccontextmanager
import json
import os
import re
import shutil

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import ROOT
from app.execution.contracts import INSTANCE_TYPES, WorkflowError


def extract_json(content):
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = block["text"]
        for index, character in enumerate(text):
            if character == "{":
                try:
                    value, _ = json.JSONDecoder().raw_decode(text[index:])
                except ValueError:
                    continue
                if isinstance(value, dict):
                    return value
    raise WorkflowError("LocalStack MCP returned no AWS JSON response", 502)


class Cloud:
    def __init__(self, aws_tool):
        self.tool = aws_tool

    async def _call(self, command, expected):
        result = await asyncio.wait_for(self.tool.ainvoke({
            "command": f"ec2 {command} --region us-east-1 --output json",
        }), timeout=45)
        value = extract_json(result)
        if expected not in value:
            raise WorkflowError("LocalStack did not confirm the requested AWS operation", 502)
        return value

    @staticmethod
    def _id(identifier):
        if not re.fullmatch(r"i-[a-f0-9]{8,32}", identifier):
            raise WorkflowError("Invalid EC2 instance ID", 422)
        return identifier

    async def inventory(self):
        value = await self._call("describe-instances", "Reservations")
        return [self.snapshot(instance) for reservation in value["Reservations"]
                for instance in reservation["Instances"]
                if instance["State"]["Name"] != "terminated"]

    async def inspect(self, identifier):
        identifier = self._id(identifier)
        value = await self._call(f"describe-instances --instance-ids {identifier}", "Reservations")
        instances = [instance for reservation in value["Reservations"] for instance in reservation["Instances"]]
        if len(instances) != 1:
            raise WorkflowError("Mapped instance was not found", 404)
        return self.snapshot(instances[0])

    @staticmethod
    def snapshot(instance):
        return {"provider_id": instance["InstanceId"], "instance_type": instance["InstanceType"],
                "state": instance["State"]["Name"],
                "tags": {item["Key"]: item["Value"] for item in instance.get("Tags", [])}}

    async def state(self, identifier, action):
        if action not in ("start", "stop"):
            raise WorkflowError("Unsupported state action", 422)
        await self._call(f"{action}-instances --instance-ids {self._id(identifier)}",
                         "StartingInstances" if action == "start" else "StoppingInstances")

    async def resize(self, identifier, target):
        if target not in INSTANCE_TYPES:
            raise WorkflowError("Unsupported demo instance type", 422)
        # AWS modify-instance-attribute returns an empty JSON object on success.
        result = await asyncio.wait_for(self.tool.ainvoke({"command":
            f"ec2 modify-instance-attribute --instance-id {self._id(identifier)} "
            f"--instance-type Value={target} --region us-east-1 --output json"}), timeout=45)
        # Some awslocal versions return no body. Verification below is authoritative.
        text = json.dumps(result)
        if any(marker in text.lower() for marker in ("error", "not running", "exception", "denied")):
            raise WorkflowError("LocalStack refused the instance type change", 502)

    async def wait(self, identifier, state):
        for _ in range(30):
            current = await self.inspect(identifier)
            if current["state"] == state:
                return current
            await asyncio.sleep(1)
        raise WorkflowError("LocalStack state transition timed out; inspect the execution audit", 502)


@asynccontextmanager
async def localstack(config):
    package = ROOT / "infra/localstack-mcp/node_modules/@localstack/localstack-mcp-server"
    if not package.exists() or not shutil.which("node"):
        raise WorkflowError("Install the LocalStack MCP npm dependencies and Node.js", 503)
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    token = config.get("LOCALSTACK_AUTH_TOKEN") or config.get("LOCALSTACK_TOKEN")
    if not token:
        raise WorkflowError("LocalStack token is not configured", 503)
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        "PATH", "SYSTEMROOT", "COMSPEC", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "TEMP", "TMP",
    }}
    env.update({"LOCALSTACK_AUTH_TOKEN": token, "MAIN_CONTAINER_NAME": "cloudpilot-localstack",
                "LOCALSTACK_HOSTNAME": config.get("CLOUDPILOT_LOCALSTACK_HOSTNAME", "localhost"), "LOCALSTACK_PORT": "4566", "MCP_ANALYTICS_DISABLED": "1"})
    parameters = StdioServerParameters(command=shutil.which("node"),
        args=[str(package / metadata["bin"]["localstack-mcp-server"])], env=env)
    try:
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=30)
                tools = await load_mcp_tools(session)
                yield Cloud(next(tool for tool in tools if tool.name == "localstack-aws-client"))
    except BaseExceptionGroup as error:
        def leaves(group):
            for item in group.exceptions:
                if isinstance(item, BaseExceptionGroup):
                    yield from leaves(item)
                else:
                    yield item
        errors = list(leaves(error))
        for item in errors:
            if isinstance(item, WorkflowError):
                raise item from None
        if any(isinstance(item, asyncio.CancelledError) for item in errors):
            raise
        raise WorkflowError("LocalStack MCP session failed; check the container and MCP installation", 502) from None
