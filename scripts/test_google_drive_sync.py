#!/usr/bin/env python3
"""Test Google Drive sync functionality"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_sources.google_drive.connector import GoogleDriveConnector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def test_google_drive_sync():
    """Test Google Drive sync and search"""
    try:
        # Initialize connector
        logger.info("Initializing Google Drive connector...")
        connector = GoogleDriveConnector()
        
        # Get initial stats
        stats = connector.get_stats()
        logger.info(f"Initial stats: {stats}")
        
        # Check if credentials exist
        creds_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'knowledge_sources', 'google_drive', 'v1', 'credentials.json')
        if not os.path.exists(creds_path):
            logger.error(f"Google Drive credentials not found at: {creds_path}")
            logger.info("\nTo set up Google Drive integration:")
            logger.info("1. Go to https://console.cloud.google.com/")
            logger.info("2. Create a project and enable Google Drive API")
            logger.info("3. Create OAuth 2.0 credentials (Desktop App)")
            logger.info("4. Download credentials.json and place it in:")
            logger.info(f"   {creds_path}")
            return
        
        # Perform sync
        logger.info("Starting Google Drive sync...")
        sync_result = await connector.sync_google_drive_content()
        
        logger.info(f"Sync result: {sync_result}")
        
        if sync_result["status"] == "success":
            logger.info(f"Successfully synced {sync_result.get('files_processed', 0)} files")
            logger.info(f"Total documents indexed: {sync_result.get('documents_indexed', 0)}")
            
            # Test search if documents were indexed
            if sync_result.get('documents_indexed', 0) > 0:
                test_queries = [
                    "project",
                    "meeting notes", 
                    "report",
                    "analysis"
                ]
                
                for query in test_queries:
                    logger.info(f"\nSearching for: '{query}'")
                    results = connector.search(query, n_results=3)
                    
                    if results:
                        logger.info(f"Found {len(results)} results:")
                        for i, result in enumerate(results):
                            metadata = result.get("metadata", {})
                            content_preview = result.get("content", "")[:200]
                            logger.info(f"\n[{i+1}] File: {metadata.get('file_name', 'N/A')}")
                            logger.info(f"    Type: {metadata.get('file_type', 'N/A')}")
                            logger.info(f"    URL: {metadata.get('google_drive_url', 'N/A')}")
                            logger.info(f"    Chunk: {metadata.get('chunk_index', 0)+1}/{metadata.get('total_chunks', 1)}")
                            logger.info(f"    Content: {content_preview}...")
                    else:
                        logger.info("No results found")
            else:
                logger.info("\nNo documents were indexed. Make sure you have files in your Google Drive.")
            
            # Get final stats
            final_stats = connector.get_stats()
            logger.info(f"\nFinal stats: {final_stats}")
            
        else:
            logger.error(f"Sync failed: {sync_result.get('message', 'Unknown error')}")
            if sync_result.get("errors"):
                for error in sync_result["errors"]:
                    logger.error(f"  - {error['file']}: {error['error']}")
                    
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_google_drive_sync())