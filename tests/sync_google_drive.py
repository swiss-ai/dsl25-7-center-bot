#!/usr/bin/env python3
"""
Test script to sync Google Drive documents to ChromaDB.
This script can be run independently to test Google Drive integration.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Add src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import project modules
from src.db.vector_db import VectorDB
from src.services.knowledge.document_processor import DocumentProcessor
from src.services.knowledge.datasources.gdrive import GoogleDriveManager

async def sync_drive_to_vectordb(
    credentials_path, 
    token_path, 
    sync_file="gdrive_last_sync.json",
    collection_name="test_documents",
    max_files=10,
    specific_file_id=None
):
    """
    Sync Google Drive documents to a test ChromaDB collection.
    
    Args:
        credentials_path: Path to Google API credentials
        token_path: Path to Google OAuth token
        sync_file: Path to file tracking synced documents
        collection_name: Name of the ChromaDB collection to use
        max_files: Maximum number of files to sync
        specific_file_id: Sync only this specific file ID if provided
    """
    logger.info("Initializing test environment")
    
    # Create test vector database
    test_db_path = Path(__file__).parent / "test_chroma_db"
    test_db_path.mkdir(exist_ok=True)
    
    # Initialize vector DB with test collection
    vector_db = VectorDB(
        collection_name=collection_name,
        persist_directory=str(test_db_path)
    )
    
    # Initialize document processor
    document_processor = DocumentProcessor(vector_db=vector_db)
    
    # Initialize Google Drive manager
    gdrive_manager = GoogleDriveManager(
        document_processor=document_processor,
        vector_db=vector_db,
        credentials_path=credentials_path,
        token_path=token_path,
        sync_file=sync_file
    )
    
    # Check if Google Drive is authenticated
    if not gdrive_manager.service:
        logger.error("Google Drive authentication failed")
        return False
    
    logger.info("Google Drive authentication successful")
    
    # Sync specific file or all files
    if specific_file_id:
        logger.info(f"Syncing specific file: {specific_file_id}")
        success = await gdrive_manager.process_file_to_vector_db(specific_file_id)
        if success:
            logger.info(f"Successfully synced file {specific_file_id}")
        else:
            logger.error(f"Failed to sync file {specific_file_id}")
        return success
    else:
        # Sync recent files
        logger.info(f"Syncing up to {max_files} recent files")
        synced_count = await gdrive_manager.sync_recent_files(max_files=max_files)
        logger.info(f"Synced {synced_count} files")
        return synced_count > 0

async def search_documents(vector_db, query, limit=5):
    """
    Search for documents in the vector database.
    
    Args:
        vector_db: Vector database instance
        query: Search query
        limit: Maximum number of results
        
    Returns:
        List of search results
    """
    try:
        # Directly use vector_db search to avoid document_processor issues
        results = vector_db.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        # Format results
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0] if "distances" in results else []
        
        formatted_results = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            formatted_result = {
                "content": doc[:200] + "..." if len(doc) > 200 else doc,
                "metadata": meta,
                "score": distances[i] if i < len(distances) else None
            }
            formatted_results.append(formatted_result)
            
        return formatted_results
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []

async def main():
    # Get credentials from environment or use default paths
    credentials_path = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", 
        "/home/dsl25-7-center-bot/config/credentials/credentials.json"
    )
    token_path = os.getenv(
        "GOOGLE_TOKEN_PATH", 
        "/home/dsl25-7-center-bot/config/credentials/token.json"
    )
    
    # Check if credentials exist
    if not os.path.exists(credentials_path):
        logger.error(f"Google credentials file not found: {credentials_path}")
        return
    
    if not os.path.exists(token_path):
        logger.error(f"Google token file not found: {token_path}")
        return
    
    # Initialize test database
    test_db_path = Path(__file__).parent / "test_chroma_db"
    vector_db = VectorDB(
        collection_name="test_documents",
        persist_directory=str(test_db_path)
    )
    
    # Sync files from Google Drive
    sync_success = await sync_drive_to_vectordb(
        credentials_path=credentials_path,
        token_path=token_path,
        collection_name="test_documents",
        max_files=5
    )
    
    if sync_success:
        # Count documents
        doc_count = vector_db.count()
        logger.info(f"Vector database contains {doc_count} document chunks")
        
        # Test search
        if doc_count > 0:
            logger.info("Testing search functionality")
            search_results = await search_documents(vector_db, "test", limit=5)
            
            logger.info(f"Found {len(search_results)} results")
            for i, result in enumerate(search_results):
                logger.info(f"Result {i+1}:")
                logger.info(f"  Content: {result['content']}")
                logger.info(f"  Metadata: {json.dumps(result['metadata'], indent=2)}")
                logger.info(f"  Score: {result['score']}")
    else:
        logger.error("Sync failed")

if __name__ == "__main__":
    asyncio.run(main())