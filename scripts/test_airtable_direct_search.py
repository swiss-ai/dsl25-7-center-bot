#!/usr/bin/env python3
"""Test script to verify Airtable direct search with deduplication"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_sources.airtable.connector import AirtableConnector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def test_direct_search():
    """Test Airtable direct search with deduplication"""
    try:
        # Initialize connector
        logger.info("Initializing Airtable connector...")
        connector = AirtableConnector()
        
        # Test queries
        test_queries = ["course", "robotics", "Dr."]
        
        for query in test_queries:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing query: '{query}'")
            logger.info(f"{'='*60}")
            
            # Get both cached and direct results
            cached_results, direct_results = connector.search_with_deduplication(query, n_results=3)
            
            logger.info(f"\nCACHED RESULTS ({len(cached_results)} found):")
            for i, result in enumerate(cached_results):
                logger.info(f"\n--- Cached Result {i+1} ---")
                logger.info(f"Table: {result['metadata'].get('table_name')}")
                logger.info(f"Record: {result['metadata'].get('record_id')}")
                logger.info(f"Content preview: {result['content'][:100]}...")
                
            logger.info(f"\nDIRECT API RESULTS ({len(direct_results)} found):")
            for i, result in enumerate(direct_results):
                is_duplicate = result['metadata'].get('is_duplicate', False)
                logger.info(f"\n--- Direct Result {i+1} {'[DUPLICATE]' if is_duplicate else '[NEW]'} ---")
                logger.info(f"Table: {result['metadata'].get('table_name')}")
                logger.info(f"Record: {result['metadata'].get('record_id')}")
                logger.info(f"Is Duplicate: {is_duplicate}")
                if not is_duplicate:
                    logger.info(f"Content preview: {result['content'][:100]}...")
                
            # Summary
            duplicate_count = sum(1 for r in direct_results if r['metadata'].get('is_duplicate', False))
            new_count = len(direct_results) - duplicate_count
            
            logger.info(f"\nSUMMARY:")
            logger.info(f"- Cached results: {len(cached_results)}")
            logger.info(f"- Direct results: {len(direct_results)}")
            logger.info(f"  - New/Updated: {new_count}")
            logger.info(f"  - Duplicates: {duplicate_count}")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_search())