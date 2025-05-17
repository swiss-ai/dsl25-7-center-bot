import logging
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
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
    chunk_size: int = 500, #put 500 again
    chunk_overlap: int = 50
) -> List[str]:
        """
        Process a document and store it in the vector database with update-aware logic.
        
        Args:
            content: The document content
            metadata: Metadata for the document
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
            
        Returns:
            List of final chunk IDs
        """
        try:
            # Generate a document ID if not provided
            doc_id = metadata.get("doc_id", str(uuid.uuid4()))
            metadata["doc_id"] = doc_id

            # Generate file ID and name
            file_id = metadata.get("file_id", doc_id)
            file_name = metadata.get("file_name", "unknown")
            current_time = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
            metadata["processed_at"] = current_time

            # Chunk the document
            chunks, chunk_metadatas = self._chunk_document(content, metadata, chunk_size, chunk_overlap)
            num_chunks = len(chunks)

            # Access the Chroma collection
            collection = self.vector_db.collection

            # Step 1: Insert temp chunks
            temp_ids = []
            temp_metadatas = []

            for i, chunk in enumerate(chunks):
                temp_id = f"temp__{file_id}__{i}"
                chunk_metadata = chunk_metadatas[i]
                chunk_metadata.update({
                    "file_id": file_id,
                    "file_name": file_name,
                    "chunk_index": i,
                    "num_chunks": num_chunks,
                    "last_modified": current_time,
                    "temp": True
                })
                temp_ids.append(temp_id)
                temp_metadatas.append(chunk_metadata)

            collection.add(
                ids=temp_ids,
                documents=chunks,
                metadatas=temp_metadatas
            )

            # Step 2: Replace old chunks
            collection.delete(where={"file_id": file_id})

            final_ids = []
            for i, chunk in enumerate(chunks):
                final_id = f"{file_id}_{i}"
                chunk_metadata = chunk_metadatas[i]
                chunk_metadata.pop("temp", None)
                collection.add(
                    ids=[final_id],
                    documents=[chunk],
                    metadatas=[chunk_metadata]
                )
                final_ids.append(final_id)

            # Cleanup temp chunks
            collection.delete(where={"$and": [{"file_id": {"$eq": file_id}}, {"temp": {"$eq": True}}]})

            logger.info(f"✅ Stored {len(final_ids)} chunks for document {file_id}")
            return final_ids

        except Exception as e:
            logger.error(f"❌ Error processing document {metadata.get('file_id', 'unknown')}: {e}")
            try:
                collection.delete(where={"file_id": metadata.get("file_id", doc_id), "temp": True})
            except:
                logger.error("⚠️ Failed to clean up temp chunks.")
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
        print(f"search_documents: query='{query}', n_results={n_results}, filter_criteria={filter_criteria}")
        try:
            logger.info(f"Starting vector_db search with query='{query}', n_results={n_results}")
            
            # Check if vector_db is properly initialized
            if not self.vector_db or not hasattr(self.vector_db, 'search'):
                logger.error("Vector DB not properly initialized")
                return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}
            
            # Use the vector_db search directly (not async)
            # Try with full_documents=False first for diagnostics
            initial_results = self.vector_db.search(
                query=query,
                n_results=n_results,
                filter_criteria=filter_criteria, 
                return_full_documents=False
            )
            
            # Log initial search results
            doc_count = len(initial_results.get("documents", [[]])[0])
            logger.info(f"Initial search found {doc_count} results for query: '{query}'")
            
            if doc_count == 0:
                logger.warning(f"No results found for query: '{query}'")
                # Return empty results rather than trying full document recovery
                return initial_results
            
            # Now do the full document recovery if we have results
            results = self.vector_db.search(
                query=query,
                n_results=n_results,
                filter_criteria=filter_criteria, 
                return_full_documents=True
            )
            
            logger.info(f"Full document recovery completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}", exc_info=True)
            # Return empty results instead of raising exception
            return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}
    
    def format_search_results(self, results: Dict[str, Any]) -> str:
        """
        Format search results for display.
        
        Args:
            results: Search results from the vector database
            
        Returns:
            Formatted search results
        """
        logger.info(f"Formatting search results: type={type(results)}")
        
        # Comprehensive validation of results structure
        if not results:
            logger.warning("Empty results object provided")
            return "No results found."
            
        # Handle the case where results is a dict with full_documents format
        if isinstance(results, dict) and "documents" in results:
            if isinstance(results["documents"], dict):
                # This is the return_full_documents=True format
                logger.info("Processing full documents format")
                if not results["documents"]:
                    return "No results found."
                    
                output = []
                for file_id, full_text in results["documents"].items():
                    title = file_id
                    source = "Knowledge Base"
                    
                    # Truncate the text for display
                    snippet = full_text[:200] + "..." if len(full_text) > 200 else full_text
                    
                    result = f"Result: {title} (Source: {source})\n{snippet}"
                    output.append(result)
                
                return "\n\n".join(output)
        
        # Standard format checking (documents as lists of lists)
        if not results.get("documents"):
            logger.warning("Missing 'documents' key in results")
            return "No results found."
            
        if not results["documents"][0]:
            logger.warning("Empty documents list in results")
            return "No results found."
        
        try:
            documents = results["documents"][0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0] if "distances" in results else None
            
            output = []
            
            # Check if documents and metadatas have same length
            if len(documents) != len(metadatas):
                logger.warning(f"Length mismatch: documents={len(documents)}, metadatas={len(metadatas)}")
                # Fix by truncating the longer one or padding the shorter one
                min_len = min(len(documents), len(metadatas))
                documents = documents[:min_len]
                metadatas = metadatas[:min_len]
            
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                # Safely extract metadata
                source = meta.get("source", "Unknown") if isinstance(meta, dict) else "Unknown"
                title = meta.get("title", "Untitled") if isinstance(meta, dict) else "Untitled"
                score = distances[i] if distances and i < len(distances) else None
                
                result = f"Result {i+1}: {title} (Source: {source})"
                if score is not None:
                    result += f" [Score: {score:.4f}]"
                
                if isinstance(meta, dict) and meta.get("url"):
                    result += f"\nURL: {meta['url']}"
                
                # Safely extract document text
                doc_text = doc[:200] + "..." if isinstance(doc, str) and len(doc) > 200 else str(doc)
                result += f"\n{doc_text}"
                output.append(result)
            
            return "\n\n".join(output)
            
        except Exception as e:
            logger.error(f"Error formatting search results: {e}", exc_info=True)
            return f"Error formatting results: {str(e)}"
    
    def fetch_document_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and reconstruct a full document by its file_id (i.e., document ID).
        
        Args:
            file_id: The file/document ID.
        
        Returns:
            Dictionary with 'content' and 'metadata', or None if not found.
        """
        print("fetch document by id inside document processor with id", file_id)
        try:
            chunk_data = self.vector_db.get_chunks_by_file_id(file_id)
            documents = chunk_data.get("documents", [])
            metadatas = chunk_data.get("metadatas", [])

            if not documents:
                logger.warning(f"No chunks found for document ID {file_id}")
                return None

            # Reconstruct full text
            indexed_chunks = zip(metadatas, documents)
            sorted_chunks = sorted(indexed_chunks, key=lambda pair: pair[0].get("chunk_index", 0))
            full_text = "\n\n".join(chunk for _, chunk in sorted_chunks)

            # Use the first chunk's metadata as base (common practice)
            base_metadata = metadatas[0] if metadatas else {}

            return {
                "content": full_text,
                "metadata": base_metadata
            }

        except Exception as e:
            logger.error(f"Error fetching document by ID {file_id}: {e}")
            return None
