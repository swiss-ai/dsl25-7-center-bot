#!/usr/bin/env python3
"""
Manual web content sync script
"""
import asyncio
import sys
import os
import logging

# Add the project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import settings
from src.db.vector_db import VectorDB
from src.db.init_db import init_db
from src.services.knowledge.document_processor import DocumentProcessor
from src.services.knowledge.web_content_sync import WebContentSyncService
from src.services.mcp.web_fetch import MCPWebFetch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def manual_sync():
    """Manually trigger web content sync"""
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        
        # Initialize components
        logger.info("Initializing components...")
        vector_db = VectorDB()
        document_processor = DocumentProcessor(vector_db=vector_db)
        web_fetch = MCPWebFetch()
        
        # Initialize sync service
        web_content_sync = WebContentSyncService(
            document_processor=document_processor,
            web_fetch=web_fetch
        )
        
        # Read current URLs
        urls = web_content_sync.read_urls_from_file()
        logger.info(f"Found {len(urls)} URLs to sync")
        
        # Perform sync
        logger.info("Starting manual sync...")
        result = await web_content_sync.manual_sync()
        
        # Print results
        logger.info(f"Sync completed:")
        logger.info(f"  Total URLs: {result['total_urls']}")
        logger.info(f"  Success: {result['success_count']}")
        logger.info(f"  Errors: {result['error_count']}")
        logger.info(f"  Time taken: {result['time_taken']:.2f}s")
        
        # Print any errors
        if result['error_count'] > 0:
            logger.error("Errors encountered:")
            for detail in result['details']:
                if detail['status'] == 'error':
                    logger.error(f"  {detail['url']}: {detail['error']}")
    
    except Exception as e:
        logger.error(f"Error during manual sync: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(manual_sync())