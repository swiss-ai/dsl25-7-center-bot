import logging
from sqlalchemy.exc import SQLAlchemyError
from models.base import init_db as base_init_db
from models.base import SessionLocal
from models.conversation import User, Conversation, Message, ToolCall

logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database."""
    try:
        # Create tables
        base_init_db()
        logger.info("Database initialized successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error initializing database: {e}")
        raise e

def create_test_data():
    """Create test data for development."""
    logger.info("Creating test data...")
    db = SessionLocal()
    
    try:
        # Create test user
        test_user = User(
            platform_id="U12345",
            platform="slack",
            name="Test User"
        )
        db.add(test_user)
        db.flush()  # To get the ID
        
        # Create test conversation
        test_conversation = Conversation(
            user_id=test_user.id,
            channel_id="C12345",
            title="Test Conversation"
        )
        db.add(test_conversation)
        db.flush()  # To get the ID
        
        # Add some test messages
        messages = [
            Message(
                conversation_id=test_conversation.id,
                role="user",
                content="Hello, bot!"
            ),
            Message(
                conversation_id=test_conversation.id,
                role="assistant",
                content="Hello! How can I help you today?"
            ),
            Message(
                conversation_id=test_conversation.id,
                role="user",
                content="Can you search for information about AI?"
            ),
            Message(
                conversation_id=test_conversation.id,
                role="assistant",
                content="I'll search for information about AI.",
                message_type="tool_call"
            )
        ]
        db.add_all(messages)
        db.flush()
        
        # Add a tool call
        tool_call = ToolCall(
            message_id=messages[3].id,
            tool_name="search",
            input_parameters={"query": "AI", "source": "all"},
            output_result={"results": ["Sample AI information"]},
            status="success"
        )
        db.add(tool_call)
        
        # Commit all changes
        db.commit()
        logger.info("Test data created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error creating test data: {e}")
        db.rollback()
    finally:
        db.close()