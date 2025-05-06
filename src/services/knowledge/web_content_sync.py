import os
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from config.settings import settings
from services.mcp.web_fetch import MCPWebFetch
from services.knowledge.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

class WebContentSyncService:
    """
    Service to sync web content from a list of URLs.
    Reads URLs from a file and fetches/processes them into the vector database.
    """
    
    def __init__(self, 
                 document_processor: Optional[DocumentProcessor] = None,
                 web_fetch: Optional[MCPWebFetch] = None):
        """
        Initialize the web content sync service.
        
        Args:
            document_processor: Document processor for storing content
            web_fetch: MCP Web Fetch integration
        """
        self.document_processor = document_processor
        self.web_fetch = web_fetch or MCPWebFetch()
        self.urls_file = settings.WEB_CONTENT_URLS_FILE
        self.sync_interval = settings.WEB_CONTENT_SYNC_INTERVAL
        self.is_running = False
        self.last_sync_time = None
        self._sync_task = None
    
    def read_urls_from_file(self) -> List[str]:
        """
        Read URLs from the configured file.
        
        Returns:
            List of URLs
        """
        urls = []
        
        try:
            if not os.path.exists(self.urls_file):
                logger.warning(f"URLs file not found: {self.urls_file}")
                return urls
            
            with open(self.urls_file, 'r') as f:
                for line in f:
                    # Skip empty lines and comments
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)
            
            logger.info(f"Read {len(urls)} URLs from {self.urls_file}")
            return urls
            
        except Exception as e:
            logger.error(f"Error reading URLs from file: {e}")
            return []
    
    async def fetch_and_process_url(self, url: str, dynamic_content: bool) -> Dict[str, Any]:
        """
        Fetch and process a single URL.
        
        Args:
            url: The URL to fetch
            dynamic_content: Whether content is dynamic (JS loading HTML content)
            
        Returns:
            Result information
        """

        if not self.document_processor:
                return {"status": "error", "url": url, "error": "Document processor not initialized"}
        
        if not dynamic_content:    
            try:
                # Fetch the content using MCP Web Fetch
                fetch_result = await self.web_fetch.fetch_url(url)
                
                if fetch_result["status"] != "success":
                    return fetch_result
                
                content = fetch_result["content"]
                
                # Generate a document ID
                import uuid
                import re
                
                # Try to extract title from the content
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else "Web Page"
                
                doc_id = f"web_{uuid.uuid4()}"
                
                # Prepare metadata
                metadata = {
                    "doc_id": doc_id,
                    "source": "web",
                    "url": url,
                    "title": title,
                    "author": "Web Content",
                    "created_at": datetime.now().isoformat(),
                    "synchronized_at": datetime.now().isoformat()
                }
                
                # Process and store the document
                chunk_ids = await self.document_processor.process_document(
                    content=content,
                    metadata=metadata,
                    chunk_size=500,
                    chunk_overlap=50
                )
                
                return {
                    "status": "success",
                    "url": url,
                    "doc_id": doc_id,
                    "title": title,
                    "chunks": len(chunk_ids)
                }
                
            except Exception as e:
                logger.error(f"Error processing URL {url}: {e}")
                return {
                    "status": "error",
                    "url": url,
                    "error": str(e)
                }
        else:
            try:
                publications = self.web_fetch.fetch_publications(url)
                res = []
                for publication in publications:
                    doc_id = f"web_{uuid.uuid4()}"
                    metadata = {
                        "doc_id": doc_id,
                        "source": "web",
                        "url": url,
                        "title": publication['title'],
                        "author": publication['authors'],
                        "created_at": datetime.now().isoformat(),
                        "synchronized_at": datetime.now().isoformat()
                    }
                
                    chunk_ids = await self.document_processor.process_document(
                        content=publication['abstract'],
                        metadata=metadata,
                        chunk_size=500,
                        chunk_overlap=50
                    )

                    res.append((doc_id, chunk_ids))

                # Not sure what to return (does not matter I think)
                return {
                    "status": "success",
                    "url": url,
                    "res": res
                }


            except Exception as e:
                logger.error(f"Error processing URL {url}: {e}")
                return {
                    "status": "error",
                    "url": url,
                    "error": str(e)
                }

    async def sync_all_urls(self) -> Dict[str, Any]:
        """
        Synchronize all URLs from the file.
        
        Returns:
            Summary of sync results
        """
        start_time = time.time()
        self.last_sync_time = datetime.now()
        
        # Read URLs from file
        urls = self.read_urls_from_file()
        
        if not urls:
            logger.warning("No URLs to synchronize")
            return {
                "status": "warning",
                "message": "No URLs found to synchronize",
                "time_taken": time.time() - start_time
            }
        
        # Start the MCP Web Fetch server if needed
        server_started = await self.web_fetch.start_server()
        if not server_started:
            logger.error("Failed to start MCP Web Fetch server")
            return {
                "status": "error",
                "message": "Failed to start MCP Web Fetch server",
                "time_taken": time.time() - start_time
            }
        
        # Process each URL
        tasks = [self.fetch_and_process_url(url, url == 'https://ai.ethz.ch/research/publications.html') for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        success_count = 0
        error_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "url": urls[i] if i < len(urls) else "Unknown",
                    "error": str(result)
                })
                error_count += 1
            else:
                processed_results.append(result)
                if result.get("status") == "success":
                    success_count += 1
                else:
                    error_count += 1
        
        time_taken = time.time() - start_time
        
        logger.info(f"Web content sync completed: {success_count} succeeded, {error_count} failed, time taken: {time_taken:.2f}s")
        
        return {
            "status": "completed",
            "total_urls": len(urls),
            "success_count": success_count,
            "error_count": error_count,
            "details": processed_results,
            "time_taken": time_taken
        }
    
    async def _sync_task_loop(self):
        """Background task to periodically sync web content."""
        while self.is_running:
            try:
                logger.info("Starting scheduled web content sync")
                sync_result = await self.sync_all_urls()
                logger.info(f"Scheduled sync completed: {sync_result['success_count']} succeeded, {sync_result['error_count']} failed")
            except Exception as e:
                logger.error(f"Error in scheduled web content sync: {e}")
            
            # Sleep until next sync interval
            await asyncio.sleep(self.sync_interval)
    
    async def start_scheduled_sync(self):
        """Start the scheduled sync task."""
        if self.is_running:
            logger.warning("Scheduled sync is already running")
            return
        
        self.is_running = True
        self._sync_task = asyncio.create_task(self._sync_task_loop())
        logger.info(f"Scheduled web content sync started with interval: {self.sync_interval}s")
    
    def stop_scheduled_sync(self):
        """Stop the scheduled sync task."""
        if not self.is_running:
            logger.warning("Scheduled sync is not running")
            return
        
        self.is_running = False
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None
        
        logger.info("Scheduled web content sync stopped")
    
    async def manual_sync(self) -> Dict[str, Any]:
        """
        Manually trigger a sync of all URLs.
        
        Returns:
            Summary of sync results
        """
        logger.info("Manual web content sync requested")
        return await self.sync_all_urls()