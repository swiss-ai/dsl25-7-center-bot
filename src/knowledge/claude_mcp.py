import anthropic
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.knowledge.knowledge_retriever import KnowledgeRetriever

logger = setup_logger(__name__)

class ClaudeClient:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.knowledge_retriever = KnowledgeRetriever()
        
    async def get_response(self, message: str, context: str = None) -> str:
        """Get a response from Claude for the given message"""
        try:
            # Search knowledge base for relevant information
            knowledge_results = self.knowledge_retriever.search(message, n_results=3)
            knowledge_context = self.knowledge_retriever.format_search_results_for_context(knowledge_results)
            
            system_prompt = """You are a helpful Slack bot assistant with access to a knowledge base and conversation history.

When responding:
- Be conversational and friendly
- Use the conversation context to provide relevant responses
- When using information from the knowledge base, cite your sources
- If information comes from Notion, mention the page title and provide the URL if available
- For Airtable data:
  - Always prioritize results marked as "(Live Data)" over "(Cached)" results
  - If you see duplicate information between Live and Cached results, only mention it once using the Live Data version
  - Mention if data is from live search vs cached to indicate freshness
- Remember what was discussed earlier in the conversation
- Keep responses concise but helpful
- If you're not sure about something, say so rather than making things up"""

            # Add conversation context if provided
            if context:
                system_prompt += f"\n\nConversation History:\n{context}"
            
            # Add knowledge base context if found
            if knowledge_context:
                system_prompt += f"\n\n{knowledge_context}"
            
            logger.debug(f"Sending request to Claude: {message}")
            if knowledge_context:
                logger.debug(f"With knowledge context from {len(knowledge_results)} sources")
            
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": message}
                ]
            )
            
            result = response.content[0].text
            logger.debug(f"Claude response: {result[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error getting Claude response: {e}")
            return "Sorry, I encountered an error while processing your request."