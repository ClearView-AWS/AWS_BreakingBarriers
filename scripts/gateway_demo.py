"""List the AgentCore Gateway's MCP tools, then let the Bedrock agent call them.

Usage:
  GATEWAY_URL=https://<id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp \
    .venv/bin/python scripts/gateway_demo.py ["question"]

Without GATEWAY_URL it reads GsGatewayStack's GatewayUrl output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from agent.gateway import GatewayClient, ask_agent  # noqa: E402

QUESTION = "Find a middle school in Seattle with English learner support. Which schools fit, and what is still unknown?"


def gateway_url() -> str:
    if os.environ.get("GATEWAY_URL"):
        return os.environ["GATEWAY_URL"]
    return subprocess.check_output(
        [
            "aws", "cloudformation", "describe-stacks", "--stack-name", "GsGatewayStack",
            "--query", "Stacks[0].Outputs[?OutputKey=='GatewayUrl'].OutputValue", "--output", "text",
        ],
        text=True,
    ).strip()


def main() -> None:
    question = " ".join(sys.argv[1:]) or QUESTION
    client = GatewayClient(gateway_url())
    print(f"Gateway: {client.url}\n")

    info = client.initialize()
    print(f"initialize -> {info.get('serverInfo', {})}")
    print("tools/list ->")
    for tool in client.list_tools():
        print(f"  - {tool['name']}: {tool.get('description', '')[:80]}")

    print(f"\nParent: {question}\n")

    def show(name: str, arguments: dict, output: str) -> None:
        print(f"[agent -> tools/call] {name} {json.dumps(arguments)}")
        print(f"  <- {output[:240]}{'…' if len(output) > 240 else ''}\n")

    result = ask_agent(question, client, on_tool=show)
    print("Agent:", result["answer"])


if __name__ == "__main__":
    main()
