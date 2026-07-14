"""Minimal MCP server core — JSON-RPC 2.0 + the MCP protocol. No dependencies.

An MCP server is just a JSON-RPC 2.0 endpoint that implements a few methods:
  - initialize   -> handshake: protocol version + capabilities + server info
  - tools/list   -> advertise the available tools and their JSON Schemas
  - tools/call   -> run one tool by name with arguments

You register tools with the @server.tool(...) decorator and feed the server
parsed JSON-RPC messages (dicts). It returns a response dict, or None for
notifications (messages with no "id"). That's the whole idea.
"""

from __future__ import annotations

from typing import Callable

PROTOCOL_VERSION = "2025-06-18"


class RpcError(Exception):
    """A JSON-RPC error (e.g. unknown method/tool)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MCPServer:
    def __init__(self, name: str, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self._tools: dict[str, dict] = {}  # name -> {description, schema, handler}

    # --- register a tool ---------------------------------------------------
    def tool(self, name: str, description: str, schema: dict):
        """Decorator: register a function as an MCP tool.

        The function receives the call's `arguments` dict and returns a string
        (shown to the model as the tool's text result).
        """

        def decorator(fn: Callable[[dict], str]) -> Callable[[dict], str]:
            self._tools[name] = {"description": description, "schema": schema, "handler": fn}
            return fn

        return decorator

    # --- handle one JSON-RPC message --------------------------------------
    def handle(self, message: dict) -> dict | None:
        method = message.get("method")
        params = message.get("params") or {}
        msg_id = message.get("id")
        is_notification = "id" not in message  # no id => no response

        try:
            result = self._dispatch(method, params)
        except RpcError as exc:
            return None if is_notification else _error(msg_id, exc.code, exc.message)
        except Exception as exc:  # a tool crashed -> JSON-RPC internal error
            return None if is_notification else _error(msg_id, -32603, f"Internal error: {exc}")

        return None if is_notification else {"jsonrpc": "2.0", "id": msg_id, "result": result}

    # --- route a method to its handler ------------------------------------
    def _dispatch(self, method: str, params: dict):
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            }

        if method in ("ping", "notifications/initialized"):
            return {}

        if method == "tools/list":
            return {
                "tools": [
                    {"name": name, "description": t["description"], "inputSchema": t["schema"]}
                    for name, t in self._tools.items()
                ]
            }

        if method == "tools/call":
            tool = self._tools.get(params.get("name"))
            if tool is None:
                raise RpcError(-32602, f"Unknown tool: {params.get('name')}")
            text = tool["handler"](params.get("arguments") or {})
            return {"content": [{"type": "text", "text": text}], "isError": False}

        raise RpcError(-32601, f"Method not found: {method}")


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
