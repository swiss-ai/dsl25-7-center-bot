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

@app.event("app_mention")
async def handle_app_mention(event, say, client):
    """Handle mentions of the bot in channels."""
    global mcp_client
    if not mcp_client:
        await say("Sorry, the bot is still initializing. Please try again in a few moments.")
        return
        
    user_message = event.get("text", "")
    slack_user = event.get("user")
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    
    if not user_message or not slack_user:
        return

    # Get typing indicator
    await say(f"Thinking...", thread_ts=thread_ts)
    
    # Log the incoming message
    logger.info(f"Incoming mention from {slack_user} in {channel_id}: {user_message}")
    
    # Clean the message (remove the mention)
    cleaned_message = ' '.join(word for word in user_message.split() if not word.startswith("<@"))
    
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
            channel_id=channel_id,
            thread_ts=thread_ts
        )
        
        if not conversation:
            conversation = await ConversationManager.create_conversation(
                db=db,
                user_id=user.id,
                channel_id=channel_id,
                thread_ts=thread_ts
            )
        
        # Store user message
        await ConversationManager.add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=cleaned_message,
            platform_ts=event.get("ts")
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
        4. Always cite the source of your information (file name, search result, etc.)

        Use these knowledge base tools to find information:
        - search: Search for information in the knowledge base
        - fetch_document: Get specific document details
        - web_fetch: Retrieve information from a URL
        - gdrive_search: Search for files in Google Drive
        - gdrive_get_file: Get content from a Google Drive file

        The user is in channel `{channel_id}` and thread `{thread_ts}`.
        After finding information, reply with `slack_reply_to_thread`.

        User request: {cleaned_message}
        """
        
        # Process the query using the MCP client
        # This will handle tool use and generate a response
        await mcp_client.process_query(
            prompt=prompt,
            conversation_history=conversation_history,
            channel_id=channel_id,
            thread_ts=thread_ts
        )
        
    except Exception as e:
        logger.error(f"Error handling app mention: {e}")
        await say(f"Sorry, I encountered an error: {str(e)}", thread_ts=thread_ts)
    finally:
        db.close()

@app.event("message")
async def handle_direct_message(event, say, client):
    """Handle direct messages to the bot."""
    global mcp_client
    
    # Skip bot messages and non-direct messages
    if "subtype" in event or event.get("channel_type") != "im":
        return
        
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
        4. Always cite the source of your information (file name, search result, etc.)

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