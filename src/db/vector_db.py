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
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_criteria
            )

            if return_full_documents:
                metadatas = results.get("metadatas", [[]])[0]
                full_docs = self.recover_full_documents_from_matches(metadatas)
                return {"documents": full_docs}

            logger.info(f"Found {len(results.get('documents', [[]])[0])} results for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching collection: {e}")
            raise e

    
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
        seen_file_ids = set()
        reconstructed_files = {}

        for metadata in matched_metadatas:
            file_id = metadata.get("file_id")
            if not file_id or file_id in seen_file_ids:
                continue

            seen_file_ids.add(file_id)
            file_chunks = self.get_chunks_by_file_id(file_id)

            metadatas = file_chunks.get("metadatas", [])
            documents = file_chunks.get("documents", [])

            if not metadatas or not documents:
                continue

            indexed_chunks = zip(metadatas, documents)
            sorted_chunks = sorted(indexed_chunks, key=lambda pair: pair[0].get("chunk_index", 0))
            full_text = "\n\n".join(chunk for _, chunk in sorted_chunks)
            reconstructed_files[file_id] = full_text

        return reconstructed_files

