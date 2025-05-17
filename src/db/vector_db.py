import os
import uuid
import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Any, Optional, Union
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Get configuration from environment
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

class VectorDB:
    """Vector database manager using Chroma."""
    
    def __init__(self, collection_name: str = "documents", persist_directory: str = CHROMA_PERSIST_DIRECTORY):
        """
        Initialize the vector database.
        
        Args:
            collection_name: The name of the collection to use
            persist_directory: Directory to persist the database
        """
        # Create persistence directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize Chroma client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # Get or create collection
        # Use sentence-transformers for embeddings
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        
        try:
            # Try to get existing collection
            self.collection = self.client.get_collection(
                name=collection_name,
                embedding_function=sentence_transformer_ef
            )
            logger.info(f"Using existing collection: {collection_name}")
        except Exception as e:
            # Create collection if it doesn't exist
            logger.info(f"Collection {collection_name} not found, creating it: {str(e)}")
            self.collection = self.client.create_collection(
                name=collection_name,
                embedding_function=sentence_transformer_ef,
                metadata={"description": f"AI Center Bot documents"}
            )
            logger.info(f"Created new collection: {collection_name}")
    
    def add_documents(
        self, 
        documents: List[str], 
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the vector database.
        
        Args:
            documents: List of document texts to add
            metadatas: List of metadata for each document
            ids: List of IDs for each document
            
        Returns:
            List of document IDs
        """
        if not documents:
            logger.warning("No documents provided to add")
            return []
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(documents))]
        
        # Ensure metadatas is provided for each document
        if metadatas is None:
            metadatas = [{} for _ in range(len(documents))]
        
        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(documents)} documents to collection")
            return ids
        except Exception as e:
            logger.error(f"Error adding documents to collection: {e}")
            raise e
    
    def search(
    self, 
    query: str, 
    n_results: int = 5, 
    filter_criteria: Optional[Dict[str, Any]] = None,
    return_full_documents: bool = False
) -> Dict[str, Any]:
        """
        Search for documents based on a query.
        
        Args:
            query: The search query
            n_results: Number of results to return
            filter_criteria: Optional metadata filter
            return_full_documents: Whether to return reconstructed full documents
        
        Returns:
            Dictionary with search results or full documents
        """
        try:
            logger.info(f"VectorDB.search: query='{query}', n_results={n_results}, filter={filter_criteria}, return_full_docs={return_full_documents}")
            
            # Check if collection is properly initialized
            if not self.collection:
                logger.error("Collection not initialized properly")
                return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}
            
            # Perform the query with additional debug info
            logger.info(f"Executing chromadb query with query_texts=['{query}']")
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_criteria
            )
            
            # Detailed logging of the query results
            doc_count = len(results.get("documents", [[]])[0]) if results.get("documents") else 0
            meta_count = len(results.get("metadatas", [[]])[0]) if results.get("metadatas") else 0
            ids_count = len(results.get("ids", [[]])[0]) if results.get("ids") else 0
            
            logger.info(f"Query results: {doc_count} documents, {meta_count} metadatas, {ids_count} ids")
            
            if doc_count == 0:
                logger.warning(f"No matching documents found for query: '{query}'")
                return results
                
            if return_full_documents:
                logger.info("Attempting to recover full documents from search results")
                try:
                    metadatas = results.get("metadatas", [[]])[0]
                    full_docs = self.recover_full_documents_from_matches(metadatas)
                    logger.info(f"Successfully recovered {len(full_docs)} full documents")
                    return {"documents": full_docs}
                except Exception as full_doc_error:
                    logger.error(f"Error recovering full documents: {full_doc_error}", exc_info=True)
                    # Return original results if full document recovery fails
                    return results

            logger.info(f"Found {doc_count} results for query: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error searching collection: {e}", exc_info=True)
            # Return empty results instead of raising the exception
            return {"documents": [[]], "metadatas": [[]], "ids": [[]], "distances": [[]]}

    
    def delete(self, ids: List[str]) -> None:
        """
        Delete documents by ID.
        
        Args:
            ids: List of document IDs to delete
        """
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents from collection")
        except Exception as e:
            logger.error(f"Error deleting documents from collection: {e}")
            raise e
    
    def get(self, ids: List[str]) -> Dict[str, Any]:
        """
        Get documents by ID.
        
        Args:
            ids: List of document IDs to retrieve
            
        Returns:
            Dictionary containing the requested documents
        """
        try:
            results = self.collection.get(ids=ids)
            logger.info(f"Retrieved {len(ids)} documents from collection")
            return results
        except Exception as e:
            logger.error(f"Error getting documents from collection: {e}")
            raise e
    
    def count(self) -> int:
        """
        Get the number of documents in the collection.
        
        Returns:
            Number of documents
        """
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Error counting documents in collection: {e}")
            raise e
        
    def get_chunks_by_file_id(self, file_id: str) -> Dict[str, Any]:
        """
        Retrieve all chunks associated with a specific file_id and write them to a debug text file.
        
        Args:
            file_id: The file identifier to retrieve chunks for.
        
        Returns:
            Dictionary with 'documents' and 'metadatas' for all chunks.
        """
        try:
            results = self.collection.get()
            matching_docs = []
            matching_metas = []

            #debug_lines = [f"🔍 Searching for file_id: {file_id}\n"]

            for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
                found_id = meta.get("file_id", "N/A")
                if found_id == file_id:
                    matching_docs.append(doc)
                    matching_metas.append(meta)
                    #debug_lines.append(f"\n✅ MATCH:\nfile_id: {found_id}\nchunk_index: {meta.get('chunk_index')}\ndoc_snippet: {doc[:200]}...\n")
                else:
                    #debug_lines.append(f"⛔️ No match: found file_id = {found_id}\n")
                    pass
            #debug_lines.append(f"\nTotal matches found: {len(matching_docs)}\n")

            #with open("chunk_debug_output.txt", "w", encoding="utf-8") as f:
                #f.writelines(debug_lines)

            logger.info(f"Retrieved {len(matching_docs)} chunks for file_id: {file_id}")
            return {"documents": matching_docs, "metadatas": matching_metas}
        
        except Exception as e:
            logger.error(f"Error retrieving chunks for file_id {file_id}: {e}")
            return {"documents": [], "metadatas": []}

    
    def recover_full_documents_from_matches(self, matched_metadatas: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Given a list of matched chunk metadata, return full reconstructed documents for each file.
        
        Args:
            matched_metadatas: List of metadata dicts for matched chunks.
        
        Returns:
            Dict mapping file_id → full document text.
        """
        # Enhanced debugging
        logger.info(f"recover_full_documents_from_matches: received {len(matched_metadatas)} metadata entries")
        
        # Early exit for empty metadata list
        if not matched_metadatas:
            logger.warning("No metadata entries provided for document recovery")
            return {}
            
        # Check if the input is the expected type
        if not isinstance(matched_metadatas, list):
            logger.error(f"Expected matched_metadatas to be a list, got {type(matched_metadatas)}")
            # Return a valid but empty result rather than failing
            return {}
        
        seen_file_ids = set()
        reconstructed_files = {}

        try:
            for i, metadata in enumerate(matched_metadatas):
                # Validate metadata entry is a dictionary
                if not isinstance(metadata, dict):
                    logger.warning(f"Metadata entry {i+1} is not a dictionary: {metadata}")
                    continue
                
                # Check for file_id in metadata
                file_id = metadata.get("file_id")
                if not file_id:
                    # Try alternative fields if file_id is missing
                    file_id = metadata.get("doc_id") or metadata.get("id")
                    if not file_id:
                        logger.warning(f"Metadata entry {i+1} missing file_id or alternative ID: {metadata}")
                        continue
                    logger.info(f"Using alternative ID field for file_id: {file_id}")
                    
                if file_id in seen_file_ids:
                    logger.debug(f"File ID {file_id} already processed, skipping duplicate")
                    continue

                logger.info(f"Retrieving chunks for file_id: {file_id}")
                seen_file_ids.add(file_id)
                
                # Get all chunks for this file
                try:
                    file_chunks = self.get_chunks_by_file_id(file_id)
                    
                    metadatas = file_chunks.get("metadatas", [])
                    documents = file_chunks.get("documents", [])

                    if not metadatas or not documents:
                        logger.warning(f"No chunks found for file_id: {file_id}")
                        # Use the original matched chunk as fallback
                        if "documents" in metadata and isinstance(metadata["documents"], str):
                            reconstructed_files[file_id] = metadata["documents"]
                            logger.info(f"Using original matched chunk as fallback for file_id: {file_id}")
                        continue

                    # Safe check for equal lengths
                    if len(metadatas) != len(documents):
                        logger.warning(f"Mismatched lengths: metadatas={len(metadatas)}, documents={len(documents)}")
                        min_len = min(len(metadatas), len(documents))
                        metadatas = metadatas[:min_len]
                        documents = documents[:min_len]
                    
                    if len(documents) == 0:
                        logger.warning(f"No valid chunks found for file_id: {file_id}")
                        continue
                        
                    logger.info(f"Retrieved {len(documents)} chunks for file_id: {file_id}")
                    
                    # Create paired entries and sort by chunk_index
                    try:
                        indexed_chunks = list(zip(metadatas, documents))
                        
                        # Check if chunk_index is present and is an integer
                        has_valid_chunk_index = all(
                            isinstance(meta.get("chunk_index"), int) or 
                            (isinstance(meta.get("chunk_index"), str) and meta.get("chunk_index", "").isdigit())
                            for meta in metadatas
                        )
                        
                        if has_valid_chunk_index:
                            # Sort by chunk_index if available
                            def get_chunk_index(pair):
                                chunk_idx = pair[0].get("chunk_index", 0)
                                if isinstance(chunk_idx, str) and chunk_idx.isdigit():
                                    return int(chunk_idx)
                                return 0 if chunk_idx is None else chunk_idx
                                
                            sorted_chunks = sorted(indexed_chunks, key=get_chunk_index)
                        else:
                            # Skip sorting if no valid chunk_index
                            logger.warning(f"No valid chunk_index found for file_id: {file_id}, using original order")
                            sorted_chunks = indexed_chunks
                        
                        # Reconstruct full text
                        chunks_text = []
                        for meta, doc in sorted_chunks:
                            if isinstance(doc, str):  # Ensure document is a string
                                chunks_text.append(doc)
                        
                        if not chunks_text:
                            logger.warning(f"No valid text chunks found for file_id: {file_id}")
                            continue
                            
                        full_text = "\n\n".join(chunks_text)
                        reconstructed_files[file_id] = full_text
                        logger.info(f"Successfully reconstructed document for file_id: {file_id} ({len(full_text)} chars)")
                        
                    except Exception as chunk_error:
                        logger.error(f"Error processing chunks for file_id {file_id}: {chunk_error}", exc_info=True)
                        # Try to use single chunk as fallback
                        if documents and isinstance(documents[0], str):
                            reconstructed_files[file_id] = documents[0]
                            logger.info(f"Using first chunk as fallback for file_id: {file_id}")
                except Exception as file_error:
                    logger.error(f"Error getting chunks for file_id {file_id}: {file_error}", exc_info=True)
            
            # If we didn't reconstruct any documents, return a basic result to prevent errors
            if not reconstructed_files and matched_metadatas:
                # Try to create a basic document from the first metadata entry
                first_meta = matched_metadatas[0]
                if isinstance(first_meta, dict):
                    first_id = first_meta.get("file_id") or first_meta.get("doc_id") or first_meta.get("id") or "unknown_document"
                    reconstructed_files[first_id] = "Document content could not be reconstructed"
                    logger.warning(f"Created placeholder content for {first_id} to prevent empty results")
            
            logger.info(f"Document recovery complete: reconstructed {len(reconstructed_files)} documents")
            return reconstructed_files
            
        except Exception as e:
            logger.error(f"Error in document recovery: {e}", exc_info=True)
            # Return a non-empty result to prevent "0" error
            if not reconstructed_files:
                reconstructed_files["unknown_document"] = "Document content could not be reconstructed"
            return reconstructed_files  # Return any documents we managed to reconstruct

