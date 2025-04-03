import logging
import uuid
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from services.mcp.web_fetch import MCPWebFetch
from services.knowledge.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

class WebContentManager:
    """Manages web content for the knowledge base using MCP Web Fetch."""
    
    def __init__(
        self, 
        document_processor: Optional[DocumentProcessor] = None,
        web_fetch: Optional[MCPWebFetch] = None
    ):
        """
        Initialize the web content manager.
        
        Args:
            document_processor: Document processor for storing content
            web_fetch: MCP Web Fetch integration instance
        """
        self.document_processor = document_processor
        self.web_fetch = web_fetch or MCPWebFetch()
    
    async def add_url_to_knowledge_base(
        self, 
        url: str, 
        chunk_size: int = 500, 
        chunk_overlap: int = 50
    ) -> Dict[str, Any]:
        """
        Fetch a URL and add its content to the knowledge base.
        
        Args:
            url: The URL to fetch and store
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks
            
        Returns:
            Dict with status and document info
        """
        if not self.document_processor:
            return {
                "status": "error",
                "error": "Document processor not initialized"
            }
        
        # Fetch the URL content
        fetch_result = await self.web_fetch.fetch_url(url)
        
        if fetch_result["status"] != "success":
            return fetch_result
        
        content = fetch_result["content"]
        
        # Extract title from the markdown content (assuming first line is title)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Web Page"
        
        # Prepare document metadata
        doc_id = f"web_{uuid.uuid4()}"
        metadata = {
            "doc_id": doc_id,
            "source": "web",
            "url": url,
            "title": title,
            "author": "Web Content",
            "created_at": datetime.now().isoformat(),
            "processed_at": datetime.now().isoformat()
        }
        
        try:
            # Process and store the document
            chunk_ids = await self.document_processor.process_document(
                content=content,
                metadata=metadata,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "title": title,
                "url": url,
                "chunk_count": len(chunk_ids)
            }
            
        except Exception as e:
            logger.error(f"Error processing web content: {e}")
            return {
                "status": "error",
                "error": f"Error processing web content: {str(e)}"
            }
    
    async def add_multiple_urls(
        self, 
        urls: List[str], 
        chunk_size: int = 500, 
        chunk_overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs and add their content to the knowledge base.
        
        Args:
            urls: List of URLs to fetch and store
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of result dictionaries for each URL
        """
        tasks = [self.add_url_to_knowledge_base(url, chunk_size, chunk_overlap) 
                for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "url": urls[i] if i < len(urls) else "Unknown",
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def search_web_content(
        self, 
        query: str, 
        n_results: int = 3
    ) -> str:
        """
        Search for web content in the knowledge base.
        
        Args:
            query: The search query
            n_results: Number of results to return
            
        Returns:
            Formatted search results
        """
        if not self.document_processor:
            return "Web search unavailable: Document processor not initialized"
        
        try:
            # Search with a filter for web source
            results = await self.document_processor.search_documents(
                query=query,
                n_results=n_results,
                filter_criteria={"source": "web"}
            )
            
            # Format the results
            formatted_results = self.document_processor.format_search_results(results)
            return formatted_results
        
        except Exception as e:
            logger.error(f"Error searching web content: {e}")
            return f"Error searching web content: {str(e)}"