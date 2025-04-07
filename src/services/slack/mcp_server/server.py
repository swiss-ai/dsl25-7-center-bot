# MCP server for Slack integration
import asyncio
import sys
import json
import os
import logging
from typing import Dict, Any, List, Optional
from slack_sdk import WebClient
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="mcp_server.log"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Force UTF-8 encoding for stdout and stderr
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

class SlackTools:
    @staticmethod
    async def post_message(channel_id: str, text: str) -> Dict[str, Any]:
        """Post a message to a Slack channel."""
        try:
            response = slack_client.chat_postMessage(channel=channel_id, text=text)
            return {"ok": True, "message": response.data}
        except Exception as e:
            logger.error(f"Error posting message: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def reply_to_thread(channel_id: str, thread_ts: str, text: str) -> Dict[str, Any]:
        """Reply to a thread in a Slack channel."""
        try:
            response = slack_client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts
            )
            return {"ok": True, "message": response.data}
        except Exception as e:
            logger.error(f"Error replying to thread: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def get_channel_history(channel_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get the message history for a channel."""
        try:
            response = slack_client.conversations_history(channel=channel_id, limit=limit)
            return {"ok": True, "messages": response.data.get("messages", [])}
        except Exception as e:
            logger.error(f"Error getting channel history: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def get_thread_replies(channel_id: str, thread_ts: str) -> Dict[str, Any]:
        """Get replies to a thread."""
        try:
            response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts)
            return {"ok": True, "messages": response.data.get("messages", [])}
        except Exception as e:
            logger.error(f"Error getting thread replies: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def add_reaction(channel_id: str, timestamp: str, reaction: str) -> Dict[str, Any]:
        """Add a reaction to a message."""
        try:
            response = slack_client.reactions_add(
                channel=channel_id,
                timestamp=timestamp,
                name=reaction
            )
            return {"ok": True, "message": response.data}
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            return {"ok": False, "error": str(e)}

# Tool schemas
TOOLS = [
    {
        "name": "slack_post_message",
        "description": "Post a message to a Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel to post to"},
                "text": {"type": "string", "description": "The text of the message to post"}
            },
            "required": ["channel_id", "text"]
        }
    },
    {
        "name": "slack_reply_to_thread",
        "description": "Reply to a thread in a Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "thread_ts": {"type": "string", "description": "The timestamp of the thread to reply to"},
                "text": {"type": "string", "description": "The text of the message to post"}
            },
            "required": ["channel_id", "thread_ts", "text"]
        }
    },
    {
        "name": "slack_get_channel_history",
        "description": "Get recent messages from a Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "limit": {"type": "integer", "description": "Maximum number of messages to return"}
            },
            "required": ["channel_id"]
        }
    },
    {
        "name": "slack_get_thread_replies",
        "description": "Get all replies in a thread",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "thread_ts": {"type": "string", "description": "The timestamp of the thread"}
            },
            "required": ["channel_id", "thread_ts"]
        }
    },
    {
        "name": "slack_add_reaction",
        "description": "Add a reaction emoji to a message",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "timestamp": {"type": "string", "description": "The timestamp of the message"},
                "reaction": {"type": "string", "description": "Name of the emoji (without colons)"}
            },
            "required": ["channel_id", "timestamp", "reaction"]
        }
    },
    {
        "name": "search",
        "description": "Search for information in the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "source": {"type": "string", "description": "The source to search (all, web, drive, notion)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_document",
        "description": "Fetch a specific document from the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "The ID of the document"},
                "source": {"type": "string", "description": "The source system (drive, web, notion)"}
            },
            "required": ["document_id", "source"]
        }
    },
    {
        "name": "web_fetch",
        "description": "Fetch content from a URL and add it to the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "gdrive_search",
        "description": "Search for files in Google Drive",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Maximum number of results to return"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "gdrive_get_file",
        "description": "Get content from a Google Drive file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "The ID of the file to fetch"}
            },
            "required": ["file_id"]
        }
    }
]

async def handle_request():
    """Main MCP server loop."""
    logger.info("🚀 Starting MCP server for Slack integration...")
    
    slack_tools = SlackTools()
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
                
            request = json.loads(line)
            logger.info(f"📥 Received request: {request}")
            
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
                            "name": "AI Center Bot MCP Server",
                            "version": "0.1.0"
                        }
                    }
                }
                logger.info("✅ Initialized successfully")
                
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
                logger.info("🧰 Sent tool list")
                
            elif method == "tools/call":
                tool_name = request["params"]["name"]
                arguments = request["params"]["arguments"]
                
                logger.info(f"🔧 Tool call: {tool_name}, args: {arguments}")
                
                try:
                    # Handle Slack tools
                    if tool_name == "slack_post_message":
                        result = await slack_tools.post_message(
                            channel_id=arguments["channel_id"],
                            text=arguments["text"]
                        )
                        
                    elif tool_name == "slack_reply_to_thread":
                        result = await slack_tools.reply_to_thread(
                            channel_id=arguments["channel_id"],
                            thread_ts=arguments["thread_ts"],
                            text=arguments["text"]
                        )
                        
                    elif tool_name == "slack_get_channel_history":
                        result = await slack_tools.get_channel_history(
                            channel_id=arguments["channel_id"],
                            limit=arguments.get("limit", 10)
                        )
                        
                    elif tool_name == "slack_get_thread_replies":
                        result = await slack_tools.get_thread_replies(
                            channel_id=arguments["channel_id"],
                            thread_ts=arguments["thread_ts"]
                        )
                        
                    elif tool_name == "slack_add_reaction":
                        result = await slack_tools.add_reaction(
                            channel_id=arguments["channel_id"],
                            timestamp=arguments["timestamp"],
                            reaction=arguments["reaction"]
                        )
                        
                    # Knowledge tools would be implemented in the main script and handled by signals
                    # For this example, we'll return a mock response
                    elif tool_name in ["search", "fetch_document", "web_fetch", "gdrive_search", "gdrive_get_file"]:
                        result = {
                            "ok": True,
                            "message": f"This is a mock response for the {tool_name} tool. In production, this would communicate with the main application."
                        }
                    
                    else:
                        result = {"ok": False, "error": f"Unknown tool: {tool_name}"}
                    
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                        }
                    }
                except Exception as e:
                    logger.error(f"❌ Error executing tool {tool_name}: {e}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Error executing tool {tool_name}: {str(e)}"
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
                logger.error(f"❓ Unknown method: {method}")
            
            # Send response
            print(json.dumps(response))
            sys.stdout.flush()
            logger.info(f"📤 Sent response: {response}")
            
        except Exception as e:
            logger.error(f"🔥 Fatal server error: {e}")
            # Send error response
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in locals() else None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(response))
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(handle_request())
