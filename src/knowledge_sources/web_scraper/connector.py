import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import os

from src.storage.chroma_client import ChromaDBClient
from src.utils.config import Config
from chromadb.utils import embedding_functions
from .v1.web_fetch import WebFetcher

logger = logging.getLogger(__name__)

class WebScraperConnector:
    """Connector to sync web content and store in ChromaDB for similarity search."""
    
    def __init__(self):
        """Initialize the web scraper connector."""
        self.collection_name = "web_content"
        self.chroma_client = ChromaDBClient()
        
        # Use sentence transformers for embeddings
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Get or create Web Content collection
        self.collection = self.chroma_client.get_or_create_collection(
            collection_name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"source": "web_scraper", "description": "Web scraped content"}
        )
        
        self.web_fetcher = WebFetcher()
        self.urls_file = Config.WEB_CONTENT_URLS_FILE
        logger.info(f"WebScraperConnector initialized with collection: {self.collection_name}")
    
    def _generate_doc_id(self, url: str, content: str) -> str:
        """Generate a unique document ID based on URL and content hash."""
        content_hash = hashlib.md5(f"{url}:{content[:100]}".encode()).hexdigest()[:8]
        return f"web_{content_hash}"
    
    def _enhance_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance metadata with additional fields for better citations."""
        enhanced = metadata.copy()
        
        # Ensure we have a proper URL for citations
        if "url" in enhanced:
            enhanced["web_url"] = enhanced["url"]
        
        # Add source type for filtering
        enhanced["source_type"] = "web_scraper"
        
        # Add indexing timestamp
        enhanced["indexed_at"] = datetime.now().isoformat()
        
        return enhanced
    
    def _read_urls_from_file(self) -> List[str]:
        """Read URLs from the configured file."""
        urls = []
        try:
            if not os.path.exists(self.urls_file):
                logger.warning(f"URLs file not found: {self.urls_file}")
                return urls
            
            with open(self.urls_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)
            
            logger.info(f"Read {len(urls)} URLs from {self.urls_file}")
            return urls
        except Exception as e:
            logger.error(f"Error reading URLs from file: {e}")
            return []
    
    def _chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        """Chunk text into smaller pieces for embedding."""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - chunk_overlap
        
        return chunks
    
    async def sync_web_content(self) -> Dict[str, Any]:
        """Sync all web content from configured URLs."""
        try:
            logger.info("Starting web content sync")
            
            # Read URLs from file
            urls = self._read_urls_from_file()
            if not urls:
                return {
                    "status": "warning",
                    "message": "No URLs found to sync",
                    "synced_count": 0
                }
            
            # Start the web fetcher
            await self.web_fetcher.start_server()
            
            synced_count = 0
            total_documents = 0
            errors = []
            
            # Clear existing documents first
            try:
                existing_ids = self.collection.get()["ids"]
                if existing_ids:
                    self.collection.delete(ids=existing_ids)
                    logger.info(f"Cleared {len(existing_ids)} existing documents")
            except Exception as e:
                logger.warning(f"Error clearing existing documents: {e}")
            
            for url in urls:
                try:
                    # Special handling for publications page
                    if url == 'https://ai.ethz.ch/research/publications.html':
                        # Skip dynamic content if Chrome is not available
                        logger.warning(f"Skipping {url} - requires Chrome/Chromium for dynamic content scraping")
                        errors.append({"url": url, "error": "Chrome/Chromium not installed - required for dynamic content"})
                        continue
                        
                        # TODO: When Chrome is available, uncomment this:
                        # publications = await self.web_fetcher.fetch_publications(url)
                        # for pub in publications:
                        #     doc_id = self._generate_doc_id(url, pub['title'])
                        #     content = f"Title: {pub['title']}\n\nAuthors: {pub['authors']}\n\nAbstract: {pub['abstract']}"
                        #     metadata = {
                        #         "url": url,
                        #         "web_url": url,
                        #         "title": pub['title'],
                        #         "authors": pub['authors'],
                        #         "source_type": "web_scraper",
                        #         "content_type": "publication",
                        #         "indexed_at": datetime.now().isoformat()
                        #     }
                        #     self.collection.add(
                        #         documents=[content],
                        #         metadatas=[self._enhance_metadata(metadata)],
                        #         ids=[doc_id]
                        #     )
                        #     total_documents += 1
                    else:
                        # Regular static content
                        result = await self.web_fetcher.fetch_url(url)
                        
                        if result.get("status") == "success":
                            content = result["content"]
                            
                            # Extract title from content if available
                            import re
                            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                            title = title_match.group(1) if title_match else "Web Page"
                            
                            # Chunk the content
                            chunks = self._chunk_text(content)
                            
                            for i, chunk in enumerate(chunks):
                                doc_id = self._generate_doc_id(url, f"{chunk[:50]}_{i}")
                                
                                metadata = {
                                    "url": url,
                                    "web_url": url,
                                    "title": title,
                                    "chunk_index": i,
                                    "total_chunks": len(chunks),
                                    "source_type": "web_scraper",
                                    "content_type": "webpage",
                                    "indexed_at": datetime.now().isoformat()
                                }
                                
                                # Add to collection
                                self.collection.add(
                                    documents=[chunk],
                                    metadatas=[self._enhance_metadata(metadata)],
                                    ids=[doc_id]
                                )
                                total_documents += 1
                            
                            synced_count += 1
                            logger.info(f"Successfully synced: {url} ({len(chunks)} chunks)")
                        else:
                            errors.append({"url": url, "error": result.get("error", "Unknown error")})
                            logger.error(f"Failed to sync {url}: {result.get('error')}")
                        
                except Exception as e:
                    errors.append({"url": url, "error": str(e)})
                    logger.error(f"Error syncing {url}: {e}")
            
            return {
                "status": "success",
                "message": f"Synced {synced_count} out of {len(urls)} URLs",
                "synced_count": synced_count,
                "total_urls": len(urls),
                "total_documents": total_documents,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error during web content sync: {e}")
            return {
                "status": "error",
                "message": str(e),
                "synced_count": 0
            }
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search web content using similarity search."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            if not results or not results["documents"] or not results["documents"][0]:
                return []
            
            formatted_results = []
            for i in range(len(results["documents"][0])):
                result = {
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                }
                formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching web content: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the web content collection."""
        try:
            # Get collection count
            collection_data = self.collection.get()
            doc_count = len(collection_data["ids"]) if collection_data and "ids" in collection_data else 0
            
            # Get unique URLs
            unique_urls = set()
            if collection_data and "metadatas" in collection_data:
                for metadata in collection_data["metadatas"]:
                    if metadata and "url" in metadata:
                        unique_urls.add(metadata["url"])
            
            return {
                "collection_name": self.collection_name,
                "total_documents": doc_count,
                "unique_urls": len(unique_urls),
                "urls_list": list(unique_urls)
            }
            
        except Exception as e:
            logger.error(f"Error getting web content stats: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }