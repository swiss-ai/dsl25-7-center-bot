#!/usr/bin/env python3
"""Test web scraper sync functionality"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_sources.web_scraper.connector import WebScraperConnector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def test_web_scraper_sync():
    """Test web scraper sync and search"""
    try:
        # Initialize connector
        logger.info("Initializing Web Scraper connector...")
        connector = WebScraperConnector()
        
        # Get initial stats
        stats = connector.get_stats()
        logger.info(f"Initial stats: {stats}")
        
        # Perform sync
        logger.info("Starting web content sync...")
        sync_result = await connector.sync_web_content()
        
        logger.info(f"Sync result: {sync_result}")
        
        if sync_result["status"] == "success":
            logger.info(f"Successfully synced {sync_result['synced_count']} URLs")
            logger.info(f"Total documents indexed: {sync_result.get('total_documents', 'N/A')}")
            
            # Test search
            test_queries = [
                "AI research",
                "ETH publications", 
                "machine learning",
                "artificial intelligence"
            ]
            
            for query in test_queries:
                logger.info(f"\nSearching for: '{query}'")
                results = connector.search(query, n_results=3)
                
                if results:
                    logger.info(f"Found {len(results)} results:")
                    for i, result in enumerate(results):
                        metadata = result.get("metadata", {})
                        content_preview = result.get("content", "")[:200]
                        logger.info(f"\n[{i+1}] Title: {metadata.get('title', 'N/A')}")
                        logger.info(f"    URL: {metadata.get('web_url', 'N/A')}")
                        logger.info(f"    Type: {metadata.get('content_type', 'N/A')}")
                        logger.info(f"    Content: {content_preview}...")
                else:
                    logger.info("No results found")
            
            # Get final stats
            final_stats = connector.get_stats()
            logger.info(f"\nFinal stats: {final_stats}")
            
        else:
            logger.error(f"Sync failed: {sync_result.get('message', 'Unknown error')}")
            if sync_result.get("errors"):
                for error in sync_result["errors"]:
                    logger.error(f"  - {error['url']}: {error['error']}")
                    
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_web_scraper_sync())