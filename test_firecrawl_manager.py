#!/usr/bin/env python3
"""
Test script for Firecrawl Manager
This script directly tests the FirecrawlManager component without needing to run the full application.
"""

import os
import sys
import asyncio
import logging
from pprint import pprint
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Ensure the module can be found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def test_manager():
    """Test the FirecrawlManager directly"""
    try:
        # Try different import paths since project structure might vary
        try:
            from src.services.knowledge.datasources.firecrawl_manager import FirecrawlManager
            logger.info("Successfully imported FirecrawlManager from src.services path")
        except ImportError:
            try:
                from services.knowledge.datasources.firecrawl_manager import FirecrawlManager
                logger.info("Successfully imported FirecrawlManager from services path")
            except ImportError:
                # Try dynamically loading the module from file path
                import importlib.util
                file_path = os.path.join(
                    os.path.dirname(__file__), 
                    "src/services/knowledge/datasources/firecrawl_manager.py"
                )
                logger.info(f"Trying to load module from file: {file_path}")
                
                if os.path.exists(file_path):
                    spec = importlib.util.spec_from_file_location("firecrawl_manager", file_path)
                    firecrawl_manager = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(firecrawl_manager)
                    FirecrawlManager = firecrawl_manager.FirecrawlManager
                    logger.info("Successfully loaded FirecrawlManager from file")
                else:
                    raise ImportError(f"Module file not found: {file_path}")
        
        # Create a simple test document processor
        class SimpleDocProcessor:
            async def process_document(self, content, metadata, chunk_size=500, chunk_overlap=50):
                logger.info(f"Processing document: {metadata.get('title')} ({len(content)} chars)")
                logger.info(f"Metadata: {metadata}")
                return ["chunk1", "chunk2"]  # Return fake chunk IDs
                
        # Create a mock VectorDB class if needed
        class MockVectorDB:
            def __init__(self, collection_name=None):
                self.collection_name = collection_name or "test_collection"
                
            def add_documents(self, documents, metadatas=None):
                logger.info(f"Adding {len(documents)} documents to vector DB")
                return [f"id{i}" for i in range(len(documents))]
                
            def count(self):
                return 0
        
        # Initialize manager with config and doc processor
        config_path = os.path.join(os.path.dirname(__file__), "config/crawl_config.yaml")
        logger.info(f"Using config file: {config_path}")
        
        manager = FirecrawlManager(
            config_path=config_path,
            document_processor=SimpleDocProcessor(),
            vector_db=MockVectorDB()
        )
        
        # Get and print status
        status = manager.get_crawl_status()
        print("\nFirecrawl Manager Status:")
        pprint(status)
        
        # Test crawling a specific URL
        if status.get("firecrawl_available", False):
            print("\nTesting URL crawl...")
            result = await manager.crawl_url_now("https://ai.ethz.ch/")
            print("\nCrawl Result:")
            pprint(result)
        else:
            print("\nSkipping crawl test as Firecrawl is not available")
            
        # Test loading and printing config
        config = manager._load_config()
        print("\nLoaded configuration:")
        print(f"Global settings: {config.get('global', {})}")
        print(f"Sites configured: {len(config.get('sites', []))}")
        
        return True
    
    except ImportError as e:
        logger.error(f"Error importing required modules: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Error testing FirecrawlManager: {e}")
        import traceback
        traceback.print_exc()
        return False
        
if __name__ == "__main__":
    print("\n=== Testing Firecrawl Manager ===\n")
    success = asyncio.run(test_manager())
    
    if success:
        print("\nTEST COMPLETE: Manager functionality tested")
    else:
        print("\nTEST FAILED: Please check the error logs")