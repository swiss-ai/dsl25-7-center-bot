import asyncio
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.integrations.slack.client import SlackClient
from src.integrations.slack.events import EventHandlers
from src.knowledge.sync_manager import KnowledgeSyncManager

logger = setup_logger(__name__)

async def main():
    """Main entry point for the Slack bot"""
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validated successfully")
        
        # Initialize knowledge sync manager
        sync_manager = KnowledgeSyncManager()
        
        # Perform initial sync
        logger.info("Performing initial knowledge sync...")
        await sync_manager.initial_sync()
        
        # Start periodic sync
        sync_manager.start_periodic_sync()
        logger.info("Started periodic knowledge sync")
        
        # Initialize Slack client
        slack_client = SlackClient()
        app = slack_client.get_app()
        
        # Register event handlers
        event_handlers = EventHandlers()
        event_handlers.register_handlers(app)
        
        logger.info("Starting Slack bot...")
        
        # Start the bot
        await slack_client.start()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())