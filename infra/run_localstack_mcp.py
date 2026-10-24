"""Launch the pinned official MCP server with this project's local configuration."""

import json
import os
from pathlib import Path
import shutil
import subprocess

from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[1]
    config = dotenv_values(root / ".env")
    package = root / "infra/localstack-mcp/node_modules/@localstack/localstack-mcp-server"
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    token = config.get("LOCALSTACK_AUTH_TOKEN") or config.get("LOCALSTACK_TOKEN")
    if not token:
        raise RuntimeError("Set LOCALSTACK_AUTH_TOKEN in the root .env")
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        "PATH", "SYSTEMROOT", "COMSPEC", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "TEMP", "TMP",
    }}
    env.update({"LOCALSTACK_AUTH_TOKEN": token, "MAIN_CONTAINER_NAME": "cloudpilot-localstack",
                "LOCALSTACK_HOSTNAME": "localhost", "LOCALSTACK_PORT": "4566",
                "MCP_ANALYTICS_DISABLED": "1"})
    return subprocess.call([shutil.which("node"), str(package / metadata["bin"]["localstack-mcp-server"])], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
