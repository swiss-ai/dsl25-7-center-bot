# This is a wrapper for the MCP Slack bot that uses the MCPClient to process queries.
#it uses the Slack Bolt framework to handle events and send messages via MCP.
import os
import asyncio
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from new_client import MCPClient

load_dotenv()

# Load Slack tokens
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Async Slack App
app = AsyncApp(token=SLACK_BOT_TOKEN)
mcp_client = MCPClient()

@app.event("app_mention")
async def handle_app_mention(event, say, client):
    user_message = event.get("text", "")
    slack_user = event.get("user")
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")

    if not user_message or not slack_user:
        return

    await say(f"Hey <@{slack_user}>, working on it... 🤖")
    print(f"\n🔹 Incoming message: {user_message}")
    print(f"📍 From user: {slack_user}, in channel: {channel_id}, thread_ts: {thread_ts}")

    cleaned_message = ' '.join(word for word in user_message.split() if not word.startswith("<@"))
    prompt = f"""
You are a Slack assistant that uses tools via MCP.

The user is in channel `{channel_id}` and thread `{thread_ts}`.
You should answer by calling `slack_reply_to_thread`.

User request: {cleaned_message}

Use other Slack tools as needed, like `slack_list_channels` or `slack_get_channel_history`, to find the necessary info.
"""
    print(f"🧹 Cleaned message: {cleaned_message}")



    # EXACTLY like client.py behavior
    print("🔁 Calling process_query()...")
    result = await mcp_client.process_query(prompt)
    print("✅ Result:\n", result)

    # Do NOT post the result — Claude will do it with slack_reply_to_thread
    # Optionally: log that we’re done
    print("✅ Claude handled the response via tool.")

# Startup function
async def main():
    await mcp_client.connect_to_server()
    print("✅ Connected to MCP, starting Slack bot...")
    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    await handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())
