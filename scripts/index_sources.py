#!/usr/bin/env python3
"""Index content from all knowledge sources"""

import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge.aggregator import KnowledgeAggregator
from src.utils.config import load_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def index_all_sources():
    """Index content from all enabled knowledge sources"""
    config = load_config()
    aggregator = KnowledgeAggregator(config)
    
    enabled_sources = config['knowledge_sources']['enabled']
    
    for source in enabled_sources:
        try:
            logger.info(f"Indexing {source}...")
            await aggregator.index_source(source)
            logger.info(f"Successfully indexed {source}")
        except Exception as e:
            logger.error(f"Failed to index {source}: {e}")

if __name__ == "__main__":
    asyncio.run(index_all_sources())