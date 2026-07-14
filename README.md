# Minimal MCP

A custom [Model Context Protocol](https://modelcontextprotocol.io) server in
**two files, zero dependencies, no auth** — the smallest thing that is still a
real, spec-valid MCP server. Built to *show how a custom MCP works* and to run
on AWS Lambda + API Gateway.

```
minimal_mcp/
├── mcp_core.py         # the reusable engine: JSON-RPC 2.0 + MCP methods
├── lambda_function.py  # your tools (todo example) + AWS Lambda adapter + demo
├── test_mcp.py         # a handful of assertions
├── deploy.sh           # zip + create Lambda + API Gateway (POST /mcp)
└── README.md
```

## The idea

An MCP server is just a **JSON-RPC 2.0 endpoint** that implements a few methods:

| Method | Purpose |
|--------|---------|
| `initialize` | Handshake: protocol version + capabilities + server info |
| `tools/list` | Advertise the tools and their JSON Schemas |
| `tools/call` | Run one tool by name with arguments |

`mcp_core.py` implements exactly that. You register tools with a decorator and
feed the server parsed JSON-RPC messages:

```python
from mcp_core import MCPServer

server = MCPServer("minimal-mcp")

@server.tool("add", "Add two numbers.",
             {"type": "object", "required": ["a", "b"],
              "properties": {"a": {"type": "number"}, "b": {"type": "number"}}})
def add(args: dict) -> str:
    return str(args["a"] + args["b"])

server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
```

Flow:

```
JSON-RPC request ─► server.handle(msg) ─► dispatch by method
                                            ├─ initialize → server info + capabilities
                                            ├─ tools/list → [{name, description, inputSchema}]
                                            └─ tools/call → your @tool function → {content:[{type:"text",...}]}
```

That's the whole protocol. Everything else (auth, databases, streaming) is
production hardening layered on top of this same core.

## Run it locally (no AWS)

```bash
cd minimal_mcp
python3 lambda_function.py     # runs a full MCP session against the todo tools
python3 test_mcp.py            # or: run the assertions
```

## Add your own tool

In `lambda_function.py`, register a function. It receives the call's
`arguments` dict and returns a string:

```python
@server.tool(
    "greet",
    "Greet someone by name.",
    {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
)
def greet(args: dict) -> str:
    return f"Hello, {args['name']}!"
```

It automatically shows up in `tools/list` and is callable via `tools/call`.

## Deploy to AWS

Because there are **no dependencies**, packaging is just zipping two files —
no `pip install`, no platform wheels to worry about.

```bash
cd minimal_mcp
ROLE_ARN=arn:aws:iam::<acct>:role/<lambda-exec-role> ./deploy.sh
```

The script zips `mcp_core.py` + `lambda_function.py`, creates/updates a
`python3.12` Lambda (`handler = lambda_function.lambda_handler`), and puts an
API Gateway HTTP API in front with a `POST /mcp` route. It prints the endpoint.

Smoke test:

```bash
curl -s -X POST "$ENDPOINT/mcp" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

## Connect a client (Claude Code)

```bash
claude mcp add --transport http minimal-mcp "$ENDPOINT/mcp"
```

> No auth here by design. Anyone with the URL can call it — fine for a demo or a
> private/internal endpoint. For bearer tokens or OAuth, see `../full_mcp`.
