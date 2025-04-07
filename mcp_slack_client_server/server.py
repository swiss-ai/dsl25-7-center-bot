#this is the server code for the slack mcp client
# it is a simple server that listens for requests from the client and executes the requested tool


#!/usr/bin/env python

import asyncio
import sys
import json
import os
from tools import SLACK_TOOLS
from slack_tools import SlackMCPTools
from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 encoding for stdout and stderr (important on Windows)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Setup logging to a file
LOG_FILE = open("server_log.txt", "a", buffering=1, encoding="utf-8")  # line-buffered

def log(message: str):
    LOG_FILE.write(message + "\n")
    LOG_FILE.flush()

async def main():
    log("🚀 Starting Python Slack MCP Server...")

    slack_tools = SlackMCPTools()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            log(f"📥 Received request: {request}")

            method = request.get("method")
            request_id = request.get("id")

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "sampling": {},
                            "roots": {"listChanged": True}
                        },
                        "serverInfo": {
                            "name": "Slack MCP Server",
                            "version": "0.1.0"
                        }
                    }
                }
                log("✅ Initialized successfully.")

            elif method == "tools/list":
                tools_info = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                param.name: {
                                    "type": param.type,
                                    "description": param.description,
                                } for param in tool.parameters
                            },
                            "required": [param.name for param in tool.parameters if param.required],
                        }
                    }
                    for tool in SLACK_TOOLS
                ]
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": tools_info
                    }
                }
                log("🛠️ Sent tool list.")

            elif method == "tools/call":
                tool_name = request["params"]["name"]
                arguments = request["params"]["arguments"]

                try:
                    result = await slack_tools.execute_tool(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": result}]
                        }
                    }
                    log(f"⚙️ Tool '{tool_name}' executed successfully.")
                except Exception as e:
                    log(f"❌ Error during tool execution: {e}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": str(e)
                        }
                    }

            else:
                # Unknown method
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}"
                    }
                }
                log(f"❓ Unknown method: {method}")

        except Exception as e:
            log(f"🔥 Fatal server error: {e}")
            # On parsing failure, send a generic error response if possible
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }

        # Always send response
        print(json.dumps(response))
        sys.stdout.flush()
        log(f"📤 Sent response: {response}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"💥 Fatal error on startup: {e}")
