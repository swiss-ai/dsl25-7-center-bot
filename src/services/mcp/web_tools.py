import logging
from typing import Dict, List, Any, Optional

from services.mcp.claude import MCPTool, MCPToolParameter
from services.knowledge.datasources.web_content import WebContentManager

logger = logging.getLogger(__name__)

# Define MCP tools for web content management
WEB_FETCH_TOOL = MCPTool(
    name="web_fetch",
    description="Fetch content from a URL and add it to the knowledge base",
    parameters=[
        MCPToolParameter(
            name="url",
            description="The URL to fetch and store in the knowledge base",
            type="string",
            required=True
        )
    ]
)

WEB_FETCH_MULTIPLE_TOOL = MCPTool(
    name="web_fetch_multiple",
    description="Fetch content from multiple URLs and add them to the knowledge base",
    parameters=[
        MCPToolParameter(
            name="urls",
            description="List of URLs to fetch and store",
            type="array",
            required=True
        )
    ]
)

WEB_SEARCH_TOOL = MCPTool(
    name="web_search",
    description="Search for information in previously fetched web content",
    parameters=[
        MCPToolParameter(
            name="query",
            description="The search query for web content",
            type="string",
            required=True
        ),
        MCPToolParameter(
            name="max_results",
            description="Maximum number of results to return (default: 3)",
            type="integer",
            required=False
        )
    ]
)

# Combine all tools into a single list
WEB_TOOLS = [
    WEB_FETCH_TOOL,
    WEB_FETCH_MULTIPLE_TOOL,
    WEB_SEARCH_TOOL
]

# Function to execute web tools
async def execute_web_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    web_content_manager: Optional[WebContentManager] = None
) -> str:
    """
    Execute a web tool based on the tool name and parameters.
    
    Args:
        tool_name: The name of the tool to execute
        parameters: The tool parameters
        web_content_manager: WebContentManager instance
    
    Returns:
        Result of the tool execution as a string
    """
    if not web_content_manager:
        return "Web content management not available: WebContentManager not initialized"
    
    try:
        # Handle web_fetch tool
        if tool_name == "web_fetch":
            url = parameters.get("url")
            if not url:
                return "Error: URL parameter is required"
            
            result = await web_content_manager.add_url_to_knowledge_base(url)
            
            if result["status"] == "success":
                return (
                    f"Successfully added web content to knowledge base:\n"
                    f"Title: {result['title']}\n"
                    f"URL: {result['url']}\n"
                    f"Document ID: {result['doc_id']}\n"
                    f"Chunks: {result['chunk_count']}"
                )
            else:
                return f"Error adding web content: {result.get('error', 'Unknown error')}"
        
        # Handle web_fetch_multiple tool
        elif tool_name == "web_fetch_multiple":
            urls = parameters.get("urls", [])
            if not urls:
                return "Error: No URLs provided"
            
            results = await web_content_manager.add_multiple_urls(urls)
            
            # Format the results as a summary
            success_count = sum(1 for r in results if r.get("status") == "success")
            error_count = len(results) - success_count
            
            summary = f"Processed {len(results)} URLs: {success_count} successful, {error_count} failed\n\n"
            
            # Add details for each URL
            for i, result in enumerate(results):
                if result.get("status") == "success":
                    summary += (
                        f"{i+1}. ✅ {result.get('title', 'Untitled')}\n"
                        f"   URL: {result.get('url', 'Unknown')}\n"
                        f"   Document ID: {result.get('doc_id', 'Unknown')}\n"
                    )
                else:
                    summary += (
                        f"{i+1}. ❌ Failed to process URL: {result.get('url', urls[i] if i < len(urls) else 'Unknown')}\n"
                        f"   Error: {result.get('error', 'Unknown error')}\n"
                    )
            
            return summary
        
        # Handle web_search tool
        elif tool_name == "web_search":
            query = parameters.get("query")
            if not query:
                return "Error: Query parameter is required"
            
            max_results = parameters.get("max_results", 3)
            if not isinstance(max_results, int) or max_results < 1:
                max_results = 3
            
            results = await web_content_manager.search_web_content(query, max_results)
            return results
        
        else:
            return f"Unknown web tool: {tool_name}"
    
    except Exception as e:
        logger.error(f"Error executing web tool {tool_name}: {e}")
        return f"Error executing {tool_name}: {str(e)}"