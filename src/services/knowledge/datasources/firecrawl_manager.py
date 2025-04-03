import os
import asyncio
import logging
import yaml
import uuid
import time
import schedule
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Import firecrawl when available, or provide graceful fallback
try:
    from firecrawl import Crawler
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    logging.warning("Firecrawl package not available. Advanced crawling disabled.")

from services.knowledge.document_processor import DocumentProcessor
from db.vector_db import VectorDB
from config.settings import settings

logger = logging.getLogger(__name__)

class FirecrawlManager:
    """
    Service to manage website crawling with Firecrawl.
    Reads configuration from a YAML file and schedules crawls.
    """
    
    def __init__(
        self, 
        config_path: Optional[str] = None,
        document_processor: Optional[DocumentProcessor] = None,
        vector_db: Optional[VectorDB] = None
    ):
        """
        Initialize the Firecrawl manager.
        
        Args:
            config_path: Path to the YAML configuration file
            document_processor: Document processor for storing content
            vector_db: Vector database instance
        """
        self.config_path = config_path or settings.FIRECRAWL_CONFIG_PATH
        self.document_processor = document_processor
        self.vector_db = vector_db or VectorDB()
        self.is_running = False
        self.scheduler_thread = None
        self.current_crawls: Set[str] = set()
        self.last_crawl_times: Dict[str, datetime] = {}
        
        # Check if Firecrawl is available
        if not FIRECRAWL_AVAILABLE:
            logger.error("Firecrawl package not installed. Run 'pip install firecrawl' to enable advanced crawling.")
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load the crawl configuration from YAML file.
        
        Returns:
            Dictionary of configuration values
        """
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Crawl configuration file not found: {self.config_path}")
                return {"global": {}, "sites": []}
            
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            logger.info(f"Loaded crawl configuration with {len(config.get('sites', []))} sites")
            return config
            
        except Exception as e:
            logger.error(f"Error loading crawl configuration: {e}")
            return {"global": {}, "sites": []}
    
    def refresh_config(self):
        """Reload the configuration from the file."""
        self.config = self._load_config()
    
    def _apply_site_config(self, site: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply global configuration and defaults to a site configuration.
        
        Args:
            site: Site configuration dictionary
            
        Returns:
            Complete site configuration with defaults
        """
        # Start with global config
        global_config = self.config.get("global", {})
        
        # Default values
        defaults = {
            "crawl_interval": 24,  # hours
            "max_pages": 100,
            "include_subdomains": True,
            "max_depth": 3,
            "respect_robots_txt": True,
            "delay": 1.0,
            "concurrency": 5,
            "timeout": 30
        }
        
        # Build complete config: defaults <- global <- site specific
        complete_config = defaults.copy()
        complete_config.update(global_config)
        complete_config.update(site)
        
        return complete_config
    
    async def start_crawl_service(self):
        """Start the crawl scheduling service."""
        if not FIRECRAWL_AVAILABLE:
            logger.error("Cannot start crawl service: Firecrawl not installed")
            return False
        
        if self.is_running:
            logger.warning("Crawl service is already running")
            return True
        
        self.is_running = True
        
        # Set up scheduler in a separate thread
        self.scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Run initial crawl for all sites
        await self.crawl_all_sites()
        
        logger.info("Firecrawl service started successfully")
        return True
    
    def stop_crawl_service(self):
        """Stop the crawl scheduling service."""
        if not self.is_running:
            logger.warning("Crawl service is not running")
            return
        
        self.is_running = False
        
        if self.scheduler_thread:
            # No clean way to stop thread, just let it exit naturally
            self.scheduler_thread = None
        
        logger.info("Firecrawl service stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop in a separate thread."""
        # Clear existing jobs
        schedule.clear()
        
        # Check for new crawls every hour
        schedule.every(1).hours.do(self._check_scheduled_crawls)
        
        # Run the scheduling loop
        logger.info("Starting Firecrawl scheduler")
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def _check_scheduled_crawls(self):
        """Check for and start scheduled crawls."""
        if not self.is_running:
            return
        
        # Refresh config
        self.refresh_config()
        
        current_time = datetime.now()
        sites_to_crawl = []
        
        for site in self.config.get("sites", []):
            site_url = site.get("url")
            if not site_url:
                continue
                
            # Apply configuration hierarchy
            site_config = self._apply_site_config(site)
            crawl_interval = site_config.get("crawl_interval", 24)  # hours
            
            # Check if it's time to crawl
            last_crawl = self.last_crawl_times.get(site_url)
            if last_crawl is None:
                # Never crawled
                sites_to_crawl.append(site)
            else:
                # Calculate hours since last crawl
                hours_since_last = (current_time - last_crawl).total_seconds() / 3600
                if hours_since_last >= crawl_interval:
                    sites_to_crawl.append(site)
        
        if sites_to_crawl:
            logger.info(f"Scheduling crawl for {len(sites_to_crawl)} sites")
            asyncio.run_coroutine_threadsafe(self.crawl_sites(sites_to_crawl), asyncio.get_event_loop())
    
    async def crawl_all_sites(self) -> Dict[str, Any]:
        """
        Crawl all sites in the configuration.
        
        Returns:
            Summary of crawl results
        """
        return await self.crawl_sites(self.config.get("sites", []))
    
    async def crawl_sites(self, sites: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Crawl multiple sites.
        
        Args:
            sites: List of site configurations
            
        Returns:
            Summary of crawl results
        """
        if not FIRECRAWL_AVAILABLE:
            return {"status": "error", "message": "Firecrawl not available"}
        
        if not sites:
            logger.warning("No sites to crawl")
            return {"status": "warning", "message": "No sites to crawl"}
        
        # Process each site
        tasks = []
        for site in sites:
            site_url = site.get("url")
            if not site_url:
                continue
                
            # Skip if already crawling
            if site_url in self.current_crawls:
                logger.info(f"Skipping {site_url}: already being crawled")
                continue
                
            # Add to current crawls
            self.current_crawls.add(site_url)
            
            # Create task
            task = asyncio.create_task(self._crawl_site(site))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                site_url = sites[i].get("url", "Unknown")
                logger.error(f"Error crawling {site_url}: {result}")
                processed_results.append({
                    "status": "error",
                    "url": site_url,
                    "error": str(result)
                })
                # Remove from current crawls
                self.current_crawls.discard(site_url)
            else:
                processed_results.append(result)
                # Update last crawl time if successful
                if result.get("status") == "success":
                    site_url = result.get("url")
                    if site_url:
                        self.last_crawl_times[site_url] = datetime.now()
                # Remove from current crawls
                self.current_crawls.discard(result.get("url", ""))
        
        summary = {
            "status": "completed",
            "total_sites": len(sites),
            "success_count": sum(1 for r in processed_results if r.get("status") == "success"),
            "error_count": sum(1 for r in processed_results if r.get("status") == "error"),
            "details": processed_results
        }
        
        logger.info(f"Crawl completed: {summary['success_count']} succeeded, {summary['error_count']} failed")
        return summary
    
    async def _crawl_site(self, site: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crawl a single site with Firecrawl.
        
        Args:
            site: Site configuration
            
        Returns:
            Crawl result information
        """
        site_url = site.get("url")
        if not site_url:
            return {"status": "error", "error": "No URL provided"}
        
        # Apply configuration hierarchy
        site_config = self._apply_site_config(site)
        
        # Process query parameters if any
        if "params" in site:
            parsed_url = urlparse(site_url)
            query_dict = parse_qs(parsed_url.query)
            
            # Update with provided params
            for key, value in site.get("params", {}).items():
                query_dict[key] = [value]
            
            # Reconstruct URL with updated query
            new_query = urlencode(query_dict, doseq=True)
            parsed_url = parsed_url._replace(query=new_query)
            site_url = urlunparse(parsed_url)
        
        logger.info(f"Starting crawl for {site_url}")
        
        try:
            # Configure crawler
            crawler = Crawler(
                start_url=site_url,
                max_depth=site_config.get("max_depth", 3),
                max_pages=site_config.get("max_pages", 100),
                respect_robots_txt=site_config.get("respect_robots_txt", True),
                follow_subdomains=site_config.get("include_subdomains", True),
                delay=site_config.get("delay", 1.0),
                concurrency=site_config.get("concurrency", 5),
                timeout=site_config.get("timeout", 30)
            )
            
            # Add exclusion patterns
            exclude_patterns = self.config.get("exclude_patterns", [])
            for pattern in exclude_patterns:
                crawler.exclude_url_pattern(pattern)
            
            # Start crawling
            pages = await crawler.run()
            
            # Process crawled pages
            successful_pages = 0
            failed_pages = 0
            
            # Use thread pool for processing to avoid blocking
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                
                for page in pages:
                    if page.response and page.response.status_code == 200:
                        # Process in thread pool
                        future = executor.submit(
                            self._process_page, 
                            page.url, 
                            page.response.text, 
                            page.response.headers.get("Content-Type", "")
                        )
                        futures.append(future)
                
                # Wait for all processing to complete
                for future in futures:
                    result = future.result()
                    if result.get("status") == "success":
                        successful_pages += 1
                    else:
                        failed_pages += 1
            
            # Return summary
            return {
                "status": "success",
                "url": site_url,
                "pages_crawled": len(pages),
                "pages_processed": successful_pages,
                "pages_failed": failed_pages,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error crawling {site_url}: {e}")
            return {
                "status": "error",
                "url": site_url,
                "error": str(e)
            }
    
    def _process_page(self, url: str, html_content: str, content_type: str) -> Dict[str, Any]:
        """
        Process a crawled page and store in vector database.
        
        Args:
            url: Page URL
            html_content: HTML content
            content_type: Content-Type header
            
        Returns:
            Processing result
        """
        try:
            # Only process HTML content
            if not content_type.startswith("text/html"):
                return {
                    "status": "skipped",
                    "url": url,
                    "reason": f"Unsupported content type: {content_type}"
                }
            
            # Convert HTML to markdown
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get title
            title = soup.title.string if soup.title else "Web Page"
            
            # Clean HTML content
            for script in soup(["script", "style", "noscript", "svg", "iframe"]):
                script.extract()
            
            # Get text content
            text = soup.get_text(separator='\n')
            
            # Clean up text
            text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
            
            # Add title and source at the top
            markdown = f"# {title}\n\nSource: {url}\n\n{text}"
            
            # Generate a document ID
            doc_id = f"web_{uuid.uuid4()}"
            
            # Prepare metadata
            metadata = {
                "doc_id": doc_id,
                "source": "web",
                "source_type": "firecrawl",
                "url": url,
                "title": title,
                "crawled_at": datetime.now().isoformat(),
                "content_type": content_type
            }
            
            # Process the document
            if self.document_processor:
                # Use document processor if available
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                chunk_ids = loop.run_until_complete(
                    self.document_processor.process_document(
                        content=markdown,
                        metadata=metadata,
                        chunk_size=500,
                        chunk_overlap=50
                    )
                )
                loop.close()
                
                return {
                    "status": "success",
                    "url": url,
                    "doc_id": doc_id,
                    "title": title,
                    "chunks": len(chunk_ids)
                }
            else:
                # Direct vector DB method if document processor not available
                chunks, chunk_metadatas = self._chunk_document(markdown, metadata)
                
                chunk_ids = self.vector_db.add_documents(
                    documents=chunks,
                    metadatas=chunk_metadatas
                )
                
                return {
                    "status": "success",
                    "url": url,
                    "doc_id": doc_id,
                    "title": title,
                    "chunks": len(chunk_ids)
                }
            
        except Exception as e:
            logger.error(f"Error processing page {url}: {e}")
            return {
                "status": "error",
                "url": url,
                "error": str(e)
            }
    
    def _chunk_document(self, content: str, metadata: Dict[str, Any], chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Split a document into overlapping chunks.
        
        Args:
            content: The document content
            metadata: Metadata for the document
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
            
        Returns:
            Tuple of (chunks, chunk_metadatas)
        """
        import re
        
        # Split on paragraphs first, then by size
        paragraphs = re.split(r'\n\s*\n', content)
        
        chunks = []
        chunk_metadatas = []
        current_chunk = ""
        
        for i, para in enumerate(paragraphs):
            # If adding this paragraph would exceed chunk size, save current chunk and start a new one
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(current_chunk)
                
                # Create metadata for this chunk
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_id"] = f"{metadata['doc_id']}_{len(chunks)}"
                chunk_metadata["chunk_index"] = len(chunks)
                chunk_metadatas.append(chunk_metadata)
                
                # Start new chunk with overlap
                words = current_chunk.split()
                overlap_words = words[-min(chunk_overlap, len(words)):]
                current_chunk = " ".join(overlap_words)
            
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_id"] = f"{metadata['doc_id']}_{len(chunks)}"
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadatas.append(chunk_metadata)
        
        return chunks, chunk_metadatas
    
    async def crawl_url_now(self, url: str) -> Dict[str, Any]:
        """
        Manually trigger a crawl for a specific URL.
        
        Args:
            url: URL to crawl
            
        Returns:
            Crawl result
        """
        # Create minimal site config
        site = {"url": url}
        
        # Apply global defaults
        site_config = self._apply_site_config(site)
        
        return await self._crawl_site(site_config)
    
    def get_crawl_status(self) -> Dict[str, Any]:
        """
        Get the status of the crawl service.
        
        Returns:
            Status information
        """
        return {
            "is_running": self.is_running,
            "firecrawl_available": FIRECRAWL_AVAILABLE,
            "sites_configured": len(self.config.get("sites", [])),
            "sites_crawled": len(self.last_crawl_times),
            "current_crawls": list(self.current_crawls),
            "last_crawl_times": {url: time.isoformat() for url, time in self.last_crawl_times.items()}
        }