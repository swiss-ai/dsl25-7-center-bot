#!/usr/bin/env python3
"""
Diagnostic script for Google Drive integration with ChromaDB
This script helps diagnose and fix issues with Google Drive sync functionality
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from pprint import pprint
import traceback

# Add the parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import project modules
from src.db.vector_db import VectorDB
from src.services.knowledge.document_processor import DocumentProcessor
from src.services.knowledge.datasources.gdrive import GoogleDriveManager
from config.settings import settings

async def list_all_gdrive_files():
    """List all available Google Drive files"""
    # Initialize Google Drive manager
    gdrive_manager = GoogleDriveManager(
        credentials_path=settings.GOOGLE_CREDENTIALS_PATH,
        token_path=settings.GOOGLE_TOKEN_PATH
    )
    
    # Check if Google Drive is authenticated
    if not gdrive_manager.service:
        logger.error("Google Drive authentication failed")
        return
    
    logger.info("Looking for supported files in Google Drive")
    
    # Build a query for supported file types
    mime_types = list(gdrive_manager.SUPPORTED_MIME_TYPES.keys())
    mime_types_query = " or ".join([f"mimeType='{mime}'" for mime in mime_types])
    query = f"({mime_types_query}) and trashed=false"
    
    try:
        # Get all files sorted by most recently modified
        files = await gdrive_manager.list_files(
            query=query,
            order_by="modifiedTime desc"
        )
        
        logger.info(f"Found {len(files)} Google Drive files that can be indexed")
        
        # Print file details
        for i, file in enumerate(files[:10]):  # Only show first 10
            print(f"{i+1}. {file.get('name')} ({file.get('mimeType')})")
            print(f"   ID: {file.get('id')}")
            print(f"   Modified: {file.get('modifiedTime')}")
            print(f"   URL: {file.get('webViewLink', 'N/A')}")
            print()
        
        # Return file information
        return files
    except Exception as e:
        logger.error(f"Error listing Google Drive files: {e}")
        traceback.print_exc()
        return []

async def check_sync_status():
    """Check the current sync status with the tracking file"""
    sync_file = settings.GOOGLE_DRIVE_SYNC_FILE or "gdrive_last_sync.json"
    
    if os.path.exists(sync_file):
        try:
            with open(sync_file, 'r') as f:
                synced_files = json.load(f)
            
            logger.info(f"Found {len(synced_files)} files in the sync tracking file")
            print(f"Sync tracking file: {sync_file}\n")
            
            # Show most recently synced files
            print("Most recently synced files:")
            sorted_files = sorted(synced_files.items(), key=lambda x: x[1], reverse=True)
            for file_id, mod_time in sorted_files[:5]:
                print(f"File ID: {file_id}")
                print(f"Last Synced: {mod_time}")
                print()
            
            return synced_files
        except Exception as e:
            logger.error(f"Error loading synced files tracking: {e}")
            return {}
    else:
        logger.warning(f"Sync tracking file not found: {sync_file}")
        return {}

async def sync_specific_file(file_id):
    """Sync a specific file from Google Drive to the vector database"""
    # Initialize vector database
    vector_db = VectorDB()
    
    # Initialize document processor
    document_processor = DocumentProcessor(vector_db=vector_db)
    
    # Initialize Google Drive manager
    gdrive_manager = GoogleDriveManager(
        document_processor=document_processor,
        vector_db=vector_db,
        credentials_path=settings.GOOGLE_CREDENTIALS_PATH,
        token_path=settings.GOOGLE_TOKEN_PATH
    )
    
    # Check if Google Drive is authenticated
    if not gdrive_manager.service:
        logger.error("Google Drive authentication failed")
        return False
    
    logger.info(f"Attempting to sync file with ID: {file_id}")
    
    try:
        # Get file metadata first
        loop = asyncio.get_event_loop()
        file_request = gdrive_manager.service.files().get(
            fileId=file_id, 
            fields="id, name, mimeType, description, modifiedTime, webViewLink"
        )
        file_metadata = await loop.run_in_executor(None, file_request.execute)
        
        print(f"File metadata:\n{json.dumps(file_metadata, indent=2)}\n")
        
        # Check if file type is supported
        mime_type = file_metadata.get('mimeType')
        if mime_type not in gdrive_manager.SUPPORTED_MIME_TYPES:
            logger.error(f"Unsupported MIME type: {mime_type}")
            return False
        
        # Get and print the content
        logger.info(f"Extracting content from file: {file_metadata.get('name')}")
        content, _ = await gdrive_manager.get_file_content(file_id, file_metadata)
        
        # Print content preview
        content_preview = content[:500] + "..." if len(content) > 500 else content
        print(f"Content preview:\n{content_preview}\n")
        
        # Process file to vector DB
        success = await gdrive_manager.process_file_to_vector_db(file_id, file_metadata)
        
        if success:
            logger.info(f"Successfully synced file {file_id} to vector database")
        else:
            logger.error(f"Failed to sync file {file_id} to vector database")
        
        return success
    
    except Exception as e:
        logger.error(f"Error syncing file {file_id}: {e}")
        traceback.print_exc()
        return False

async def diagnose_vector_database():
    """Diagnose the vector database for Google Drive documents"""
    # Initialize vector database
    vector_db = VectorDB()
    
    # Check document count
    count = vector_db.count()
    logger.info(f"Vector database contains {count} document chunks")
    
    # Get all documents
    try:
        results = vector_db.collection.get()
        
        # Group by file_id
        file_chunks = {}
        
        for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
            file_id = meta.get("file_id", "unknown")
            
            if file_id not in file_chunks:
                file_chunks[file_id] = {
                    "chunks": [],
                    "metadata": meta,
                    "chunk_count": 0
                }
            
            # Add this chunk
            file_chunks[file_id]["chunks"].append(doc)
            file_chunks[file_id]["chunk_count"] += 1
        
        # Print document statistics
        print(f"\nFound {len(file_chunks)} unique documents in vector database")
        
        for file_id, data in file_chunks.items():
            meta = data["metadata"]
            print(f"\nDocument: {meta.get('title', 'Untitled')}")
            print(f"Source: {meta.get('source', 'Unknown')}")
            print(f"File ID: {file_id}")
            print(f"Chunks: {data['chunk_count']}")
            
            if "source" in meta and meta["source"] == "google_drive":
                print("File Type: Google Drive document")
                print(f"URL: {meta.get('url', 'N/A')}")
        
        # Test search on Google Drive documents
        print("\n--- Testing search for Google Drive documents ---")
        results = vector_db.search(
            query="test", 
            n_results=3,
            filter_criteria={"source": "google_drive"}
        )
        
        # Print search results
        if not results or not results.get("documents") or not results["documents"][0]:
            print("No search results found for Google Drive documents.")
        else:
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if "distances" in results else None
            
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                print(f"\nResult {i+1}:")
                print(f"Title: {meta.get('title', 'Untitled')}")
                print(f"File ID: {meta.get('file_id', 'Unknown')}")
                print(f"Score: {distances[i] if distances else 'N/A'}")
                print(f"Content: {doc[:200]}...")
        
        return file_chunks
    
    except Exception as e:
        logger.error(f"Error diagnosing vector database: {e}")
        traceback.print_exc()
        return {}

async def test_document_processor_search():
    """Test the document processor search functionality"""
    # Initialize vector database
    vector_db = VectorDB()
    
    # Initialize document processor
    document_processor = DocumentProcessor(vector_db=vector_db)
    
    print("\n--- Testing document processor search ---")
    
    try:
        # Perform the search
        results = await document_processor.search_documents(
            query="test",
            n_results=3
        )
        
        print(f"Search results type: {type(results)}")
        print(f"Search results: {results}")
        
        # Format and print results
        formatted = document_processor.format_search_results(results)
        print(f"\nFormatted search results:\n{formatted}")
        
        return True
    except Exception as e:
        logger.error(f"Error in document processor search: {e}")
        traceback.print_exc()
        return False

async def main():
    """Run all diagnostic tests"""
    print("\n=== Google Drive Integration Diagnostic Tool ===\n")
    
    # Check settings
    print(f"Google Drive Enabled: {settings.GOOGLE_DRIVE_ENABLED}")
    print(f"Credentials Path: {settings.GOOGLE_CREDENTIALS_PATH}")
    print(f"Token Path: {settings.GOOGLE_TOKEN_PATH}")
    print(f"Max Files per Sync: {settings.GOOGLE_DRIVE_MAX_FILES}")
    print(f"Sync Tracking File: {settings.GOOGLE_DRIVE_SYNC_FILE or 'gdrive_last_sync.json'}")
    
    # Make sure credentials exist
    if not (settings.GOOGLE_CREDENTIALS_PATH and os.path.exists(settings.GOOGLE_CREDENTIALS_PATH)):
        logger.error(f"Google credentials file not found: {settings.GOOGLE_CREDENTIALS_PATH}")
        return
    
    if not (settings.GOOGLE_TOKEN_PATH and os.path.exists(settings.GOOGLE_TOKEN_PATH)):
        logger.error(f"Google token file not found: {settings.GOOGLE_TOKEN_PATH}")
        return
    
    # 1. Check sync tracking file
    print("\n--- Checking sync tracking file ---")
    await check_sync_status()
    
    # 2. List Google Drive files
    print("\n--- Listing Google Drive files ---")
    files = await list_all_gdrive_files()
    
    # 3. Diagnose vector database
    print("\n--- Diagnosing vector database ---")
    await diagnose_vector_database()
    
    # 4. Test document processor search
    print("\n--- Testing document processor search ---")
    await test_document_processor_search()
    
    # 5. Sync a specific file if Google Drive files were found
    if files and len(files) > 0:
        file_id = files[0]['id']  # Use the first file
        print(f"\n--- Syncing file {files[0]['name']} ---")
        await sync_specific_file(file_id)
    
    print("\n=== Diagnostic tests completed ===")

if __name__ == "__main__":
    asyncio.run(main())