import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from src.utils.logger import setup_logger
import os

logger = setup_logger(__name__)

class ChromaDBClient:
    def __init__(self, persist_directory: str = "./data/chroma"):
        """Initialize ChromaDB client with persistence"""
        self.persist_directory = persist_directory
        
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        logger.info(f"ChromaDB client initialized with persist directory: {persist_directory}")
    
    def get_or_create_collection(self, 
                                collection_name: str, 
                                embedding_function=None,
                                metadata: Dict[str, Any] = None) -> chromadb.Collection:
        """Get or create a collection"""
        try:
            # Try to get existing collection
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=embedding_function
            )
            logger.info(f"Retrieved existing collection: {collection_name}")
        except:
            # Create new collection if it doesn't exist
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=embedding_function,
                metadata=metadata or {}
            )
            logger.info(f"Created new collection: {collection_name}")
        
        return collection
    
    def delete_collection(self, collection_name: str):
        """Delete a collection"""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
    
    def list_collections(self) -> List[str]:
        """List all collections"""
        collections = self.client.list_collections()
        return [col.name for col in collections]
    
    def get_collection_count(self, collection_name: str) -> int:
        """Get document count in a collection"""
        try:
            collection = self.client.get_collection(collection_name)
            return collection.count()
        except Exception as e:
            logger.error(f"Error getting count for collection {collection_name}: {e}")
            return 0