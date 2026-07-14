"""Minimal assertions for the MCP server. Run: python3 test_mcp.py

Kept dependency-free (no pytest) so the whole project stays stdlib-only.
"""

from mcp_core import MCPServer


def build():
    server = MCPServer("test-mcp")

    @server.tool(
        "echo",
        "Echo a message.",
        {"type": "object", "required": ["msg"], "properties": {"msg": {"type": "string"}}},
    )
    def echo(args: dict) -> str:
        return args["msg"]

    return server


def rpc(server, method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return server.handle(msg)


def main() -> None:
    server = build()

    # initialize
    r = rpc(server, "initialize")
    assert r["result"]["protocolVersion"]
    assert r["result"]["serverInfo"]["name"] == "test-mcp"

    # tools/list reflects the registered tool
    r = rpc(server, "tools/list")
    assert [t["name"] for t in r["result"]["tools"]] == ["echo"]

    # tools/call runs the handler
    r = rpc(server, "tools/call", {"name": "echo", "arguments": {"msg": "hi"}})
    assert r["result"]["content"][0]["text"] == "hi"
    assert r["result"]["isError"] is False

    # unknown method -> -32601
    r = rpc(server, "nope")
    assert r["error"]["code"] == -32601

    # unknown tool -> -32602
    r = rpc(server, "tools/call", {"name": "ghost"})
    assert r["error"]["code"] == -32602

    # a notification (no "id") yields no response
    assert server.handle({"jsonrpc": "2.0", "method": "ping"}) is None

    print("All tests passed.")


if __name__ == "__main__":
    main()
