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
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_criteria
            )
            
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