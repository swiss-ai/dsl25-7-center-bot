from slack_sdk import WebClient
from dotenv import load_dotenv
import os
import json
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import Depends

from models.base import get_db, SessionLocal
from models.conversation import User, Conversation, Message
from services.mcp.claude import process_with_claude, claude_mcp_request, get_claude_response_text
from services.conversation.manager import ConversationManager

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_BOT_TOKEN)
logger = logging.getLogger(__name__)

async def handle_slack_event(event_data: dict):
    """
    Process Slack events, focusing on messages that mention the bot.
    
    Args:
        event_data: The event data from Slack
    """
    # Skip retries and bot messages
    if event_data.get("X-Slack-Retry-Num") or event_data.get("X-Slack-Retry-Reason"):
        return
    
    event = event_data.get("event", {})
    event_type = event.get("type")
    
    # Handle different event types
    if event_type == "app_mention":
        await handle_app_mention(event)
    elif event_type == "message" and "subtype" not in event:
        # Only process messages in DMs with the bot
        if event.get("channel_type") == "im":
            await handle_direct_message(event)

async def handle_app_mention(event: dict):
    """
    Handle when the bot is mentioned in a channel.
    
    Args:
        event: The Slack event
    """
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts", ts)
    
    # Remove the bot mention from the text
    # This assumes the mention is at the beginning of the message
    clean_text = text.split(">", 1)[1].strip() if ">" in text else text
    
    try:
        # Get database session
        db = SessionLocal()
        
        try:
            # Skip typing indicator - we'll just send a direct response instead
            
            # Get or create user
            user = await ConversationManager.get_or_create_user(
                db=db,
                platform_id=user_id,
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
                content=clean_text,
                platform_ts=ts
            )
            
            # Get conversation history for context
            conversation_history = await ConversationManager.get_conversation_history_for_claude(
                db=db,
                conversation_id=conversation.id
            )
            
            # Use Claude MCP with tools and history - ALWAYS enable tools
            # Get dependencies from main to avoid circular imports
            from main import document_processor, gdrive_mcp, web_content_manager
            
            # Always force tool use to ensure knowledge-based responses
            claude_response = await claude_mcp_request(
                user_message=clean_text,
                conversation_history=conversation_history,
                enable_tool_use=True,  # Always enable tools to restrict to knowledge base
                document_processor=document_processor,
                gdrive_mcp=gdrive_mcp,
                web_content_manager=web_content_manager
            )
            
            # Extract text response
            response_text = await get_claude_response_text(claude_response)
            
            # Store assistant response
            assistant_message = await ConversationManager.add_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=response_text
            )
            
            # Slack message character limit (40,000 chars to be safe)
            SLACK_CHAR_LIMIT = 40000
            
            # Truncate response if needed
            if len(response_text) > SLACK_CHAR_LIMIT:
                response_text = response_text[:SLACK_CHAR_LIMIT-100] + "\n\n[Response truncated due to length]"
            
            # Send a single response message
            client.chat_postMessage(
                channel=channel_id,
                text=response_text,
                thread_ts=thread_ts,
                mrkdwn=True
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling app mention: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"Sorry, I encountered an error: {str(e)}",
            thread_ts=thread_ts
        )

async def handle_direct_message(event: dict):
    """
    Handle direct messages to the bot.
    
    Args:
        event: The Slack event
    """
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    ts = event.get("ts")
    
    try:
        # Get database session
        db = SessionLocal()
        
        try:
            # Skip typing indicator - we'll just send a direct response instead
            
            # Get or create user
            user = await ConversationManager.get_or_create_user(
                db=db,
                platform_id=user_id,
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
                content=text,
                platform_ts=ts
            )
            
            # Get conversation history for context
            conversation_history = await ConversationManager.get_conversation_history_for_claude(
                db=db,
                conversation_id=conversation.id
            )
            
            # Use Claude MCP with tools and history
            # Get dependencies from main to avoid circular imports
            from main import document_processor, gdrive_mcp, web_content_manager
            
            # Use advanced MCP capabilities with tools
            claude_response = await claude_mcp_request(
                user_message=text,
                conversation_history=conversation_history,
                enable_tool_use=True,
                document_processor=document_processor,
                gdrive_mcp=gdrive_mcp,
                web_content_manager=web_content_manager
            )
            
            # Extract text response
            response_text = await get_claude_response_text(claude_response)
            
            # Store assistant response
            assistant_message = await ConversationManager.add_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=response_text
            )
            
            # Slack message character limit (40,000 chars to be safe)
            SLACK_CHAR_LIMIT = 40000
            
            # Truncate response if needed
            if len(response_text) > SLACK_CHAR_LIMIT:
                response_text = response_text[:SLACK_CHAR_LIMIT-100] + "\n\n[Response truncated due to length]"
            
            # Send a single response message
            client.chat_postMessage(
                channel=channel_id,
                text=response_text,
                mrkdwn=True
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling direct message: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"Sorry, I encountered an error: {str(e)}"
        )

