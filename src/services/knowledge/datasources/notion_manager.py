import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

from services.knowledge.document_processor import DocumentProcessor
from db.vector_db import VectorDB
from config.settings import settings

# Import notion scraper with correct path
import sys
import os

# Add the notion directory to the Python path
notion_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "notion")
sys.path.append(notion_path)

from notion_scraper import NotionScraper

logger = logging.getLogger(__name__)

class NotionManager:
    """
    Service to manage Notion page fetching and processing.
    Reads configuration from environment variables and provides
    methods to fetch and store Notion content.
    """
    
    def __init__(
        self, 
        document_processor: Optional[DocumentProcessor] = None,
        vector_db: Optional[VectorDB] = None
    ):
        """
        Initialize the Notion manager.
        
        Args:
            document_processor: Document processor for storing content
            vector_db: Vector database instance
        """
        self.document_processor = document_processor
        self.vector_db = vector_db or VectorDB()
        self.api_key = settings.NOTION_API_KEY
        self.configured_pages = settings.NOTION_PAGES.split(',') if settings.NOTION_PAGES else []
        
        # Check if Notion API key is available
        if not self.api_key:
            logger.error("Notion API key not found. Set NOTION_API_KEY in environment variables.")
        else:
            logger.info(f"Notion manager initialized with {len(self.configured_pages)} configured pages")
    
    async def sync_all_pages(self) -> Dict[str, Any]:
        """
        Sync all configured Notion pages to the vector database.
        
        Returns:
            Summary of sync results
        """
        if not self.api_key:
            return {"status": "error", "message": "Notion API key not configured"}
        
        if not self.configured_pages:
            logger.warning("No Notion pages configured")
            return {"status": "warning", "message": "No Notion pages configured"}
        
        # Process all pages
        results = []
        for page_id in self.configured_pages:
            page_id = page_id.strip()
            if not page_id:
                continue
                
            result = await self.sync_page(page_id)
            results.append(result)
        
        # Return summary
        summary = {
            "status": "completed",
            "total_pages": len(self.configured_pages),
            "success_count": sum(1 for r in results if r.get("status") == "success"),
            "error_count": sum(1 for r in results if r.get("status") == "error"),
            "details": results
        }
        
        logger.info(f"Notion sync completed: {summary['success_count']} succeeded, {summary['error_count']} failed")
        return summary
    
    async def sync_page(self, page_id: str) -> Dict[str, Any]:
        """
        Sync a specific Notion page to the vector database.
        
        Args:
            page_id: ID of the Notion page to sync
            
        Returns:
            Sync result information
        """
        if not self.api_key:
            return {"status": "error", "message": "Notion API key not configured", "page_id": page_id}
        
        logger.info(f"Starting sync for Notion page {page_id}")
        
        try:
            # Create Notion scraper
            scraper = NotionScraper(self.api_key)
            
            # Get page data (title and content)
            page_data = scraper.retrieve_page_content(page_id)
            
            # Check if we got valid data
            if not page_data or "error" in page_data:
                error_message = page_data.get("error", "Unknown error") if page_data else "No data returned"
                logger.error(f"Error retrieving Notion page {page_id}: {error_message}")
                return {
                    "status": "error",
                    "page_id": page_id,
                    "error": error_message
                }
            
            # Get page title
            page_title = page_data.get("title", "Untitled Notion Page")
            
            # Get embedding documents
            embedding_docs = scraper.get_embedding_documents(page_data)
            
            # Process each document
            processed_count = 0
            for doc in embedding_docs:
                # Create document ID
                doc_id = f"notion_{uuid.uuid4()}"
                
                # Prepare metadata
                metadata = {
                    "doc_id": doc_id,
                    "source": "notion",
                    "page_id": page_id,
                    "title": page_title,
                    "retrieved_at": datetime.now().isoformat(),
                    **doc["metadata"]  # Include original metadata
                }
                
                # Process the document
                if self.document_processor:
                    # Use document processor if available
                    chunk_ids = await self.document_processor.process_document(
                        content=doc["page_content"],
                        metadata=metadata,
                        chunk_size=500,
                        chunk_overlap=50
                    )
                    processed_count += len(chunk_ids)
                else:
                    # Direct vector DB method if document processor not available
                    chunks, chunk_metadatas = self._chunk_document(doc["page_content"], metadata)
                    
                    chunk_ids = self.vector_db.add_documents(
                        documents=chunks,
                        metadatas=chunk_metadatas
                    )
                    processed_count += len(chunk_ids)
            
            # Return summary
            return {
                "status": "success",
                "page_id": page_id,
                "title": page_title,
                "documents": len(embedding_docs),
                "chunks": processed_count,
                "timestamp": datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"Error syncing Notion page {page_id}: {e}")
            return {
                "status": "error",
                "page_id": page_id,
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