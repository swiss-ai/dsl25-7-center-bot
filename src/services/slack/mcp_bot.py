# MCP-based Slack bot for AI Center
import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

from models.base import SessionLocal
from models.conversation import User, Conversation, Message
from services.conversation.manager import ConversationManager
from services.slack.mcp_client import MCPSlackClient

load_dotenv()

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Configure logging
logger = logging.getLogger(__name__)

# Create app instance
app = AsyncApp(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None
mcp_client = None

async def initialize_mcp_client(document_processor=None, gdrive_manager=None, web_content_manager=None):
    """Initialize the MCP client with knowledge tools."""
    global mcp_client
    
    # Create MCP client
    mcp_client = MCPSlackClient()
    
    # Connect to the MCP server with knowledge tools
    await mcp_client.connect_to_server(
        document_processor=document_processor, 
        gdrive_manager=gdrive_manager,
        web_content_manager=web_content_manager
    )
    
    logger.info("MCP Slack client initialized and connected to server")
    return mcp_client

# This cache will store recently processed message IDs to avoid duplicates
processed_messages = {}

@app.event("app_mention")
async def handle_app_mention(event, say, client):
    """Handle @mentions of the bot in Slack channels."""
    global mcp_client, processed_messages

    message_ts = event.get("ts")
    channel_id = event.get("channel")
    user_id = event.get("user")
    thread_ts = event.get("thread_ts") or message_ts
    raw_text = event.get("text", "")

    # Prevent duplicate handling
    if message_ts in processed_messages:
        logger.info(f"Skipping duplicate message: {message_ts}")
        return
    processed_messages[message_ts] = True
    if len(processed_messages) > 100:
        for ts in sorted(processed_messages)[:-100]:
            processed_messages.pop(ts)

    # Ensure MCP is ready
    if not mcp_client:
        await say("Sorry, I'm still starting up. Try again in a moment.", thread_ts=thread_ts)
        return

    # Clean user message (remove bot mention)
    cleaned_text = ' '.join(w for w in raw_text.split() if not w.startswith("<@"))
    logger.info(f"Bot mentioned by {user_id} in {channel_id}: {cleaned_text}")

    # Show typing indicator
    await say("Thinking...", thread_ts=thread_ts)

    db = SessionLocal()
    try:
        # Get or create user record
        user = await ConversationManager.get_or_create_user(
            db=db, platform_id=user_id, platform="slack"
        )

        # Fetch or start new conversation
        conversation = await ConversationManager.get_active_conversation(
            db=db, user_id=user.id, channel_id=channel_id, thread_ts=thread_ts
        ) or await ConversationManager.create_conversation(
            db=db, user_id=user.id, channel_id=channel_id, thread_ts=thread_ts
        )

        # Store the incoming message
        await ConversationManager.add_message(
            db=db, conversation_id=conversation.id, role="user", content=cleaned_text, platform_ts=message_ts
        )

        # Build conversation history for prompt context
        history = await ConversationManager.get_conversation_history_for_claude(
            db=db, conversation_id=conversation.id
        )

        # Construct the system prompt
        prompt = f"""
        You are a Slack assistant helping users by combining your general knowledge with specialized information retrieved via MCP tools.

        GUIDING RULES:
        1. If relevant information is found in the knowledge base (via tools), you MUST prioritize and trust that over your own knowledge.
        2. If relevant information is not found in the knowledge base, you may use your general knowledge (pretrained data) but you MUST say that you did not find it in the knowledge base (litteraly write that).
        3. In case of any conflict between your pretraining and tool data, prefer the tool data.

        SOURCE CITATION REQUIREMENTS:
        Always cite your sources when using tool-based results:
        - Knowledge Base: [Title, Last Updated: <date>]
        - Google Drive: [Google Drive: Title, Modified: <date>]
        - Web Content: [Web: Title, URL]

        KNOWLEDGE TOOLS:
        - `search`: Search for info in the knowledge base
        - `fetch_document`: Retrieve a full document from the knowledge base
        - `web_fetch`: Add and retrieve content from a public URL
        - `gdrive_search`: Search for Google Drive files
        - `gdrive_get_file`: Fetch content from a Google Drive file

        CONTEXT:
        - User is in channel `{channel_id}`, thread `{thread_ts}`
        - Use `slack_reply_to_thread` to respond

        User request: {cleaned_text}

        """

        # Let the MCP client handle everything
        await mcp_client.process_query(
            prompt=prompt,
            conversation_history=history,
            channel_id=channel_id,
            thread_ts=thread_ts
        )

    except Exception as e:
        logger.error(f"Error handling @mention: {e}")
        await say(f"Sorry, something went wrong: {str(e)}", thread_ts=thread_ts)
    finally:
        db.close()


@app.event("message")
async def handle_direct_message(event, say, client):
    """Handle direct messages to the bot."""
    global mcp_client, processed_messages
    
    # Skip bot messages and non-direct messages
    if "subtype" in event or event.get("channel_type") != "im":
        return
    
    # Extract message ID for deduplication
    message_id = event.get("ts")
    
    # Skip if we've already processed this message
    if message_id in processed_messages:
        logger.info(f"Skipping already processed message: {message_id}")
        return
    
    # Mark this message as processed
    processed_messages[message_id] = True
    
    # Cleanup old messages from the cache (keep last 100 messages)
    if len(processed_messages) > 100:
        oldest_keys = sorted(processed_messages.keys())[:len(processed_messages) - 100]
        for key in oldest_keys:
            processed_messages.pop(key, None)
        
    if not mcp_client:
        await say("Sorry, the bot is still initializing. Please try again in a few moments.")
        return
        
    user_message = event.get("text", "")
    slack_user = event.get("user")
    channel_id = event.get("channel")
    ts = event.get("ts")
    
    if not user_message or not slack_user:
        return

    # Get typing indicator
    await say("Thinking...")
    
    # Log the incoming message
    logger.info(f"Incoming DM from {slack_user}: {user_message}")
    
    # Get database session for conversation tracking
    db = SessionLocal()
    
    try:
        # Get or create user
        user = await ConversationManager.get_or_create_user(
            db=db,
            platform_id=slack_user,
            platform="slack"
        )
        
        # Get active conversation or create new one
        conversation = await ConversationManager.get_active_conversation(
            db=db,
            user_id=user.id,
            channel_id=channel_id
        )
        
        if not conversation:
            conversation = await ConversationManager.create_conversation(
                db=db,
                user_id=user.id,
                channel_id=channel_id
            )
        
        # Store user message
        await ConversationManager.add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=user_message,
            platform_ts=ts
        )
        
        # Get conversation history for context
        conversation_history = await ConversationManager.get_conversation_history_for_claude(
            db=db,
            conversation_id=conversation.id
        )
        
        # Create prompt with conversation context and tool instructions
        prompt = f"""
        You are a Slack assistant that uses tools via MCP to answer questions based ONLY on the knowledge base.

        CRITICAL RESTRICTIONS:
        1. You MUST NEVER use information outside of the provided knowledge sources
        2. If the information is not in the knowledge base, Google Drive, or fetched web content, you MUST say that you don't have that information
        3. DO NOT use your general knowledge or training data to answer questions - ONLY use the search and file access tools
        4. ALWAYS cite the source of your information using the metadata provided with each result

        SOURCE CITATION FORMAT:
        When you get information from a tool, you MUST cite the source properly using the source metadata provided:
        - For knowledge base results: [Title, Last Updated: date]
        - For Google Drive files: [Google Drive: Title, Modified: date]
        - For web content: [Web: Title, URL]
        
        Always include source citation immediately after presenting information from that source.

        Use these knowledge base tools to find information:
        - search: Search for information in the knowledge base
        - fetch_document: Get specific document details
        - web_fetch: Retrieve information from a URL
        - gdrive_search: Search for files in Google Drive
        - gdrive_get_file: Get content from a Google Drive file

        The user is in a direct message in channel `{channel_id}`.
        After finding information, reply with `slack_post_message`.

        User request: {user_message}
        """
        
        # Process the query using the MCP client
        # This will handle tool use and generate a response
        await mcp_client.process_query(
            prompt=prompt,
            conversation_history=conversation_history,
            channel_id=channel_id
        )
        
    except Exception as e:
        logger.error(f"Error handling direct message: {e}")
        await say(f"Sorry, I encountered an error: {str(e)}")
    finally:
        db.close()

async def start_socket_mode():
    """Start the Socket Mode handler for the Slack app."""
    if not SLACK_APP_TOKEN:
        logger.error("SLACK_APP_TOKEN is not set - Socket Mode cannot be started")
        return False
        
    if not app:
        logger.error("Slack app not initialized - Socket Mode cannot be started")
        return False
        
    try:
        handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
        await handler.start_async()
        logger.info("Socket Mode handler connected")
        return True
    except Exception as e:
        logger.error(f"Error starting Socket Mode: {e}")
        return False