from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ConversationHistory:
    def __init__(self, max_messages_per_channel: int = 100, max_age_hours: int = 24):
        """
        Initialize conversation history tracker
        
        Args:
            max_messages_per_channel: Maximum messages to keep per channel
            max_age_hours: Maximum age of messages to keep (in hours)
        """
        self.max_messages = max_messages_per_channel
        self.max_age = timedelta(hours=max_age_hours)
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_channel))
        
    def add_message(self, channel: str, user: str, text: str, timestamp: str = None):
        """Add a message to the conversation history"""
        message = {
            'user': user,
            'text': text,
            'timestamp': timestamp or datetime.now().isoformat(),
            'datetime': datetime.now()
        }
        self.history[channel].append(message)
        logger.debug(f"Added message to channel {channel}: {text[:50]}...")
        
    def get_context(self, channel: str, num_messages: int = 20) -> List[Dict]:
        """
        Get recent conversation context for a channel
        
        Args:
            channel: Channel ID
            num_messages: Number of recent messages to return
            
        Returns:
            List of recent messages
        """
        if channel not in self.history:
            return []
            
        # Filter out old messages
        now = datetime.now()
        recent_messages = [
            msg for msg in self.history[channel]
            if now - msg['datetime'] <= self.max_age
        ]
        
        # Update the deque with only recent messages
        self.history[channel] = deque(recent_messages, maxlen=self.max_messages)
        
        # Return the most recent messages
        return list(self.history[channel])[-num_messages:]
    
    def format_context_for_claude(self, channel: str, num_messages: int = 20) -> str:
        """Format conversation history as context for Claude"""
        messages = self.get_context(channel, num_messages)
        
        if not messages:
            return ""
            
        context_lines = ["Recent conversation history:"]
        for msg in messages:
            # Format: "User123: Hello everyone"
            context_lines.append(f"{msg['user']}: {msg['text']}")
            
        return "\n".join(context_lines)
    
    def clear_channel(self, channel: str):
        """Clear history for a specific channel"""
        if channel in self.history:
            del self.history[channel]
            logger.info(f"Cleared history for channel {channel}")