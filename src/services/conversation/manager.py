import logging
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from models.base import get_db
from models.conversation import User, Conversation, Message, ToolCall

logger = logging.getLogger(__name__)

class ConversationManager:
    """Service for managing conversation data."""
    
    @staticmethod
    async def get_or_create_user(db: Session, platform_id: str, platform: str = "slack", name: Optional[str] = None) -> User:
        """
        Get a user by platform ID or create if not found.
        
        Args:
            db: Database session
            platform_id: Platform-specific user ID (e.g., Slack user ID)
            platform: Platform name (default: "slack")
            name: User's name (optional)
            
        Returns:
            User: The user object
        """
        try:
            user = db.query(User).filter(User.platform_id == platform_id, User.platform == platform).first()
            
            if not user:
                user = User(
                    platform_id=platform_id,
                    platform=platform,
                    name=name
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                
            return user
        except SQLAlchemyError as e:
            logger.error(f"Error getting or creating user {platform_id}: {e}")
            db.rollback()
            raise e
    
    @staticmethod
    async def create_conversation(
        db: Session,
        user_id: str,
        channel_id: str,
        thread_ts: Optional[str] = None,
        title: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            db: Database session
            user_id: The user ID
            channel_id: The channel ID
            thread_ts: Thread timestamp (optional)
            title: Conversation title (optional)
            meta_data: Additional metadata (optional)
            
        Returns:
            Conversation: The new conversation
        """
        try:
            conversation = Conversation(
                user_id=user_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
                title=title,
                meta_data=meta_data
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            
            return conversation
        except SQLAlchemyError as e:
            logger.error(f"Error creating conversation: {e}")
            db.rollback()
            raise e
    
    @staticmethod
    async def get_active_conversation(
        db: Session,
        user_id: str,
        channel_id: str,
        thread_ts: Optional[str] = None
    ) -> Optional[Conversation]:
        """
        Get the active conversation for a user in a channel/thread.
        
        Args:
            db: Database session
            user_id: The user ID
            channel_id: The channel ID
            thread_ts: Thread timestamp (optional)
            
        Returns:
            Conversation: The active conversation or None
        """
        try:
            query = db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.channel_id == channel_id,
                Conversation.is_active == True
            )
            
            if thread_ts:
                query = query.filter(Conversation.thread_ts == thread_ts)
                
            return query.order_by(Conversation.updated_at.desc()).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting active conversation: {e}")
            raise e
    
    @staticmethod
    async def add_message(
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        platform_ts: Optional[str] = None,
        message_type: str = "text",
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a message to a conversation.
        
        Args:
            db: Database session
            conversation_id: The conversation ID
            role: Message role (user, assistant, system, tool)
            content: Message content
            platform_ts: Platform-specific timestamp (optional)
            message_type: Message type (text, tool_call, tool_result)
            meta_data: Additional metadata (optional)
            
        Returns:
            Message: The new message
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                platform_ts=platform_ts,
                message_type=message_type,
                meta_data=meta_data
            )
            db.add(message)
            
            # Update conversation timestamp
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conversation:
                conversation.updated_at = datetime.now()
                
            db.commit()
            db.refresh(message)
            
            return message
        except SQLAlchemyError as e:
            logger.error(f"Error adding message to conversation {conversation_id}: {e}")
            db.rollback()
            raise e
    
    @staticmethod
    async def add_tool_call(
        db: Session,
        message_id: str,
        tool_name: str,
        input_parameters: Dict[str, Any],
        output_result: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        error_message: Optional[str] = None
    ) -> ToolCall:
        """
        Add a tool call to a message.
        
        Args:
            db: Database session
            message_id: The message ID
            tool_name: The tool name
            input_parameters: Tool input parameters
            output_result: Tool output result (optional)
            status: Tool call status (pending, success, error)
            error_message: Error message (if status is error)
            
        Returns:
            ToolCall: The new tool call
        """
        try:
            tool_call = ToolCall(
                message_id=message_id,
                tool_name=tool_name,
                input_parameters=input_parameters,
                output_result=output_result,
                status=status,
                error_message=error_message
            )
            db.add(tool_call)
            db.commit()
            db.refresh(tool_call)
            
            return tool_call
        except SQLAlchemyError as e:
            logger.error(f"Error adding tool call to message {message_id}: {e}")
            db.rollback()
            raise e
    
    @staticmethod
    async def get_conversation_messages(db: Session, conversation_id: str) -> List[Message]:
        """
        Get all messages for a conversation.
        
        Args:
            db: Database session
            conversation_id: The conversation ID
            
        Returns:
            List[Message]: List of messages
        """
        try:
            return db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.timestamp).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting messages for conversation {conversation_id}: {e}")
            raise e
    
    @staticmethod
    async def get_conversation_history_for_claude(db: Session, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history formatted for Claude.
        
        Args:
            db: Database session
            conversation_id: The conversation ID
            
        Returns:
            List[Dict]: Formatted messages for Claude
        """
        try:
            messages = await ConversationManager.get_conversation_messages(db, conversation_id)
            
            formatted_messages = []
            for msg in messages:
                # Only include user and assistant messages for Claude
                if msg.role in ["user", "assistant"]:
                    formatted_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                # Include tool messages as well
                elif msg.role == "tool":
                    formatted_messages.append({
                        "role": "tool",
                        "content": msg.content,
                        "name": msg.meta_data.get("tool_name") if msg.meta_data else "unknown_tool"
                    })
                    
            return formatted_messages
        except SQLAlchemyError as e:
            logger.error(f"Error getting history for conversation {conversation_id}: {e}")
            raise e
    
    @staticmethod
    async def end_conversation(db: Session, conversation_id: str) -> bool:
        """
        End a conversation (mark as inactive).
        
        Args:
            db: Database session
            conversation_id: The conversation ID
            
        Returns:
            bool: Success status
        """
        try:
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conversation:
                conversation.is_active = False
                db.commit()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error ending conversation {conversation_id}: {e}")
            db.rollback()
            raise e