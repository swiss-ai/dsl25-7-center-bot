import logging
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta

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
        
        For channel-wide history, this will:
        1. First try to get the exact thread conversation if thread_ts is provided
        2. If not found or not in thread, get the user's main channel conversation
        
        Args:
            db: Database session
            user_id: The user ID
            channel_id: The channel ID
            thread_ts: Thread timestamp (optional)
            
        Returns:
            Conversation: The active conversation or None
        """
        try:
            # First try to find an exact thread match if thread_ts is provided
            if thread_ts:
                thread_conversation = db.query(Conversation).filter(
                    Conversation.user_id == user_id,
                    Conversation.channel_id == channel_id,
                    Conversation.thread_ts == thread_ts,
                    Conversation.is_active == True
                ).order_by(Conversation.updated_at.desc()).first()
                
                if thread_conversation:
                    return thread_conversation
            
            # If no thread_ts provided or no thread conversation found,
            # look for the main channel conversation (where thread_ts is NULL)
            main_conversation = db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.channel_id == channel_id,
                Conversation.thread_ts == None,  # This means it's the main channel conversation
                Conversation.is_active == True
            ).order_by(Conversation.updated_at.desc()).first()
            
            # Return the main conversation if found
            if main_conversation:
                return main_conversation
                
            # If we reach this point, create a new conversation if needed
            # (calling code will handle this)
            return None
            
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
    async def get_conversation_history_for_claude(db: Session, conversation_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Return structured conversation history for use with LLMs (Claude/GPT).
        
        Args:
            db: Database session
            conversation_id: The conversation ID
            max_messages: Maximum number of recent messages to include (default: 10)
            
        Returns:
            List of formatted messages for Claude
        """
        try:
            messages = await ConversationManager.get_conversation_messages(db, conversation_id)

            # Ensure messages are ordered by timestamp
            # Use timestamp as primary sort key (never None), platform_ts as secondary
            # Use "" as default for None values to prevent comparison errors
            messages = sorted(messages, key=lambda m: (m.timestamp, m.platform_ts or ""))
            
            # Limit to the most recent messages (respecting Claude's context limits)
            # Include at most max_messages pairs of turns (user + assistant)
            if len(messages) > max_messages * 2:
                # If truncating, always include the first system message if available
                system_message = next((m for m in messages if m.role == "system"), None)
                
                # Get the most recent messages
                messages = messages[-(max_messages * 2):]
                
                # Add the system message at the beginning if it exists
                if system_message:
                    messages = [system_message] + messages
                    
                # Add a note about truncated history
                logger.info(f"Truncated conversation history from {len(messages)} to {max_messages * 2} messages")

            formatted_messages = []
            for msg in messages:
                if msg.role in ["user", "assistant"]:
                    formatted_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                elif msg.role == "system":
                    formatted_messages.append({
                        "role": "system",
                        "content": msg.content
                    })
                elif msg.role == "tool":
                    formatted_messages.append({
                        "role": "tool",
                        "content": msg.content,
                        "name": msg.meta_data.get("tool_name") if msg.meta_data else "tool"
                    })

            return formatted_messages

        except SQLAlchemyError as e:
            logger.error(f"Error getting history for conversation {conversation_id}: {e}")
            raise

    @staticmethod
    async def get_token_count(text: str) -> int:
        """
        Estimate token count for a text string.
        This is an approximate method - Claude uses tokenization
        that splits text differently than simple whitespace.
        
        Args:
            text: The text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Very rough estimate: 1 token ~= 4 characters or 0.75 words
        char_estimate = len(text) / 4
        word_estimate = len(text.split()) * 0.75
        
        # Use the average of both methods
        return int((char_estimate + word_estimate) / 2)
    
    @staticmethod
    async def generate_conversation_summary(messages: List[Message], cutoff_index: int) -> Dict[str, str]:
        """
        Generate a summary of older conversation messages.
        
        Args:
            messages: List of messages to summarize
            cutoff_index: Index before which messages will be summarized
            
        Returns:
            A formatted system message with the summary
        """
        if cutoff_index <= 0:
            return None
            
        # Get messages to summarize
        messages_to_summarize = messages[:cutoff_index]
        
        # Group exchanges by date for better summarization
        from collections import defaultdict
        
        # Group by day
        exchanges_by_day = defaultdict(list)
        current_exchange = []
        current_user = None
        
        for msg in messages_to_summarize:
            # Format date as "YYYY-MM-DD"
            day_key = msg.timestamp.strftime("%Y-%m-%d") if msg.timestamp else "unknown"
            
            # Start a new exchange when user changes
            if msg.role == "user":
                if current_user != "user" and current_exchange:
                    exchanges_by_day[day_key].append(current_exchange)
                    current_exchange = []
                current_user = "user"
            elif msg.role == "assistant":
                if current_user != "assistant" and current_exchange:
                    exchanges_by_day[day_key].append(current_exchange)
                    current_exchange = []
                current_user = "assistant"
                
            # Add message to current exchange
            current_exchange.append(msg)
            
        # Add final exchange if not empty
        if current_exchange:
            day_key = current_exchange[0].timestamp.strftime("%Y-%m-%d") if current_exchange[0].timestamp else "unknown"
            exchanges_by_day[day_key].append(current_exchange)
            
        # Create summary
        summary_parts = ["**Earlier Conversation Summary:**"]
        
        for day, exchanges in sorted(exchanges_by_day.items()):
            # Add day header
            if day != "unknown":
                try:
                    date_obj = datetime.strptime(day, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%B %d, %Y")
                    summary_parts.append(f"\n**{formatted_date}:**")
                except:
                    summary_parts.append(f"\n**{day}:**")
            else:
                summary_parts.append("\n**Earlier:**")
                
            # Summarize each exchange
            for exchange in exchanges:
                user_msgs = [m for m in exchange if m.role == "user"]
                assistant_msgs = [m for m in exchange if m.role == "assistant"]
                
                if user_msgs:
                    # Summarize user questions
                    user_content = " ".join([m.content[:50] + "..." if len(m.content) > 50 else m.content for m in user_msgs])
                    summary_parts.append(f"- User asked about: {user_content}")
                
                if assistant_msgs:
                    # Summarize assistant responses
                    assistant_content = " ".join([m.content[:100] + "..." if len(m.content) > 100 else m.content for m in assistant_msgs])
                    summary_parts.append(f"- Assistant provided: {assistant_content}")
        
        summary = "\n".join(summary_parts)
        return {
            "role": "system",
            "content": summary
        }
    
    @staticmethod
    async def calculate_max_messages(
        all_messages: List[Message], 
        available_tokens: int = 12000,  # Claude 3 Sonnet has ~16K tokens, leave ~4K for responses
        token_buffer: int = 1000  # Safety buffer
    ) -> int:
        """
        Dynamically calculate max messages based on available tokens.
        
        Args:
            all_messages: All messages in conversation
            available_tokens: Token limit for context
            token_buffer: Safety buffer to leave space for response
            
        Returns:
            Recommended max messages to include
        """
        if not all_messages:
            return 15  # Default if no messages
            
        # Calculate average tokens per message
        total_tokens = 0
        for msg in all_messages:
            # Get token count for each message
            msg_tokens = await ConversationManager.get_token_count(msg.content)
            total_tokens += msg_tokens
        
        avg_tokens_per_message = max(1, total_tokens / len(all_messages))
        
        # Calculate how many messages we can fit
        usable_tokens = available_tokens - token_buffer
        max_messages = int(usable_tokens / avg_tokens_per_message)
        
        # Ensure reasonable limits
        return max(5, min(max_messages, 30))  # Between 5 and 30 messages
    
    @staticmethod
    async def get_channel_history_for_claude(
        db: Session, 
        user_id: str, 
        channel_id: str,
        thread_ts: Optional[str] = None,
        max_messages: Optional[int] = None  # Now optional since we'll calculate dynamically
    ) -> List[Dict[str, Any]]:
        """
        Return unified conversation history across threads and main channel for a user.
        
        Args:
            db: Database session
            user_id: The user ID
            channel_id: The channel ID
            thread_ts: Current thread timestamp (optional)
            max_messages: Maximum number of recent messages to include (optional, calculated if None)
            
        Returns:
            List of formatted messages for Claude
        """
        try:
            # Get all of user's active conversations in this channel
            conversations = db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.channel_id == channel_id,
                Conversation.is_active == True
            ).all()
            
            if not conversations:
                logger.info(f"No active conversations found for user {user_id} in channel {channel_id}")
                return []
            
            # Get all messages from these conversations
            all_messages = []
            for conversation in conversations:
                messages = await ConversationManager.get_conversation_messages(db, conversation.id)
                # Add conversation context to messages
                for msg in messages:
                    # Use setattr to safely add dynamic attributes
                    setattr(msg, 'thread_context', conversation.thread_ts or "main")
                    
                    # Add timestamp in human-readable format
                    if msg.timestamp:
                        time_format = "%Y-%m-%d %H:%M:%S"
                        setattr(msg, 'formatted_time', msg.timestamp.strftime(time_format))
                    else:
                        setattr(msg, 'formatted_time', "Unknown time")
                        
                all_messages.extend(messages)
            
            # Sort all messages by timestamp
            all_messages = sorted(all_messages, key=lambda m: (m.timestamp, m.platform_ts or ""))
            
            # Calculate dynamic max messages if not provided
            if max_messages is None:
                try:
                    max_messages = await ConversationManager.calculate_max_messages(all_messages)
                    logger.info(f"Dynamically calculated max_messages: {max_messages}")
                except Exception as e:
                    logger.error(f"Error calculating max messages: {e}")
                    max_messages = 15  # Fallback to default
            
            # Whether we need a summary of older messages
            summary_message = None
            messages_to_use = all_messages
            
            # If we have too many messages, prioritize and create summary
            if len(all_messages) > max_messages * 2:
                original_count = len(all_messages)
                
                # First pass: identify current thread messages if applicable
                if thread_ts:
                    thread_messages = [m for m in all_messages if getattr(m, 'thread_context', None) == thread_ts]
                    other_messages = [m for m in all_messages if getattr(m, 'thread_context', None) != thread_ts]
                    
                    # If thread has enough context, use just those messages
                    if len(thread_messages) >= 4:  # At least 2 exchanges
                        # Find a good cutoff point for thread messages (entire last exchanges)
                        preserve_count = min(len(thread_messages), max_messages)
                        preserved_messages = thread_messages[-preserve_count:]
                        remaining_slots = max_messages - len(preserved_messages)
                        
                        # Fill remaining slots with recent messages from other threads/main
                        if remaining_slots > 0 and other_messages:
                            messages_to_use = preserved_messages + other_messages[-remaining_slots:]
                        else:
                            messages_to_use = preserved_messages
                    else:
                        # Not enough thread context, just take the most recent overall
                        messages_to_use = all_messages[-max_messages * 2:]
                else:
                    # No thread context, just take most recent
                    messages_to_use = all_messages[-max_messages * 2:]
                
                # Generate summary of older messages if we excluded any
                if len(messages_to_use) < len(all_messages):
                    try:
                        cutoff_index = all_messages.index(messages_to_use[0]) if messages_to_use else len(all_messages)
                        summary_message = await ConversationManager.generate_conversation_summary(
                            all_messages, cutoff_index
                        )
                    except Exception as e:
                        logger.error(f"Error generating conversation summary: {e}")
                        # Create a simple summary instead
                        summary_message = {
                            "role": "system",
                            "content": f"**Note:** There are {len(all_messages) - len(messages_to_use)} older messages not shown in this history."
                        }
                
                logger.info(f"Truncated channel history from {original_count} to {len(messages_to_use)} messages")
            
            # Format messages for Claude
            formatted_messages = []
            
            # Add summary message first if available
            if summary_message:
                formatted_messages.append(summary_message)
            
            for msg in messages_to_use:
                # Include timestamp in content if available
                content_with_time = msg.content
                
                # Only add timestamps for messages older than 1 hour
                if hasattr(msg, 'formatted_time') and msg.timestamp:
                    # Calculate time ago
                    try:
                        # Get current time with timezone handling
                        # If timestamp has no timezone, use UTC
                        tz = msg.timestamp.tzinfo if msg.timestamp.tzinfo else None
                        now = datetime.now(tz)
                        time_diff = now - msg.timestamp
                        hours_ago = time_diff.total_seconds() / 3600
                    except Exception as e:
                        logger.error(f"Error calculating message age: {e}")
                        hours_ago = 0  # Default to recent message
                    
                    # Add timestamp for older messages
                    if hours_ago > 1:
                        # For privacy, only include date for messages older than 24 hours
                        if hours_ago > 24:
                            date_part = msg.timestamp.strftime("%b %d")
                            content_with_time = f"[{date_part}] {content_with_time}"
                        else:
                            time_part = msg.timestamp.strftime("%H:%M")
                            content_with_time = f"[{time_part}] {content_with_time}"
                
                if msg.role in ["user", "assistant"]:
                    formatted_messages.append({
                        "role": msg.role,
                        "content": content_with_time
                    })
                elif msg.role == "system":
                    formatted_messages.append({
                        "role": "system",
                        "content": content_with_time
                    })
                elif msg.role == "tool":
                    formatted_messages.append({
                        "role": "tool",
                        "content": content_with_time,
                        "name": msg.meta_data.get("tool_name") if msg.meta_data else "tool"
                    })
                    
            return formatted_messages
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting channel history: {e}")
            raise

    
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
            
    @staticmethod
    async def get_user_conversations(db: Session, user_id: str, limit: int = 10) -> List[Conversation]:
        """
        Get recent conversations for a specific user.
        
        Args:
            db: Database session
            user_id: The user ID
            limit: Maximum number of conversations to return
            
        Returns:
            List[Conversation]: List of conversations
        """
        try:
            return db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.updated_at.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversations for user {user_id}: {e}")
            raise e
            
    @staticmethod
    async def export_conversation_history(db: Session, conversation_id: str) -> Dict[str, Any]:
        """
        Export a conversation history to a structured format.
        
        Args:
            db: Database session
            conversation_id: The conversation ID
            
        Returns:
            Dict: Structured conversation data
        """
        try:
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conversation:
                return {"error": "Conversation not found"}
                
            messages = await ConversationManager.get_conversation_messages(db, conversation_id)
            
            # Format for easy import/export
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "message_type": msg.message_type,
                    "meta_data": msg.meta_data
                })
                
            return {
                "conversation_id": conversation.id,
                "user_id": conversation.user_id,
                "title": conversation.title,
                "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
                "channel_id": conversation.channel_id,
                "thread_ts": conversation.thread_ts,
                "messages": formatted_messages
            }
        except SQLAlchemyError as e:
            logger.error(f"Error exporting conversation {conversation_id}: {e}")
            raise e
            
    @staticmethod
    async def import_conversation_history(
        db: Session, 
        user_id: str, 
        conversation_data: Dict[str, Any],
        channel_id: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> Conversation:
        """
        Import a conversation history from a structured format.
        
        Args:
            db: Database session
            user_id: The user ID to associate with the imported conversation
            conversation_data: Structured conversation data
            channel_id: Optional new channel ID
            thread_ts: Optional new thread timestamp
            
        Returns:
            Conversation: The imported conversation
        """
        try:
            # Create new conversation
            new_conversation = Conversation(
                user_id=user_id,
                channel_id=channel_id or conversation_data.get("channel_id"),
                thread_ts=thread_ts or conversation_data.get("thread_ts"),
                title=conversation_data.get("title", "Imported Conversation"),
                meta_data={"imported": True, "original_id": conversation_data.get("conversation_id")}
            )
            db.add(new_conversation)
            db.flush()  # Get ID without committing
            
            # Import messages
            for msg_data in conversation_data.get("messages", []):
                message = Message(
                    conversation_id=new_conversation.id,
                    role=msg_data.get("role"),
                    content=msg_data.get("content"),
                    message_type=msg_data.get("message_type", "text"),
                    meta_data=msg_data.get("meta_data")
                )
                db.add(message)
                
            db.commit()
            db.refresh(new_conversation)
            return new_conversation
            
        except SQLAlchemyError as e:
            logger.error(f"Error importing conversation: {e}")
            db.rollback()
            raise e
            
    @staticmethod
    async def get_user_conversation_by_title(db: Session, user_id: str, title: str) -> Optional[Conversation]:
        """
        Find a user's conversation by title.
        
        Args:
            db: Database session
            user_id: The user ID
            title: The conversation title to search for
            
        Returns:
            Optional[Conversation]: The conversation if found
        """
        try:
            return db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.title.ilike(f"%{title}%")
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding conversation by title for user {user_id}: {e}")
            raise e
            
    @staticmethod
    async def attach_history_to_conversation(
        db: Session,
        target_conversation_id: str,
        source_conversation_id: str,
        max_messages: int = 20
    ) -> bool:
        """
        Attach history from one conversation to another as context messages.
        
        Args:
            db: Database session
            target_conversation_id: Target conversation ID
            source_conversation_id: Source conversation ID for history
            max_messages: Maximum messages to include from history
            
        Returns:
            bool: Success status
        """
        try:
            # Get source messages
            source_messages = await ConversationManager.get_conversation_messages(db, source_conversation_id)
            if len(source_messages) > max_messages:
                source_messages = source_messages[-max_messages:]  # Get only the most recent messages
                
            # Get target conversation
            target_conversation = db.query(Conversation).filter(Conversation.id == target_conversation_id).first()
            if not target_conversation:
                return False
                
            # Add meta_data to target conversation to indicate it has attached history
            if not target_conversation.meta_data:
                target_conversation.meta_data = {}
            
            if "attached_histories" not in target_conversation.meta_data:
                target_conversation.meta_data["attached_histories"] = []
                
            target_conversation.meta_data["attached_histories"].append(source_conversation_id)
            
            # Add source messages to target conversation with special metadata
            for msg in source_messages:
                # Create a new message in target conversation
                history_msg = Message(
                    conversation_id=target_conversation_id,
                    role=msg.role,
                    content=msg.content,
                    message_type=msg.message_type,
                    meta_data={
                        "from_history": True,
                        "original_message_id": msg.id,
                        "original_conversation_id": source_conversation_id
                    }
                )
                db.add(history_msg)
                
            db.commit()
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Error attaching history: {e}")
            db.rollback()
            raise e