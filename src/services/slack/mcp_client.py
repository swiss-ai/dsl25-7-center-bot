# MCP client for Slack integration
import os
import logging
import asyncio
import sys
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from anthropic import Anthropic, AsyncAnthropic
from contextlib import AsyncExitStack
import subprocess
from slack_sdk import WebClient

# Attempt to import MCP library
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP library not available. Install with 'pip install mcp'")

load_dotenv()

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Configure logging
logger = logging.getLogger(__name__)

class MCPSlackClient:
    """MCP client for Slack integration."""
    
    def __init__(self):
        """Initialize the MCP client."""
        if not MCP_AVAILABLE:
            raise ImportError("MCP library not available. Install with 'pip install mcp'")
            
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.slack_client = WebClient(token=SLACK_BOT_TOKEN)
        self.anthropic = AsyncAnthropic(api_key=CLAUDE_API_KEY)
        self.document_processor = None
        self.gdrive_manager = None
        self.web_content_manager = None
        
    async def connect_to_server(self, document_processor=None, gdrive_manager=None, web_content_manager=None):
        """
        Connect to the MCP server.
        
        Args:
            document_processor: Document processor for knowledge base access
            gdrive_manager: Google Drive manager for file access
            web_content_manager: Web content manager for web access
        """
        # Store knowledge components for tool execution
        self.document_processor = document_processor
        self.gdrive_manager = gdrive_manager
        self.web_content_manager = web_content_manager
        
        # Start MCP server
        # First, create the server.py file in a temporary location
        script_path = await self._create_mcp_server()
        
        # Prepare environment variables
        env = {
            "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
            "PYTHONPATH": os.getcwd()  # Add current directory to Python path
        }
        
        # Add knowledge source environment variables if available
        if os.getenv("GOOGLE_CREDENTIALS_PATH"):
            env["GOOGLE_CREDENTIALS_PATH"] = os.getenv("GOOGLE_CREDENTIALS_PATH")
        if os.getenv("GOOGLE_TOKEN_PATH"):
            env["GOOGLE_TOKEN_PATH"] = os.getenv("GOOGLE_TOKEN_PATH")
        if os.getenv("GOOGLE_DRIVE_SYNC_FILE"):
            env["GOOGLE_DRIVE_SYNC_FILE"] = os.getenv("GOOGLE_DRIVE_SYNC_FILE")
        
        # Connect to the server
        server_params = StdioServerParameters(
            command="python",
            args=[script_path],
            env=env
        )
        
        logger.info("Connecting to MCP server...")
        
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            
            await self.session.initialize()
            
            # Get available tools
            response = await self.session.list_tools()
            tools = response.tools
            tool_names = [tool.name for tool in tools]
            
            logger.info(f"Connected to MCP server with tools: {tool_names}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            return False
    
    async def _create_mcp_server(self):
        """Return the path to the MCP server script."""
        # We now use a pre-created server script
        script_dir = os.path.join(os.getcwd(),  "services", "slack", "mcp_server")
        script_path = os.path.join(script_dir, "server.py")
        
        # Check if script exists
        if not os.path.exists(script_path):
            logger.error(f"Server script not found at {script_path}")
            raise FileNotFoundError(f"MCP server script not found at {script_path}")
            
        logger.info(f"Using MCP server script at {script_path}")
        return script_path
    
    async def process_query(
    self,
    prompt: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    channel_id: Optional[str] = None,
    thread_ts: Optional[str] = None
) -> str:
        """
        Process a user query using Claude and MCP tools.
        Supports multi-step reasoning with multiple tool calls.

        Args:
            prompt: User's prompt.
            conversation_history: Optional history for context.
            channel_id: Slack channel ID (used for posting).
            thread_ts: Slack thread timestamp.

        Returns:
            Claude's final response.
        """
        if not self.session:
            logger.error("MCP session not initialized")
            return "Error: MCP session not initialized"

        logger.info(" Starting process_query")
        
        try:
            # Get available tools
            tool_list_response = await self.session.list_tools()
            available_tools = [{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tool_list_response.tools]
            logger.info(f" Available tools: {[tool['name'] for tool in available_tools]}")

            # Build message list
            messages = []
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            messages.append({
                "role": "user",
                "content": prompt
            })

            final_text = []
            tool_used = False

            # Main tool-processing loop
            while True:
                logger.info(" Sending message to Claude")
                response = await self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=4000,
                    messages=messages,
                    tools=available_tools
                )

                tool_used = False  # Reset
                for content in response.content:
                    if content.type == 'text':
                        final_text.append(content.text)

                    elif content.type == 'tool_use':
                        tool_used = True
                        tool_name = content.name
                        tool_args = content.input
                        logger.info(f"🛠 Tool use detected: {tool_name} with args {tool_args}")
                        logger.info(f" Tool use detected: {tool_name} with args: {tool_args}")

                        # Call tool
                        result = await self.session.call_tool(tool_name, tool_args)

                        # Continue conversation with tool result
                        messages.append({
                            "role": "assistant",
                            "content": [content]
                        })
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content[0].text
                            }]
                        })
                        break  # One tool per round

                if not tool_used:
                    logger.info(" No more tools requested, ending loop")
                    break

            response_text = "\n".join(final_text)

            # If Claude didn’t use a Slack post tool, send message ourselves
            if not any(tool["name"].startswith("slack_") for tool in available_tools):
                logger.info("📬 Sending Slack message manually (Claude didn’t use Slack tools)")
                if thread_ts:
                    await self.session.call_tool("slack_reply_to_thread", {
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                        "text": response_text
                    })
                elif channel_id:
                    await self.session.call_tool("slack_post_message", {
                        "channel_id": channel_id,
                        "text": response_text
                    })
            logger.info("done with this query")
            return response_text

        except Exception as e:
            logger.error(f" Error in process_query: {e}")
            error_text = f"Sorry, I encountered an error: {str(e)}"

            # Fallback Slack error post
            if thread_ts:
                await self.session.call_tool("slack_reply_to_thread", {
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "text": error_text
                })
            elif channel_id:
                await self.session.call_tool("slack_post_message", {
                    "channel_id": channel_id,
                    "text": error_text
                })

            return error_text

    
    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")