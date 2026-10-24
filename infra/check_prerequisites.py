"""Read-only checks for Person 5's configured integrations; never prints secrets."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import time

from dotenv import dotenv_values
import httpx

ROOT = Path(__file__).resolve().parents[1]


def check_llm(config):
    from langchain.agents import create_agent
    from langchain_core.messages import ToolMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    @tool
    def check_connection(status: str) -> str:
        """Verify the connection with status OK."""
        if status != "OK":
            raise ValueError("Expected OK")
        return "Connection verified. Reply OK and stop calling tools."

    model = ChatOpenAI(
        model=config["CLOUDPILOT_LLM_MODEL"],
        base_url=config["OPENAI_BASE_URL"],
        api_key=config["OPENAI_API_KEY"],
        max_tokens=256,
        temperature=0,
        streaming=False,
        use_responses_api=False,
        timeout=45,
        max_retries=0,
    )
    agent = create_agent(
        model=model,
        tools=[check_connection],
        system_prompt="Call check_connection exactly once with status OK. Then reply OK and stop.",
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Verify the connection."}]},
        {"recursion_limit": 6},
    )
    if not any(isinstance(message, ToolMessage) for message in result["messages"]):
        raise RuntimeError("No tool result returned")
    final = result["messages"][-1]
    if not final.content or getattr(final, "tool_calls", []):
        raise RuntimeError("Tool round trip did not complete")
    return {"passed": True, "model": config["CLOUDPILOT_LLM_MODEL"], "tool_roundtrip": True}


def check_localstack(config):
    response = httpx.get("http://127.0.0.1:4566/_localstack/health", timeout=10)
    response.raise_for_status()
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "ec2",
        endpoint_url="http://127.0.0.1:4566",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 2}),
    )
    resources = []
    for page in client.get_paginator("describe_instances").paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                if tags.get("CloudPilotDemo") == "true":
                    resources.append({"id": instance["InstanceId"], "name": tags.get("Name"),
                                      "management": tags.get("Management"), "type": instance["InstanceType"]})
    fixtures_ready = {"terraform", "manual"}.issubset(
        {resource["management"] for resource in resources}
    )
    return {"passed": fixtures_ready, "endpoint": "http://127.0.0.1:4566",
            "fixtures_ready": fixtures_ready, "resources": resources}


async def check_mcp(config):
    from langchain_mcp_adapters.tools import load_mcp_tools
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    package = ROOT / "infra/localstack-mcp/node_modules/@localstack/localstack-mcp-server"
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    executable = package / metadata["bin"]["localstack-mcp-server"]
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        "PATH", "SYSTEMROOT", "COMSPEC", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "TEMP", "TMP",
    }}
    env.update({"LOCALSTACK_AUTH_TOKEN": config["LOCALSTACK_AUTH_TOKEN"],
                "MAIN_CONTAINER_NAME": "cloudpilot-localstack", "LOCALSTACK_HOSTNAME": "localhost",
                "LOCALSTACK_PORT": "4566", "MCP_ANALYTICS_DISABLED": "1"})
    parameters = StdioServerParameters(command=shutil.which("node"), args=[str(executable)], env=env)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            if "localstack-aws-client" not in names:
                raise RuntimeError("LocalStack AWS tool missing")
            adapted_tools = await load_mcp_tools(session)
            aws_tool = next(tool for tool in adapted_tools if tool.name == "localstack-aws-client")
            result = await aws_tool.ainvoke({
                "command": "ec2 describe-instances --region us-east-1 --output json",
            })
            inventory = None
            for block in result:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                for index, character in enumerate(block["text"]):
                    if character != "{":
                        continue
                    try:
                        value, _ = json.JSONDecoder().raw_decode(block["text"][index:])
                    except ValueError:
                        continue
                    if isinstance(value, dict) and isinstance(value.get("Reservations"), list):
                        inventory = value
                        break
            if inventory is None:
                raise RuntimeError("MCP response did not contain EC2 inventory")
    return {"passed": True, "package_version": metadata["version"], "tools": names,
            "resource_lookup_verified": True, "langchain_adapter_verified": True,
            "reservation_count": len(inventory["Reservations"])}


def check_github(config):
    import jwt

    key = ROOT / config["GITHUB_APP_PRIVATE_KEY_PATH"]
    now = int(time.time())
    signed = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": config["GITHUB_APP_ID"]},
                        key.read_bytes(), algorithm="RS256")
    repository = config["CLOUDPILOT_GITHUB_TEST_REPO"]
    with httpx.Client(base_url="https://api.github.com", timeout=20,
                      headers={"Authorization": "Bearer " + signed,
                               "Accept": "application/vnd.github+json"}) as client:
        app = client.get("/app")
        app.raise_for_status()
        installation = client.get(f"/repos/{repository}/installation")
        installation.raise_for_status()
        identifier = installation.json()["id"]
        token = client.post(f"/app/installations/{identifier}/access_tokens", json={
            "repositories": [repository.split("/")[1]],
            "permissions": {"contents": "write", "pull_requests": "write"},
        })
        token.raise_for_status()
        repo = client.get(f"/repos/{repository}",
                          headers={"Authorization": "Bearer " + token.json()["token"]})
        repo.raise_for_status()
    return {"passed": True, "app": app.json()["slug"], "installation_id": identifier,
            "repository": repository, "repository_access_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=["all", "llm", "localstack", "mcp", "github"])
    choice = parser.parse_args().check
    config = dotenv_values(ROOT / ".env")
    checks = {"llm": check_llm, "localstack": check_localstack,
              "mcp": lambda c: asyncio.run(asyncio.wait_for(check_mcp(c), timeout=90)),
              "github": check_github}
    report = {}
    for name, function in checks.items():
        if choice not in ("all", name):
            continue
        try:
            report[name] = function(config)
        except Exception as error:
            report[name] = {"passed": False, "error_type": type(error).__name__}
            if isinstance(error, httpx.HTTPStatusError):
                report[name]["http_status"] = error.response.status_code
    target = ROOT / "data/local/prerequisites.json"
    previous = json.loads(target.read_text()) if target.exists() else {}
    previous.update(report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(result["passed"] for result in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
