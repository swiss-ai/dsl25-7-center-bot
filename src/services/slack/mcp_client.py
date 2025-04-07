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
        
        # Connect to the server
        server_params = StdioServerParameters(
            command="python",
            args=[script_path],
            env={
                "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
                "PYTHONPATH": os.getcwd()  # Add current directory to Python path
            }
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
        script_dir = os.path.join(os.getcwd(), "src", "services", "slack", "mcp_server")
        script_path = os.path.join(script_dir, "server.py")
        
        # Check if script exists
        if not os.path.exists(script_path):
            logger.error(f"Server script not found at {script_path}")
            raise FileNotFoundError(f"MCP server script not found at {script_path}")
            
        logger.info(f"Using MCP server script at {script_path}")
        return script_path
    
    async def process_query(self, prompt: str, conversation_history: Optional[List[Dict[str, str]]] = None, 
                          channel_id: Optional[str] = None, thread_ts: Optional[str] = None) -> str:
        """
        Process a query using Claude MCP.
        
        Args:
            prompt: The prompt to send to Claude
            conversation_history: Optional conversation history
            channel_id: Slack channel ID (for context)
            thread_ts: Thread timestamp (for thread replies)
            
        Returns:
            Claude's response (though the actual reply is sent through Slack tools)
        """
        if not self.session:
            logger.error("MCP session not initialized")
            return "Error: MCP session not initialized"
        
        # Get available tools
        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        # Format conversation history for Claude
        messages = []
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add the current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        logger.info(f"Sending prompt to Claude: {prompt[:50]}...")
        
        try:
            # Send request to Claude
            response = await self.anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4000,
                messages=messages,
                tools=available_tools
            )
            
            logger.info("Received response from Claude")
            
            # Process Claude's response for tool use
            final_text = []
            tool_used = False
            
            for content in response.content:
                if content.type == 'text':
                    final_text.append(content.text)
                
                elif content.type == 'tool_use':
                    tool_used = True
                    tool_name = content.name
                    tool_args = content.input
                    
                    logger.info(f"Tool use detected: {tool_name}")
                    
                    # Execute the tool using MCP
                    result = await self.session.call_tool(tool_name, tool_args)
                    
                    # Continue conversation with tool result
                    follow_up_messages = messages.copy()
                    follow_up_messages.append({
                        "role": "assistant",
                        "content": [content]
                    })
                    follow_up_messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content[0].text
                            }
                        ]
                    })
                    
                    # Get Claude's follow-up response
                    follow_up_response = await self.anthropic.messages.create(
                        model="claude-3-5-sonnet-20240620",
                        max_tokens=4000,
                        messages=follow_up_messages,
                        tools=available_tools
                    )
                    
                    # Process follow-up response
                    for follow_up_content in follow_up_response.content:
                        if follow_up_content.type == 'text':
                            final_text.append(follow_up_content.text)
            
            # If we didn't use a tool that posts to Slack, send the response now
            if not tool_used:
                response_text = "\n".join(final_text)
                
                # Send the response to Slack
                if thread_ts:
                    await self.session.call_tool("slack_reply_to_thread", {
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                        "text": response_text
                    })
                else:
                    await self.session.call_tool("slack_post_message", {
                        "channel_id": channel_id,
                        "text": response_text
                    })
            
            return "\n".join(final_text)
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            error_message = f"Sorry, I encountered an error: {str(e)}"
            
            # Send error message to Slack
            if thread_ts:
                await self.session.call_tool("slack_reply_to_thread", {
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "text": error_message
                })
            elif channel_id:
                await self.session.call_tool("slack_post_message", {
                    "channel_id": channel_id,
                    "text": error_message
                })
                
            return error_message
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")