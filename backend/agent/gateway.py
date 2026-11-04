"""MCP client for the AgentCore Gateway, and a Bedrock agent that calls its tools.

The gateway uses AWS_IAM inbound auth, so each JSON-RPC request is SigV4-signed for
the `bedrock-agentcore` service with the caller's credentials. GATEWAY_URL turns it on.
"""

from __future__ import annotations

import json
import logging
import os
from itertools import count
from typing import Any, Callable

log = logging.getLogger(__name__)

GATEWAY_URL = os.environ.get("GATEWAY_URL", "").strip()

AGENT_SYSTEM = (
    "You help a parent research schools. Use the school tools for every fact; do not "
    "answer from memory. Keep the answer short, name the school, and say which tool "
    "field each fact came from. Never promise a scholarship amount."
)


class GatewayClient:
    """JSON-RPC over the gateway's streamable HTTP endpoint."""

    def __init__(self, url: str = GATEWAY_URL, region: str | None = None):
        if not url:
            raise ValueError("GATEWAY_URL is not set")
        import boto3

        self.url = url
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._credentials = boto3.Session().get_credentials()
        self._ids = count(1)
        self._session_id: str | None = None

    def _post(self, method: str, params: dict | None = None) -> dict:
        import httpx
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        body = json.dumps({"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params or {}})
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        request = AWSRequest(method="POST", url=self.url, data=body, headers=headers)
        SigV4Auth(self._credentials.get_frozen_credentials(), "bedrock-agentcore", self.region).add_auth(request)
        response = httpx.post(self.url, content=body, headers=dict(request.headers), timeout=30)
        response.raise_for_status()
        self._session_id = response.headers.get("Mcp-Session-Id", self._session_id)
        message = _parse(response.text)
        if "error" in message:
            raise RuntimeError(f"gateway {method} failed: {message['error']}")
        return message["result"]

    def initialize(self) -> dict:
        return self._post(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "gs-guided-search", "version": "1.0"},
            },
        )

    def list_tools(self) -> list[dict]:
        return self._post("tools/list")["tools"]

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._post("tools/call", {"name": name, "arguments": arguments})
        return "".join(part.get("text", "") for part in result.get("content", []))


def _parse(text: str) -> dict:
    """The gateway answers with JSON or a one-event SSE stream."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
    return json.loads(data[-1])


def ask_agent(
    question: str,
    client: GatewayClient | None = None,
    on_tool: Callable[[str, dict, str], None] | None = None,
    max_rounds: int = 5,
) -> dict[str, Any]:
    """Bedrock Converse with the gateway's MCP tools. Returns the answer and each tool call."""
    import boto3

    from catalog import models

    client = client or GatewayClient()
    client.initialize()
    tools = client.list_tools()
    tool_config = {
        "tools": [
            {"toolSpec": {"name": t["name"], "description": t.get("description", ""), "inputSchema": {"json": t["inputSchema"]}}}
            for t in tools
        ]
    }
    bedrock = boto3.client("bedrock-runtime", region_name=models().get("region", "us-east-1"))
    messages: list[dict] = [{"role": "user", "content": [{"text": question}]}]
    calls: list[dict] = []
    for _ in range(max_rounds):
        response = bedrock.converse(
            modelId=models()["fast_model"],
            system=[{"text": AGENT_SYSTEM}],
            messages=messages,
            toolConfig=tool_config,
        )
        message = response["output"]["message"]
        messages.append(message)
        uses = [block["toolUse"] for block in message["content"] if "toolUse" in block]
        if response["stopReason"] != "tool_use" or not uses:
            answer = "".join(block.get("text", "") for block in message["content"])
            return {"answer": answer, "tool_calls": calls, "tools": [t["name"] for t in tools]}
        results = []
        for use in uses:
            output = client.call_tool(use["name"], use["input"])
            calls.append({"name": use["name"], "arguments": use["input"], "result": output})
            if on_tool:
                on_tool(use["name"], use["input"], output)
            results.append({"toolResult": {"toolUseId": use["toolUseId"], "content": [{"text": output}]}})
        messages.append({"role": "user", "content": results})
    log.warning("gateway agent stopped after %d rounds", max_rounds)
    return {"answer": "", "tool_calls": calls, "tools": [t["name"] for t in tools]}
