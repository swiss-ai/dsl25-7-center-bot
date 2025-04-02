import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def format_slack_message(text: str, blocks: Optional[list] = None) -> Dict[str, Any]:
    """
    Format a message for Slack with optional blocks.
    
    Args:
        text: The text of the message
        blocks: Optional blocks for advanced formatting
        
    Returns:
        Dict containing the formatted message
    """
    message = {"text": text}
    
    if blocks:
        message["blocks"] = blocks
    
    return message

def safe_parse_json(text: str) -> Dict[str, Any]:
    """
    Safely parse JSON, returning an empty dict on failure.
    
    Args:
        text: The JSON string to parse
        
    Returns:
        The parsed JSON as a dict, or an empty dict on failure
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return {}