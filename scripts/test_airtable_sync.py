#!/usr/bin/env python3
"""Test script to verify Airtable sync functionality"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_sources.airtable.connector import AirtableConnector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def test_airtable_sync():
    """Test Airtable synchronization"""
    try:
        # Initialize connector
        logger.info("Initializing Airtable connector...")
        connector = AirtableConnector()
        
        # Get initial stats
        logger.info("Getting initial stats...")
        stats = connector.get_stats()
        logger.info(f"Initial stats: {stats}")
        
        # Perform sync
        logger.info("Starting Airtable sync...")
        result = await connector.sync_airtable_content()
        
        if result["status"] == "success":
            logger.info(f"Sync successful! Indexed {result['documents_indexed']} documents")
            logger.info(f"Tables indexed: {result.get('tables_indexed', {})}")
        else:
            logger.error(f"Sync failed: {result.get('message', 'Unknown error')}")
            return
        
        # Get updated stats
        logger.info("Getting updated stats...")
        stats = connector.get_stats()
        logger.info(f"Updated stats: {stats}")
        
        # Test search
        test_queries = ["project", "contact", "status"]
        
        for test_query in test_queries:
            logger.info(f"\nTesting search with query: '{test_query}'")
            search_results = connector.search(test_query, n_results=3)
            
            logger.info(f"Found {len(search_results)} results")
            for i, result in enumerate(search_results):
                logger.info(f"\nResult {i+1}:")
                logger.info(f"  Content: {result['content'][:200]}...")
                logger.info(f"  Table: {result['metadata'].get('table_name', 'Unknown')}")
                logger.info(f"  Record ID: {result['metadata'].get('record_id', 'Unknown')}")
                logger.info(f"  URL: {result['metadata'].get('airtable_url', 'No URL')}")
                logger.info(f"  Distance: {result.get('distance', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_airtable_sync())