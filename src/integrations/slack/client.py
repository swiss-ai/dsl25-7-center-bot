from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from src.utils.config import Config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class SlackClient:
    def __init__(self):
        self.app = AsyncApp(
            token=Config.SLACK_BOT_TOKEN,
            signing_secret=Config.SLACK_SIGNING_SECRET
        )
        
        self.socket_handler = AsyncSocketModeHandler(
            self.app,
            Config.SLACK_APP_TOKEN
        )
        
    async def start(self):
        """Start the Socket Mode handler"""
        await self.socket_handler.start_async()
        
    def get_app(self):
        """Get the Slack app instance"""
        return self.app