async def handle_message_with_context(
    event: dict, 
    conversation_id: Optional[str] = None, 
    document_processor=None,
    gdrive_mcp=None
):
    """
    Handle a message with conversation context.
    This is a more advanced version that will be used more fully in Phase 2.
    
    Args:
        event: The Slack event
        conversation_id: Optional conversation ID
        document_processor: Document processor instance (optional)
        gdrive_mcp: Google Drive MCP instance (optional)
    """
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts", ts)
    
    try:
        # Get database session
        db = SessionLocal()
        
        try:
            # Skip typing indicator - we'll just send a direct response instead
            
            # Get or create user
            user = await ConversationManager.get_or_create_user(
                db=db,
                platform_id=user_id,
                platform="slack"
            )
            
            # Get specified conversation or active one
            conversation = None
            if conversation_id:
                # Query by ID if provided
                conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            else:
                # Otherwise get active conversation
                conversation = await ConversationManager.get_active_conversation(
                    db=db,
                    user_id=user.id,
                    channel_id=channel_id,
                    thread_ts=thread_ts if thread_ts != ts else None
                )
            
            # Create new conversation if needed
            if not conversation:
                conversation = await ConversationManager.create_conversation(
                    db=db,
                    user_id=user.id,
                    channel_id=channel_id,
                    thread_ts=thread_ts if thread_ts != ts else None
                )
            
            # Store user message
            await ConversationManager.add_message(
                db=db,
                conversation_id=conversation.id,
                role="user",
                content=text,
                platform_ts=ts
            )
            
            # Get conversation history for context
            conversation_history = await ConversationManager.get_conversation_history_for_claude(
                db=db,
                conversation_id=conversation.id
            )
            
            # Get dependencies from main to avoid circular imports
            from main import document_processor, gdrive_mcp, web_content_manager
            
            # Use Claude MCP with tools and history - ALWAYS enable tools
            claude_response = await claude_mcp_request(
                user_message=text,
                conversation_history=conversation_history,
                enable_tool_use=True,  # Always enable tools to restrict to knowledge base
                document_processor=document_processor,
                gdrive_mcp=gdrive_mcp,
                web_content_manager=web_content_manager
            )
            
            # Extract text response
            response_text = await get_claude_response_text(claude_response)
            
            # Store assistant response
            assistant_message = await ConversationManager.add_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=response_text
            )
            
            # Slack message character limit (40,000 chars to be safe)
            SLACK_CHAR_LIMIT = 40000
            
            # Truncate response if needed
            if len(response_text) > SLACK_CHAR_LIMIT:
                response_text = response_text[:SLACK_CHAR_LIMIT-100] + "\n\n[Response truncated due to length]"
            
            # Send a single response message
            client.chat_postMessage(
                channel=channel_id,
                text=response_text,
                thread_ts=thread_ts if thread_ts != ts else None,
                mrkdwn=True
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling message with context: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"Sorry, I encountered an error: {str(e)}",
            thread_ts=thread_ts if thread_ts != ts else None
        )

async def get_thread_history(channel_id: str, thread_ts: str):
    """
    Get the conversation history for a thread.
    
    Args:
        channel_id: The Slack channel ID
        thread_ts: The thread timestamp
        
    Returns:
        List of messages in the thread
    """
    try:
        result = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts
        )
        
        # Return the messages, excluding the loading/typing messages
        return [msg for msg in result["messages"] if msg.get("text") != "Thinking..."]
    except Exception as e:
        logger.error(f"Error getting thread history: {e}")
        return []

def format_conversation_for_claude(messages):
    """
    Format Slack conversation history for Claude.
    
    Args:
        messages: List of Slack messages
        
    Returns:
        Formatted conversation history for Claude
    """
    formatted = []
    
    for message in messages:
        is_bot = message.get("bot_id") is not None
        role = "assistant" if is_bot else "user"
        
        formatted.append({
            "role": role,
            "content": message.get("text", "")
        })
    
    return formatted