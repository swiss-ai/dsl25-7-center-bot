import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Literal
from dotenv import load_dotenv
from anthropic import Anthropic, AsyncAnthropic

load_dotenv()

CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=CLAUDE_API_KEY)
async_anthropic_client = AsyncAnthropic(api_key=CLAUDE_API_KEY)
logger = logging.getLogger(__name__)

# Base prompt to instruct Claude on its role
SYSTEM_PROMPT = """
You are an AI assistant integrated with Slack. Your role is to help users by answering questions
using ONLY information from the connected knowledge sources. You have access to various data sources 
through MCP tools and must use these tools to find information.

IMPORTANT RESTRICTIONS:
1. You MUST NEVER use information outside of what's available in the knowledge sources
2. If the information is not in the knowledge base, Google Drive, or fetched web content, say that you don't have that information
3. DO NOT use your general knowledge to answer questions - only use the search and file access tools
4. You MUST cite the source of all information you provide (file name, search result, URL, etc.)

DATA SOURCES YOU CAN ACCESS:
1. Knowledge Base - Vector database with previously stored information
2. Google Drive - Access to shared documents, spreadsheets, and PDFs
3. Web Content - URLs that have been fetched and added to the knowledge base

WEB CONTENT TOOLS:
- web_fetch: Add a URL to the knowledge base - use this to retrieve information from websites
- web_fetch_multiple: Add multiple URLs to the knowledge base in a single operation
- web_search: Search previously fetched web content for specific information

SPECIAL HANDLING FOR WEB CONTENT:
- When the user asks about web content that might not be in your knowledge base, suggest using the web_fetch tool
- When fetching web content, always provide clear citations including the URL source
- For questions about fetched web content, use web_search to find the relevant information

SPECIAL HANDLING FOR PDF FILES:
- When users ask about PDF files, ALWAYS search Google Drive with the gdrive_search tool 
- If you find a relevant PDF, use gdrive_get_file to get more details about it
- For PDF content questions, instruct the user to ask specifically about that PDF by name
- You can process and provide information about PDFs in Google Drive when directly asked

When responding:
1. Be concise, clear, and focused on information from the knowledge sources
2. Always use tools to search for information before attempting to answer
3. Format your responses appropriately for Slack (using markdown)
4. Always cite your sources when providing information
5. If the search returns no results, clearly state that the information is not available in the knowledge base
6. DO NOT make up information or use your general knowledge
"""

# Define the MCP Tool schema structure
class MCPToolParameter:
    """Schema for an MCP tool parameter."""
    def __init__(
        self, 
        name: str, 
        description: str, 
        type: str,
        required: bool = False,
        enum: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.type = type
        self.required = required
        self.enum = enum
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to the format expected by Claude MCP."""
        param_dict = {
            "description": self.description,
            "type": self.type
        }
        if self.enum:
            param_dict["enum"] = self.enum
        return param_dict

class MCPTool:
    """Schema for an MCP tool definition."""
    def __init__(
        self, 
        name: str, 
        description: str, 
        parameters: Optional[List[MCPToolParameter]] = None
    ):
        self.name = name
        self.description = description
        self.parameters = parameters or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to the format expected by Claude MCP."""
        # Create properties dict in the correct format
        properties = {}
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            # Add enum if available
            if param.enum:
                properties[param.name]["enum"] = param.enum
        
        return {
            "type": "custom",
            "input_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": properties,
                "required": [p.name for p in self.parameters if p.required]
            },
            "name": self.name,
            "description": self.description
        }

# Define some basic tools
SEARCH_TOOL = MCPTool(
    name="search",
    description="Search for information across all available knowledge sources",
    parameters=[
        MCPToolParameter(
            name="query",
            description="The search query",
            type="string",
            required=True
        ),
        MCPToolParameter(
            name="source",
            description="The specific source to search in",
            type="string",
            required=False,
            enum=["all", "slack", "drive", "notion", "web"]
        )
    ]
)

FETCH_DOCUMENT_TOOL = MCPTool(
    name="fetch_document",
    description="Fetch a specific document by ID",
    parameters=[
        MCPToolParameter(
            name="document_id",
            description="The ID of the document to fetch",
            type="string",
            required=True
        ),
        MCPToolParameter(
            name="source",
            description="The source system",
            type="string",
            required=True,
            enum=["drive", "notion", "slack", "wiki", "web"]
        )
    ]
)

