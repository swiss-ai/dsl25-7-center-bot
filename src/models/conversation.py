from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from .base import Base

def generate_uuid():
    """Generate a UUID for IDs."""
    return str(uuid.uuid4())

class User(Base):
    """User model representing Slack users or other platform users."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    platform_id = Column(String(50), unique=True, nullable=False, index=True)  # Slack user ID
    platform = Column(String(20), nullable=False, default="slack")  # Platform: slack, web, etc.
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.name} ({self.platform_id})>"

class Conversation(Base):
    """Model representing a conversation session."""
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    channel_id = Column(String(50), nullable=False)  # Slack channel ID
    thread_ts = Column(String(50), nullable=True)  # Slack thread timestamp
    title = Column(String(255), nullable=True)  # Generated title for the conversation
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSON, nullable=True)  # Additional metadata
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.timestamp")
    
    def __repr__(self):
        return f"<Conversation {self.id} ({self.channel_id})>"

class Message(Base):
    """Model representing a message in a conversation."""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    platform_ts = Column(String(50), nullable=True)  # Slack message timestamp
    message_type = Column(String(20), default="text")  # text, tool_call, tool_result
    meta_data = Column(JSON, nullable=True)  # Additional metadata like tools used
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    tool_calls = relationship("ToolCall", back_populates="message")
    
    def __repr__(self):
        return f"<Message {self.id} ({self.role})>"

class ToolCall(Base):
    """Model representing a tool call in a message."""
    __tablename__ = "tool_calls"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=False)
    tool_name = Column(String(100), nullable=False)
    input_parameters = Column(JSON, nullable=False)  # Input parameters
    output_result = Column(JSON, nullable=True)  # Output result
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="pending")  # pending, success, error
    error_message = Column(Text, nullable=True)
    
    # Relationships
    message = relationship("Message", back_populates="tool_calls")
    
    def __repr__(self):
        return f"<ToolCall {self.id} ({self.tool_name})>"