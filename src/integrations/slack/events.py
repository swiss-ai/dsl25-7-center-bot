from slack_bolt.async_app import AsyncApp
from src.knowledge.claude_mcp import ClaudeClient
from src.response.context import ConversationHistory
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class EventHandlers:
    def __init__(self):
        self.claude_client = ClaudeClient()
        self.conversation_history = ConversationHistory()
        
    def register_handlers(self, app: AsyncApp):
        """Register all event handlers with the Slack app"""
        
        # Handle app mentions
        @app.event("app_mention")
        async def handle_app_mention(event, say, client):
            await self._handle_mention(event, say, client)
            
        # Handle all messages (for context tracking)
        @app.event("message")
        async def handle_message(event, say, client):
            # Track all messages for context
            await self._track_message(event, client)
            
            # Only respond to DMs (no channel_type means it's a DM)
            if event.get("channel_type") not in ["channel", "group"]:
                await self._handle_dm(event, say, client)
    
    async def _track_message(self, event, client):
        """Track all messages for conversation history"""
        try:
            # Skip bot messages
            if event.get("bot_id"):
                return
                
            channel = event.get("channel")
            user = event.get("user")
            text = event.get("text", "")
            timestamp = event.get("ts")
            
            # Get user's display name for better context
            try:
                user_info = await client.users_info(user=user)
                username = user_info["user"]["profile"].get("display_name") or user_info["user"]["name"]
            except:
                username = f"User_{user}"
            
            # Add to conversation history
            self.conversation_history.add_message(channel, username, text, timestamp)
            
        except Exception as e:
            logger.error(f"Error tracking message: {e}")
    
    async def _handle_mention(self, event, say, client):
        """Handle when the bot is mentioned"""
        try:
            channel = event.get("channel")
            user = event.get("user")
            text = event.get("text", "")
            
            # Remove the bot mention from the text
            import re
            clean_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
            
            logger.info(f"Handling mention from user {user}: {clean_text}")
            
            # Get conversation context
            context = self.conversation_history.format_context_for_claude(channel)
            
            # Get response from Claude with context
            response = await self.claude_client.get_response(clean_text, context)
            
            logger.info(f"Sending response: {response[:100]}...")
            
            # Send the response
            await say(response)
            
            # Add bot's response to history
            self.conversation_history.add_message(channel, "Assistant", response)
            
            logger.info("Response sent successfully")
            
        except Exception as e:
            logger.error(f"Error handling mention: {e}")
            await say("Sorry, I encountered an error processing your request.")
    
    async def _handle_dm(self, event, say, client):
        """Handle direct messages to the bot"""
        try:
            # Skip bot's own messages
            if event.get("bot_id"):
                return
                
            channel = event.get("channel")
            user = event.get("user")
            text = event.get("text", "")
            
            logger.info(f"Handling DM from user {user}: {text}")
            
            # Get conversation context (DMs also maintain history)
            context = self.conversation_history.format_context_for_claude(channel)
            
            # Get response from Claude with context
            response = await self.claude_client.get_response(text, context)
            
            # Send the response
            await say(response)
            
            # Add bot's response to history
            self.conversation_history.add_message(channel, "Assistant", response)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await say("Sorry, I encountered an error processing your request.")