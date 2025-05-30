import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_slack_client():
    """Mock Slack client for testing"""
    client = Mock()
    client.chat_postMessage = AsyncMock()
    return client

@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB client for testing"""
    client = Mock()
    client.list_collections = Mock(return_value=[])
    return client

@pytest.fixture
def sample_slack_event():
    """Sample Slack event for testing"""
    return {
        "type": "message",
        "channel": "C1234567890",
        "user": "U1234567890",
        "text": "Test message",
        "ts": "1234567890.123456"
    }