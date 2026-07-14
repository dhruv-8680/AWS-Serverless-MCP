"""Minimal custom MCP on AWS Lambda — a todo tracker example.

This file has two jobs:
  1) Define tools and register them on the MCP server (your business logic).
  2) Adapt AWS Lambda + API Gateway (HTTP) to the transport-agnostic server.

Run locally (no AWS needed):
    python lambda_function.py

Deploy to AWS Lambda:
    - zip mcp_core.py + lambda_function.py together
    - runtime: python3.12
    - handler: lambda_function.lambda_handler
    - put an API Gateway HTTP API in front with a `POST /mcp` route
"""

from __future__ import annotations

import base64
import json

from mcp_core import MCPServer

server = MCPServer("minimal-mcp")

# --- an in-memory "database" (swap for DynamoDB/Postgres in production) ---
_TASKS: list[dict] = []


@server.tool(
    "add_task",
    "Add a task to the list.",
    {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}},
)
def add_task(args: dict) -> str:
    task = {"id": len(_TASKS) + 1, "title": args["title"], "done": False}
    _TASKS.append(task)
    return f"Added task {task['id']}: {task['title']}"


@server.tool("list_tasks", "List all tasks.", {"type": "object", "properties": {}})
def list_tasks(args: dict) -> str:
    if not _TASKS:
        return "No tasks."
    return "\n".join(f"[{'x' if t['done'] else ' '}] {t['id']}. {t['title']}" for t in _TASKS)


@server.tool(
    "complete_task",
    "Mark a task done by id.",
    {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
)
def complete_task(args: dict) -> str:
    for task in _TASKS:
        if task["id"] == args["id"]:
            task["done"] = True
            return f"Completed task {task['id']}: {task['title']}"
    return f"No task with id {args['id']}"


# --- AWS Lambda + API Gateway adapter ------------------------------------
def lambda_handler(event, context):
    """API Gateway (HTTP API) proxy event -> MCP server -> proxy response."""
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        return _resp(200, {"jsonrpc": "2.0", "id": None,
                           "error": {"code": -32700, "message": "Parse error"}})

    result = server.handle(message)
    if result is None:          # a notification -> acknowledge with no body
        return _resp(202, None)
    return _resp(200, result)


def _resp(status: int, payload) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": "" if payload is None else json.dumps(payload),
        "isBase64Encoded": False,
    }


# --- local demo (runs the full MCP flow without AWS) ---------------------
if __name__ == "__main__":
    def call(rpc_id, method, params=None):
        msg = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
        if params is not None:
            msg["params"] = params
        print(f">>> {method} {params or ''}")
        print(json.dumps(server.handle(msg), indent=2), "\n")

    call(1, "initialize")
    call(2, "tools/list")
    call(3, "tools/call", {"name": "add_task", "arguments": {"title": "Write docs"}})
    call(4, "tools/call", {"name": "add_task", "arguments": {"title": "Ship it"}})
    call(5, "tools/call", {"name": "list_tasks", "arguments": {}})
    call(6, "tools/call", {"name": "complete_task", "arguments": {"id": 1}})
    call(7, "tools/call", {"name": "list_tasks", "arguments": {}})
