import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel

# Support both legacy and MCP Google Drive
try:
    from services.knowledge.datasources.gdrive import GoogleDriveMCP
except ImportError:
    GoogleDriveMCP = None

try:
    from services.knowledge.datasources.mcp_gdrive import MCPGoogleDrive
except ImportError:
    MCPGoogleDrive = None
from services.mcp.claude import MCPTool, MCPToolParameter

logger = logging.getLogger(__name__)

# Define Google Drive-specific tools
GDRIVE_SEARCH_TOOL = MCPTool(
    name="gdrive_search",
    description="Search for files in Google Drive",
    parameters=[
        MCPToolParameter(
            name="query",
            description="The search query",
            type="string",
            required=True
        ),
        MCPToolParameter(
            name="max_results",
            description="Maximum number of results to return",
            type="integer",
            required=False
        )
    ]
)

GDRIVE_GET_FILE_TOOL = MCPTool(
    name="gdrive_get_file",
    description="Get the content of a file from Google Drive",
    parameters=[
        MCPToolParameter(
            name="file_id",
            description="The ID of the file",
            type="string",
            required=True
        )
    ]
)

GDRIVE_SYNC_TOOL = MCPTool(
    name="gdrive_sync",
    description="Sync recent files from Google Drive to the knowledge base",
    parameters=[
        MCPToolParameter(
            name="query",
            description="Optional query to filter files",
            type="string",
            required=False
        ),
        MCPToolParameter(
            name="max_files",
            description="Maximum number of files to sync",
            type="integer",
            required=False
        )
    ]
)

GDRIVE_TOOLS = [
    GDRIVE_SEARCH_TOOL,
    GDRIVE_GET_FILE_TOOL,
    GDRIVE_SYNC_TOOL
]

