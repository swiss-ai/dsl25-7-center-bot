#!/usr/bin/env python3
"""
Script to manually sync web content from the URLs file to the vector database.
Run this script to fetch and index web content without starting the full server.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    # Import necessary components
    from db.vector_db import VectorDB
    from services.knowledge.document_processor import DocumentProcessor
    from services.mcp.web_fetch import MCPWebFetch
    from services.knowledge.web_content_sync import WebContentSyncService
    from config.settings import settings
    
    logger.info("Starting web content sync")
    
    # Initialize components
    vector_db = VectorDB(collection_name="documents")
    document_processor = DocumentProcessor(vector_db=vector_db)
    web_fetch = MCPWebFetch()
    
    # Display URL file path
    logger.info(f"Using URLs file: {settings.WEB_CONTENT_URLS_FILE}")
    
    # Initialize web content sync service
    web_content_sync = WebContentSyncService(
        document_processor=document_processor,
        web_fetch=web_fetch
    )
    
    # Count documents before sync
    doc_count_before = vector_db.count()
    logger.info(f"Documents in database before sync: {doc_count_before}")
    
    # Perform sync
    logger.info("Starting web content sync...")
    result = await web_content_sync.manual_sync()
    
    # Show result
    if result["status"] == "completed":
        logger.info(f"Sync completed: {result['success_count']} succeeded, {result['error_count']} failed")
        logger.info(f"Time taken: {result['time_taken']:.2f}s")
        
        # Show details for each URL
        for i, detail in enumerate(result.get("details", [])):
            status = "✅" if detail.get("status") == "success" else "❌"
            url = detail.get("url", "Unknown")
            if detail.get("status") == "success":
                logger.info(f"{status} {url} - Added as document {detail.get('doc_id')} with {detail.get('chunks', 0)} chunks")
            else:
                logger.info(f"{status} {url} - Error: {detail.get('error', 'Unknown error')}")
    else:
        logger.warning(f"Sync result: {result}")
    
    # Count documents after sync
    doc_count_after = vector_db.count()
    logger.info(f"Documents in database after sync: {doc_count_after}")
    logger.info(f"Added {doc_count_after - doc_count_before} new documents")
    
    # Perform a test search
    if doc_count_after > 0:
        logger.info("Performing test search...")
        results = await document_processor.search_documents(
            query="claude",
            n_results=3,
            filter_criteria={"source": "web"}
        )
        
        if results and results.get("documents") and results["documents"][0]:
            logger.info(f"Found {len(results['documents'][0])} relevant documents")
            # Show first result summary
            if results["documents"][0]:
                first_doc = results["documents"][0][0][:200] + "..."
                first_meta = results["metadatas"][0][0] if "metadatas" in results and results["metadatas"][0] else {}
                logger.info(f"First result: {first_meta.get('title', 'Untitled')} ({first_meta.get('url', 'No URL')})")
                logger.info(f"Content sample: {first_doc}")
        else:
            logger.warning("No search results found")
    
    logger.info("Web content sync process completed")

if __name__ == "__main__":
    asyncio.run(main())