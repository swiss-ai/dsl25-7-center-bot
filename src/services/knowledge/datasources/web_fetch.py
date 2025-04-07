import logging
import aiohttp
import asyncio
import uuid
import os
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from bs4 import BeautifulSoup

from config.settings import settings
from services.knowledge.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

class WebFetchManager:
    """
    Web content fetching and processing.
    """
    
    def __init__(self, document_processor: Optional[DocumentProcessor] = None):
        """
        Initialize the web fetcher.
        
        Args:
            document_processor: Document processor for storing content
        """
        self.document_processor = document_processor
        
    # Implement the WebFetchManager methods - can be added later
    # For now, this is a placeholder to fix the import error

class WebFetchMCP:
    """
    Web content fetching and processing for MCP integration.
    """
    
    def __init__(self, document_processor: Optional[DocumentProcessor] = None):
        """
        Initialize the web fetcher.
        
        Args:
            document_processor: Document processor for storing content
        """
        self.document_processor = document_processor
        
    async def fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch content from a URL.
        
        Args:
            url: The URL to fetch
            
        Returns:
            The text content of the page, or None if the fetch failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching {url}: HTTP {response.status}")
                        return None
                    
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" in content_type:
                        html = await response.text()
                        return self._extract_text_from_html(html, url)
                    elif "application/json" in content_type:
                        json_text = await response.text()
                        return json_text
                    else:
                        return await response.text()
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def _extract_text_from_html(self, html: str, url: str) -> str:
        """
        Extract meaningful text content from HTML.
        
        Args:
            html: The HTML content
            url: The source URL
            
        Returns:
            Cleaned text content
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        
        # Get title
        title = soup.title.text if soup.title else "Untitled Page"
        
        # Get text content from article, main, and content divs first
        main_content = ""
        
        # First try common content containers
        content_containers = soup.select("article, main, [role='main'], .content, #content, .post, .entry")
        if content_containers:
            for container in content_containers:
                main_content += container.get_text(separator="\n", strip=True) + "\n\n"
        else:
            # If no content containers, use the body
            main_content = soup.body.get_text(separator="\n", strip=True) if soup.body else ""
        
        # Clean up whitespace
        main_content = re.sub(r'\n\s*\n', '\n\n', main_content)
        
        # Format output with title and URL
        text = f"# {title}\nSource: {url}\n\n{main_content}"
        return text
    
    async def fetch_and_store(self, url: str) -> Dict[str, Any]:
        """
        Fetch URL content and store it in the vector database.
        
        Args:
            url: The URL to fetch and store
            
        Returns:
            Result dictionary with status and document info
        """
        if not self.document_processor:
            return {"status": "error", "error": "Document processor not initialized"}
        
        content = await self.fetch_url(url)
        if not content:
            return {"status": "error", "error": f"Failed to fetch content from {url}"}
        
        # Extract title from content (assumes first line is title)
        title_match = re.search(r'#\s+(.*?)(?:\n|$)', content)
        title = title_match.group(1) if title_match else "Untitled Page"
        
        # Prepare metadata
        metadata = {
            "source": "web",
            "url": url,
            "title": title,
            "author": "Unknown",
            "created_at": datetime.now().isoformat(),
            "doc_id": f"web_{uuid.uuid4()}"
        }
        
        # Process and store the document
        try:
            chunk_ids = await self.document_processor.process_document(
                content=content,
                metadata=metadata,
                chunk_size=500,
                chunk_overlap=50
            )
            
            return {
                "status": "success",
                "doc_id": metadata["doc_id"],
                "title": title,
                "url": url,
                "chunk_count": len(chunk_ids)
            }
        except Exception as e:
            logger.error(f"Error processing web content: {e}")
            return {"status": "error", "error": str(e)}
    
    async def fetch_and_store_multiple(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch and store multiple URLs in parallel.
        
        Args:
            urls: List of URLs to fetch and store
            
        Returns:
            List of result dictionaries
        """
        tasks = [self.fetch_and_store(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "url": urls[i],
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def search_web_content(self, query: str, n_results: int = 3) -> str:
        """
        Search web content in the vector database.
        
        Args:
            query: The search query
            n_results: Number of results to return
            
        Returns:
            Formatted search results
        """
        if not self.document_processor:
            return "Web search not available: Document processor not initialized"
        
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