class GoogleDriveMCPTools:
    """Helper class for Google Drive MCP tools."""
    
    def __init__(self, gdrive_mcp = None):
        """
        Initialize the Google Drive MCP tools.
        
        Args:
            gdrive_mcp: The Google Drive MCP instance (either GoogleDriveMCP or MCPGoogleDrive)
        """
        self.gdrive_mcp = gdrive_mcp
    
    async def execute_gdrive_search(self, query: str, max_results: int = 10) -> str:
        """
        Execute the gdrive_search tool.
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            
        Returns:
            Formatted search results
        """
        if not self.gdrive_mcp:
            return "Google Drive MCP not initialized."
        
        try:
            files = await self.gdrive_mcp.search_files(query, max_results)
            
            if not files:
                return f"No files found matching '{query}'."
            
            # Check if we have PDF files in the results
            pdf_files = [file for file in files if file.get('mimeType') == 'application/pdf']
            
            results = []
            for i, file in enumerate(files):
                file_type = self._format_mime_type(file.get('mimeType', 'Unknown'))
                file_id = file.get('id')
                file_name = file.get('name', 'Untitled')
                
                result_entry = (
                    f"{i+1}. **{file_name}**\n"
                    f"   - ID: {file_id}\n"
                    f"   - Type: {file_type}\n"
                    f"   - Modified: {self._format_date(file.get('modifiedTime'))}\n"
                    f"   - Link: {file.get('webViewLink', 'No link available')}"
                )
                
                # Add special instructions for PDF files
                if file.get('mimeType') == 'application/pdf':
                    result_entry += f"\n   - To view details about this PDF: Use gdrive_get_file with ID '{file_id}'"
                
                results.append(result_entry)
            
            response = f"Found {len(files)} results in Google Drive for '{query}':\n\n" + "\n\n".join(results)
            
            # Add instruction for PDFs if any were found
            if pdf_files:
                pdf_tip = "\n\n**Note on PDF files:** To access information about PDF files in the results, use the `gdrive_get_file` tool with the file ID from the search results."
                response += pdf_tip
                
            return response
            
        except Exception as e:
            logger.error(f"Error executing gdrive_search: {e}")
            return f"Error searching Google Drive: {str(e)}"
    
    async def execute_gdrive_get_file(self, file_id: str) -> str:
        """
        Execute the gdrive_get_file tool.
        
        Args:
            file_id: The ID of the file
            
        Returns:
            File content with metadata
        """
        if not self.gdrive_mcp:
            return "Google Drive MCP not initialized."
        
        try:
            # Get metadata first
            file_metadata = None
            try:
                # Use files().get instead of get_file_content for just metadata
                file_request = self.gdrive_mcp.service.files().get(
                    fileId=file_id, 
                    fields="id, name, mimeType, description, modifiedTime, createdTime, webViewLink, owners, webContentLink"
                )
                file_metadata = file_request.execute()
            except Exception as e:
                logger.error(f"Error getting file metadata: {e}")
                return f"Error retrieving file metadata from Google Drive: {str(e)}"
            
            # Basic file info
            file_name = file_metadata.get('name', 'Untitled')
            mime_type = file_metadata.get('mimeType', 'Unknown')
            web_view_link = file_metadata.get('webViewLink', 'No link available')
            
            # Format basic metadata header
            header = (
                f"# {file_name}\n\n"
                f"- **Type**: {self._format_mime_type(mime_type)}\n"
                f"- **Created**: {self._format_date(file_metadata.get('createdTime'))}\n"
                f"- **Modified**: {self._format_date(file_metadata.get('modifiedTime'))}\n"
                f"- **Link**: {web_view_link}\n\n"
            )
            
            # Special handling for PDF files - instruct to use the webViewLink
            if mime_type == 'application/pdf':
                return (
                    f"{header}\n"
                    f"This is a PDF document. You can access it directly at: {web_view_link}\n\n"
                    f"For detailed questions about this PDF, please ask specifically about '{file_name}'."
                )
            
            # For other file types, try to get content as before
            content, _ = await self.gdrive_mcp.get_file_content(file_id)
            
            if not content:
                return f"{header}\nCould not retrieve content for this file. Please access it directly via the link above."
            
            # Return header + content (limit content length if too large)
            return header + self._truncate_content(content)
            
        except Exception as e:
            logger.error(f"Error executing gdrive_get_file: {e}")
            return f"Error retrieving file from Google Drive: {str(e)}"
    
    async def execute_gdrive_sync(self, query: Optional[str] = None, max_files: int = 20) -> str:
        """
        Execute the gdrive_sync tool.
        
        Args:
            query: Optional query to filter files
            max_files: Maximum number of files to sync
            
        Returns:
            Sync results
        """
        if not self.gdrive_mcp:
            return "Google Drive MCP not initialized."
        
        try:
            synced_count = await self.gdrive_mcp.sync_recent_files(query, max_files)
            
            if synced_count == 0:
                return "No files were synced from Google Drive."
            
            return f"Successfully synced {synced_count} files from Google Drive to the knowledge base."
            
        except Exception as e:
            logger.error(f"Error executing gdrive_sync: {e}")
            return f"Error syncing files from Google Drive: {str(e)}"
    
    def _format_mime_type(self, mime_type: str) -> str:
        """Format MIME type to a readable string."""
        mime_map = {
            'application/vnd.google-apps.document': 'Google Doc',
            'application/vnd.google-apps.spreadsheet': 'Google Sheet',
            'application/vnd.google-apps.presentation': 'Google Slides',
            'application/pdf': 'PDF',
            'text/plain': 'Text',
            'text/markdown': 'Markdown',
            'text/csv': 'CSV',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint'
        }
        return mime_map.get(mime_type, mime_type)
    
    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date string to readable format."""
        if not date_str:
            return "Unknown"
        
        # Simple formatting - can be enhanced as needed
        return date_str.replace('T', ' ').replace('Z', ' UTC')
    
    def _truncate_content(self, content: str, max_length: int = 4000) -> str:
        """Truncate content if it's too long."""
        if len(content) <= max_length:
            return content
        
        return content[:max_length] + f"\n\n[Content truncated. Total length: {len(content)} characters]"

async def execute_gdrive_tool(
    tool_name: str, 
    parameters: Dict[str, Any],
    gdrive_mcp
) -> str:
    """
    Execute a Google Drive tool based on name and parameters.
    
    Args:
        tool_name: The name of the tool to execute
        parameters: Dictionary of parameters for the tool
        gdrive_mcp: Google Drive MCP instance
        
    Returns:
        str: The result of the tool execution
    """
    tools = GoogleDriveMCPTools(gdrive_mcp)
    
    if tool_name == "gdrive_search":
        query = parameters.get("query", "")
        max_results = parameters.get("max_results", 10)
        return await tools.execute_gdrive_search(query, max_results)
    
    elif tool_name == "gdrive_get_file":
        file_id = parameters.get("file_id", "")
        return await tools.execute_gdrive_get_file(file_id)
    
    elif tool_name == "gdrive_sync":
        query = parameters.get("query")
        max_files = parameters.get("max_files", 20)
        return await tools.execute_gdrive_sync(query, max_files)
    
    else:
        return f"Unknown Google Drive tool: {tool_name}"