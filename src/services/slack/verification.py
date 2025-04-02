import hmac
import hashlib
import time
from fastapi import Request
from dotenv import load_dotenv
import os

load_dotenv()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

async def verify_slack_request(request: Request) -> bool:
    """
    Verify that incoming requests are from Slack using their signing secret.
    
    Args:
        request: The incoming FastAPI request
        
    Returns:
        bool: True if the request is verified, False otherwise
    """
    if SLACK_SIGNING_SECRET is None:
        raise ValueError("SLACK_SIGNING_SECRET environment variable is not set")
    
    # Get Slack signature and timestamp
    slack_signature = request.headers.get("X-Slack-Signature", "")
    slack_timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    
    # Check if timestamp is too old (prevent replay attacks)
    if abs(time.time() - float(slack_timestamp)) > 60 * 5:
        return False
    
    # Get request body as bytes
    body = await request.body()
    
    # Create the base string (timestamp:body)
    base_string = f"v0:{slack_timestamp}:{body.decode('utf-8')}"
    
    # Create the signature using HMAC SHA256
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        base_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures using constant time comparison
    return hmac.compare_digest(my_signature, slack_signature)