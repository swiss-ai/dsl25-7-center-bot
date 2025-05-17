import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
import sys

from services.knowledge.document_processor import DocumentProcessor
from db.vector_db import VectorDB
from config.settings import settings

# Add the airtable directory to the Python path
airtable_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "airtable")
sys.path.append(airtable_path)

# Import airtable scraper
from airtable_scraper import AirtableScraper, fetch_airtable_for_embedding

logger = logging.getLogger(__name__)

class AirtableManager:
    """
    Service to manage Airtable data fetching and processing.
    Reads configuration from environment variables and provides
    methods to fetch and store Airtable content.
    """
    
    def __init__(
        self, 
        document_processor: Optional[DocumentProcessor] = None,
        vector_db: Optional[VectorDB] = None
    ):
        """
        Initialize the Airtable manager.
        
        Args:
            document_processor: Document processor for storing content
            vector_db: Vector database instance
        """
        self.document_processor = document_processor
        self.vector_db = vector_db or VectorDB()
        self.api_key = os.getenv("AIRTABLE_API_KEY")
        self.base_id = os.getenv("AIRTABLE_BASE_ID")
        self.include_tables = os.getenv("AIRTABLE_TABLES", "").split(',') if os.getenv("AIRTABLE_TABLES") else None
        
        # Check if Airtable API key is available
        if not self.api_key:
            logger.error("Airtable API key not found. Set AIRTABLE_API_KEY in environment variables.")
        else:
            logger.info(f"Airtable manager initialized with base ID: {self.base_id}")
    
    async def sync_airtable_base(self) -> Dict[str, Any]:
        """
        Sync Airtable base content to the vector database.
        
        Returns:
            Summary of sync results
        """
        if not self.api_key or not self.base_id:
            return {"status": "error", "message": "Airtable API key or base ID not configured"}
        
        logger.info(f"Starting sync for Airtable base {self.base_id}")
        
        try:
            # Initialize Airtable scraper
            scraper = AirtableScraper(self.api_key)
            
            # Get embedding documents
            include_tables_list = self.include_tables if self.include_tables and self.include_tables[0] else None
            embedding_docs = fetch_airtable_for_embedding(
                base_id=self.base_id,
                api_key=self.api_key,
                include_tables=include_tables_list
            )
            
            if not embedding_docs:
                logger.warning(f"No documents found in Airtable base {self.base_id}")
                return {
                    "status": "warning",
                    "message": "No documents found in Airtable base",
                    "base_id": self.base_id
                }
            
            # Process each document
            processed_count = 0
            for doc in embedding_docs:
                # Create document ID based on record ID in metadata
                record_id = doc["metadata"].get("record_id", str(uuid.uuid4()))
                doc_id = f"airtable_{record_id}"
                
                # Prepare metadata
                metadata = {
                    "doc_id": doc_id,
                    "source": "airtable",
                    "base_id": self.base_id,
                    "table_name": doc["metadata"].get("table_name", "Unknown"),
                    "table_id": doc["metadata"].get("table_id", "Unknown"),
                    "record_id": record_id,
                    "title": f"{doc['metadata'].get('table_name', 'Airtable')} Record",
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
                "base_id": self.base_id,
                "documents": len(embedding_docs),
                "chunks": processed_count,
                "timestamp": datetime.now().isoformat(),
                "tables": self.include_tables if self.include_tables else "all"
            }
                
        except Exception as e:
            logger.error(f"Error syncing Airtable base {self.base_id}: {e}")
            return {
                "status": "error",
                "base_id": self.base_id,
                "error": str(e)
            }
    
    async def search_airtable_records(self, query: str, table_name: Optional[str] = None, n_results: int = 5) -> str:
        """
        Search for Airtable records using direct API access.
        
        Args:
            query: The search query
            table_name: Optional specific table to search in
            n_results: Number of results to return
            
        Returns:
            Formatted search results
        """
        logger.info(f"Searching Airtable with query '{query}' in table '{table_name if table_name else 'all'}'")
        
        # Import the direct search module
        try:
            # Add airtable directory to path
            airtable_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "airtable")
            sys.path.insert(0, airtable_path)
            
            # Import the direct search class
            from direct_search import AirtableDirectSearch
            
            # Create searcher
            searcher = AirtableDirectSearch(api_key=self.api_key, base_id=self.base_id)
            
            # Run direct search against Airtable API
            results = await searcher.search_records(
                query=query,
                table_name=table_name,
                max_results=n_results
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error with direct Airtable search: {e}")
            
            # Fall back to vector database search if direct search fails
            if not self.document_processor:
                return f"Error: Document processor not initialized. Direct search also failed: {str(e)}"
            
            try:
                # Build filter criteria based on table name
                filter_criteria = {"source": "airtable"}
                if table_name:
                    filter_criteria["table_name"] = table_name
                
                # Perform the search using the document processor
                results = await self.document_processor.search_documents(
                    query=query,
                    n_results=n_results,
                    filter_criteria=filter_criteria
                )
                
                # Format the results
                formatted_results = self.document_processor.format_search_results(results)
                
                # If no results found
                if formatted_results == "No results found.":
                    if table_name:
                        return f"No Airtable records found for '{query}' in table '{table_name}'."
                    else:
                        return f"No Airtable records found for '{query}'."
                
                return f"## Airtable Search Results (from vector DB)\n{formatted_results}"
                
            except Exception as e2:
                logger.error(f"Error searching Airtable records in vector DB: {e2}")
                return f"Error searching Airtable: Direct search failed ({str(e)}) and vector DB search failed ({str(e2)})"
    
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