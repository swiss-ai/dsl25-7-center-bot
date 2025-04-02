import logging
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from db.vector_db import VectorDB

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Service for processing documents and storing them in the vector database.
    """
    
    def __init__(self, vector_db: Optional[VectorDB] = None):
        """
        Initialize the document processor.
        
        Args:
            vector_db: Optional vector database instance
        """
        self.vector_db = vector_db or VectorDB(collection_name="documents")
    
    async def process_document(
        self, 
        content: str, 
        metadata: Dict[str, Any],
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        Process a document and store it in the vector database.
        
        Args:
            content: The document content
            metadata: Metadata for the document
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
            
        Returns:
            List of chunk IDs
        """
        try:
            # Generate a document ID if not provided
            doc_id = metadata.get("doc_id", str(uuid.uuid4()))
            
            # Add document ID and timestamp to metadata
            metadata["doc_id"] = doc_id
            metadata["processed_at"] = datetime.now().isoformat()
            
            # Chunk the document
            chunks, chunk_metadatas = self._chunk_document(content, metadata, chunk_size, chunk_overlap)
            
            # Add chunks to vector database
            chunk_ids = self.vector_db.add_documents(
                documents=chunks,
                metadatas=chunk_metadatas
            )
            
            logger.info(f"Processed document {doc_id} into {len(chunks)} chunks")
            return chunk_ids
        
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            raise e
    
    def _chunk_document(
        self, 
        content: str, 
        metadata: Dict[str, Any],
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
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
        # Simple chunking by splitting on paragraphs first, then by size
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
    
    async def search_documents(
        self, 
        query: str, 
        n_results: int = 5, 
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for documents based on a query.
        
        Args:
            query: The search query
            n_results: Number of results to return
            filter_criteria: Filter to apply to the search
            
        Returns:
            Dictionary containing search results
        """
        try:
            # Use the vector_db search directly (not async)
            results = self.vector_db.search(
                query=query,
                n_results=n_results,
                filter_criteria=filter_criteria
            )
            
            return results
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            raise e
    
    def format_search_results(self, results: Dict[str, Any]) -> str:
        """
        Format search results for display.
        
        Args:
            results: Search results from the vector database
            
        Returns:
            Formatted search results
        """
        if not results or not results.get("documents") or not results["documents"][0]:
            return "No results found."
        
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results else None
        
        output = []
        
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            source = meta.get("source", "Unknown")
            title = meta.get("title", "Untitled")
            score = distances[i] if distances else None
            
            result = f"Result {i+1}: {title} (Source: {source})"
            if score is not None:
                result += f" [Score: {score:.4f}]"
            
            if meta.get("url"):
                result += f"\nURL: {meta['url']}"
                
            result += f"\n{doc[:200]}..."
            output.append(result)
        
        return "\n\n".join(output)