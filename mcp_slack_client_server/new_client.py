# This is a Python script that connects to an MCP server and interacts with it using the Anthropic API.
# It allows users to send queries and receive responses, while also handling tool usage

import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path : str = './server.py'):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env={
        "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
        "SLACK_TEAM_ID": os.getenv("SLACK_TEAM_ID")
        }
        )
        print("Connecting to server...")
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        print("Connected to server!")
        await self.session.initialize()
        print("Server initialized!")
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        messages = [
            {"role": "user", "content": query}
        ]
        print("PROCESS QUERY CALLED with this query:", query)

        # Track tools that send responses to Slack (we'll stop after one)
        post_tool_names = {
            "slack_post_message",
            "slack_reply_to_thread",
            "slack_add_reaction"
        }
        post_tool_count = 0

        # Get available tools
        print("BEFORE await self.session.list_tools()")
        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        final_text = []
        print("GROS RAGEUX")

        while True:
            # Claude call with context + tools
            print("🔁 Sending prompt to Claude...")
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
                tools=available_tools
            )
            print("✅ Got response from Claude.")

            tool_used = False

            for content in response.content:
                if content.type == 'text':
                    final_text.append(content.text)

                elif content.type == 'tool_use':
                    tool_used = True
                    tool_name = content.name
                    tool_args = content.input

                    print(f"🛠 TOOL USE DETECTED: {tool_name}")
                    print(f"📦 Tool args: {tool_args}")

                    final_text.append(f"[Calling tool `{tool_name}` with args {tool_args}]")

                    # Run the tool
                    result = await self.session.call_tool(tool_name, tool_args)

                    # Track message-posting tools and stop if one was used
                    if tool_name in post_tool_names:
                        post_tool_count += 1
                        print(f"✉️ Post-like tool used: {tool_name} (count={post_tool_count})")
                        if post_tool_count >= 1:
                            print("🛑 Stopping after first post-like tool.")
                            return "\n".join(final_text)

                    # Continue conversation
                    if hasattr(content, 'text') and content.text:
                        messages.append({"role": "assistant", "content": content.text})
                    messages.append({"role": "user", "content": result.content})

                    break  # Only handle one tool at a time

            if not tool_used:
                print("✅ No more tools used. Ending loop.")
                break

        return "\n".join(final_text)



    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
        
    client = MCPClient()
    try:
        await client.connect_to_server()
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())