DEFAULT_TOOLS = [SEARCH_TOOL, FETCH_DOCUMENT_TOOL]

# Import Google Drive tools
try:
    from services.mcp.gdrive import GDRIVE_TOOLS
    DEFAULT_TOOLS.extend(GDRIVE_TOOLS)
except ImportError:
    pass

# Import Web tools
try:
    from services.mcp.web_tools import WEB_TOOLS
    DEFAULT_TOOLS.extend(WEB_TOOLS)
except ImportError:
    pass

class ClaudeMCPRequestFormatter:
    """Helper class to format Claude MCP requests."""
    
    @staticmethod
    def format_user_message(content: str) -> Dict[str, Any]:
        """Format a user message for Claude."""
        return {"role": "user", "content": content}
    
    @staticmethod
    def format_assistant_message(content: str) -> Dict[str, Any]:
        """Format an assistant message for Claude."""
        return {"role": "assistant", "content": [{"type": "text", "text": content}]}
    
    @staticmethod
    def format_tool_result(tool_name: str, content: str) -> Dict[str, Any]:
        """Format a tool result for Claude."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_name,
                    "content": content
                }
            ]
        }
    
    @staticmethod
    def format_full_request(
        messages: List[Dict[str, Any]],
        system: str = SYSTEM_PROMPT,
        tools: List[MCPTool] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: str = "claude-3-opus-20240229"
    ) -> Dict[str, Any]:
        """Format a complete request for Claude API."""
        request_data = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages
        }
        
        if tools:
            request_data["tools"] = [tool.to_dict() for tool in tools]
        
        return request_data

class ToolExecution:
    """Handler for tool execution."""
    
    @staticmethod
    async def execute_search(
        query: str, 
        source: str = "all", 
        document_processor=None,
        gdrive_mcp=None,
        web_content_manager=None
    ) -> str:
        """
        Execute a search across knowledge sources.
        
        Args:
            query: The search query
            source: The source to search in
            document_processor: Document processor instance (optional)
            gdrive_mcp: Google Drive MCP instance (optional)
            web_content_manager: Web Content Manager instance (optional)
            
        Returns:
            Search results as text
        """
        logger.info(f"Searching for '{query}' in source: {source}")
        
        combined_results = []
        
        # First check in the vector database (knowledge base)
        kb_results = "No results found in the knowledge base."
        if document_processor:
            try:
                # Build filter criteria based on source
                filter_criteria = None
                if source != "all" and source != "drive" and source != "web":
                    filter_criteria = {"source": source}
                
                # Perform the search using the document processor
                results = await document_processor.search_documents(
                    query=query,
                    n_results=3,
                    filter_criteria=filter_criteria
                )
                
                # Format the results as text
                kb_results = document_processor.format_search_results(results)
                if kb_results != "No results found.":
                    combined_results.append("## Knowledge Base Results\n" + kb_results)
            except Exception as e:
                logger.error(f"Error searching vector database: {e}")
                kb_results = f"Error searching knowledge base: {str(e)}"
                combined_results.append("## Knowledge Base Results\n" + kb_results)
        
        # Then search Google Drive directly if it's available (commented out)
        """
        gdrive_results = "No results found in Google Drive."
        if gdrive_mcp and (source == "all" or source == "drive"):
            try:
                # Use Google Drive search directly
                from services.mcp.gdrive import execute_gdrive_tool
                gdrive_results = await execute_gdrive_tool(
                    "gdrive_search", 
                    {"query": query, "max_results": 3}, 
                    gdrive_mcp
                )
                combined_results.append("## Google Drive Results\n" + gdrive_results)
            except Exception as e:
                logger.error(f"Error searching Google Drive: {e}")
                gdrive_results = f"Error searching Google Drive: {str(e)}"
                combined_results.append("## Google Drive Results\n" + gdrive_results)
        """
        
        # Also search web content if it's available
        web_results = "No results found in web content."
        if web_content_manager and (source == "all" or source == "web"):
            try:
                # Search web content specifically
                web_results = await web_content_manager.search_web_content(query, 3)
                if web_results and "No results found" not in web_results:
                    combined_results.append("## Web Content Results\n" + web_results)
            except Exception as e:
                logger.error(f"Error searching web content: {e}")
                web_results = f"Error searching web content: {str(e)}"
                combined_results.append("## Web Content Results\n" + web_results)
        
        # If no results at all
        if not combined_results:
            return f"No search results found for '{query}' in any sources."
        
        # Combine the results
        return "\n\n".join(combined_results)
    
    @staticmethod
    async def execute_fetch_document(
        document_id: str, 
        source: str, 
        document_processor=None,
        gdrive_mcp=None,
        web_content_manager=None
    ) -> str:
        """
        Fetch a document from a specific source.
        
        Args:
            document_id: The document ID
            source: The source system
            document_processor: Document processor instance (optional)
            gdrive_mcp: Google Drive MCP instance (optional)
            web_content_manager: Web Content Manager instance (optional)
            
        Returns:
            Document content
        """
        logger.info(f"Fetching document {document_id} from {source}")
        
        # Handle Google Drive documents (commented out)
        """
        if source == "drive" and gdrive_mcp:
            from services.mcp.gdrive import execute_gdrive_tool
            return await execute_gdrive_tool(
                "gdrive_get_file", 
                {"file_id": document_id}, 
                gdrive_mcp
            )
        """
        
        # Handle web source documents (using same vector DB infrastructure)
        if source == "web":
            # Default to vector database retrieval for web content
            if not document_processor:
                return f"Document {document_id} from {source}:\n- Document processor not initialized."
            
            try:
                # Use the vector database to search for the document by ID
                if not document_processor.vector_db:
                    return f"Document {document_id} from {source}:\n- Vector database not initialized."
                
                # Try to get the document from the vector database with web source filter
                result = document_processor.vector_db.get(
                    ids=[document_id],
                    where={"source": "web"}
                )
                
                if not result or not result.get("documents") or not result["documents"]:
                    return f"Web document {document_id} not found."
                
                # Format the result
                content = result["documents"][0]
                metadata = result["metadatas"][0] if "metadatas" in result else {}
                
                title = metadata.get("title", "Untitled")
                url = metadata.get("url", "Unknown URL")
                created_at = metadata.get("created_at", "Unknown date")
                
                header = f"# {title}\n\nURL: {url}\nDate: {created_at}\nSource: Web Content\n\n"
                
                return header + content
                
            except Exception as e:
                logger.error(f"Error fetching web document: {e}")
                return f"Error fetching web document {document_id}: {str(e)}"
        
        # Default to vector database retrieval for other sources
        if not document_processor:
            return f"Document {document_id} from {source}:\n- Document processor not initialized."
        
        try:
            # For now, use the vector database to search for the document by ID
            if not document_processor.vector_db:
                return f"Document {document_id} from {source}:\n- Vector database not initialized."
            
            # Try to get the document from the vector database
            result = document_processor.vector_db.get(ids=[document_id])
            
            if not result or not result.get("documents") or not result["documents"]:
                return f"Document {document_id} not found in {source}."
            
            # Format the result
            content = result["documents"][0]
            metadata = result["metadatas"][0] if "metadatas" in result else {}
            
            title = metadata.get("title", "Untitled")
            author = metadata.get("author", "Unknown")
            created_at = metadata.get("created_at", "Unknown date")
            
            header = f"# {title}\n\nAuthor: {author}\nDate: {created_at}\nSource: {source}\n\n"
            
            return header + content
        
        except Exception as e:
            logger.error(f"Error fetching document: {e}")
            return f"Error fetching document {document_id}: {str(e)}"
    
    @staticmethod
    async def execute_tool(
        tool_name: str, 
        parameters: Dict[str, Any], 
        document_processor=None,
        gdrive_mcp=None,
        web_content_manager=None
    ) -> str:
        """
        Execute a tool based on name and parameters.
        
        Args:
            tool_name: The name of the tool to execute
            parameters: Dictionary of parameters for the tool
            document_processor: Document processor instance (optional)
            gdrive_mcp: Google Drive MCP instance (optional)
            
        Returns:
            str: The result of the tool execution
        """
        try:
            # Handle standard knowledge tools
            if tool_name == "search":
                query = parameters.get("query", "")
                source = parameters.get("source", "all")
                return await ToolExecution.execute_search(query, source, document_processor, gdrive_mcp, web_content_manager)
            
            elif tool_name == "fetch_document":
                document_id = parameters.get("document_id", "")
                source = parameters.get("source", "")
                return await ToolExecution.execute_fetch_document(document_id, source, document_processor, gdrive_mcp, web_content_manager)
            
            # Handle Google Drive tools
            elif tool_name.startswith("gdrive_") and gdrive_mcp:
                from services.mcp.gdrive import execute_gdrive_tool
                return await execute_gdrive_tool(tool_name, parameters, gdrive_mcp)
            
            # Handle Web tools
            elif tool_name.startswith("web_"):
                from services.mcp.web_tools import execute_web_tool
                from services.knowledge.datasources.web_content import WebContentManager
                
                # Create web content manager if needed
                web_content_manager = WebContentManager(document_processor=document_processor)
                return await execute_web_tool(tool_name, parameters, web_content_manager)
            
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return f"Error executing tool {tool_name}: {str(e)}"

async def process_with_claude(user_message: str) -> str:
    """
    Process a user message with Claude using the MCP protocol.
    
    Args:
        user_message: The user's message text
        
    Returns:
        str: Claude's response text
    """
    try:
        # For Phase 1+, we'll use a simple version of the MCP protocol
        # Later phases will implement the full MCP protocol with tool execution
        
        response = await async_anthropic_client.messages.create(
            model="claude-3-opus-20240229",  # Use appropriate model
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )
        
        return response.content[0].text
        
    except Exception as e:
        logger.error(f"Error in Claude processing: {e}")
        return f"I'm having trouble processing your request. Please try again later."

async def claude_mcp_request(
    user_message: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    tools: Optional[List[MCPTool]] = None,
    enable_tool_use: bool = False,
    document_processor=None,
    gdrive_mcp=None,
    web_content_manager=None
) -> Dict[str, Any]:
    """
    Make a request to Claude using the MCP protocol with optional tools.
    
    Args:
        user_message: The user's message
        conversation_history: List of previous messages
        tools: List of tool definitions to include
        enable_tool_use: Whether to allow Claude to use tools
        document_processor: Document processor instance (optional)
        gdrive_mcp: Google Drive MCP instance (optional)
        
    Returns:
        Claude's response including any tool calls
    """
    formatter = ClaudeMCPRequestFormatter()
    
    # Build the messages array with conversation history
    messages = conversation_history or []
    messages.append(formatter.format_user_message(user_message))
    
    # Use default tools if none specified
    tools_to_use = tools or DEFAULT_TOOLS if enable_tool_use else None
    
    try:
        # Create request to Claude
        request_data = formatter.format_full_request(
            messages=messages,
            tools=tools_to_use,
            model="claude-3-5-sonnet-20240620"
        )
        
        # Make the API call
        response = await async_anthropic_client.messages.create(**request_data)
        
        # Process tool calls if they exist
        has_tool_use = False
        tool_uses = []
        
        # First collect all tool uses
        for content_block in response.content:
            if content_block.type == "tool_use":
                has_tool_use = True
                tool_uses.append({
                    "id": content_block.id,
                    "name": content_block.name,
                    "input": content_block.input
                })
                
        if enable_tool_use and has_tool_use:
            # First add the assistant response with tool use
            messages.append({
                "role": "assistant",
                "content": response.content
            })
            
            # Then execute each tool and add results
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_parameters = tool_use["input"]
                tool_id = tool_use["id"]
                
                # Execute the tool
                tool_result = await ToolExecution.execute_tool(
                    tool_name, 
                    tool_parameters,
                    document_processor,
                    gdrive_mcp,
                    web_content_manager
                )
                
                # Add tool result to messages
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": tool_result
                        }
                    ]
                })
            
            # Get final response from Claude with tool results
            final_request = formatter.format_full_request(
                messages=messages,
                tools=tools_to_use,
                model="claude-3-5-sonnet-20240620"
            )
            final_response = await async_anthropic_client.messages.create(**final_request)
            return final_response
        
        return response
        
    except Exception as e:
        logger.error(f"Error in Claude MCP request: {e}")
        error_response = {
            "error": str(e),
            "content": [{"type": "text", "text": "I'm having trouble processing your request."}]
        }
        return error_response

async def get_claude_response_text(response: Dict[str, Any]) -> str:
    """
    Extract text content from Claude response.
    
    Args:
        response: Claude API response
        
    Returns:
        str: The response text
    """
    try:
        if hasattr(response, 'content') and response.content:
            text_blocks = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_blocks)
        elif isinstance(response, dict) and "content" in response:
            if isinstance(response["content"], list):
                text_blocks = [block.get("text", "") for block in response["content"] 
                              if block.get("type") == "text"]
                return "\n".join(text_blocks)
        return "Sorry, I couldn't generate a proper response."
    except Exception as e:
        logger.error(f"Error extracting text from Claude response: {e}")
        return "Sorry, I encountered an error processing the response."