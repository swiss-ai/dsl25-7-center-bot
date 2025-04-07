#!/usr/bin/env python3
"""
Check if URLs in web_content_urls.txt match what's actually in the vector database
"""
import os
import sys
import asyncio
import logging
from typing import Dict, List, Any, Set

# Add the parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Import necessary modules
from src.db.vector_db import VectorDB
from dotenv import load_dotenv
from src.config.settings import settings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from the configured file."""
    urls = []
    
    try:
        if not os.path.exists(file_path):
            logger.warning(f"URLs file not found: {file_path}")
            return urls
        
        with open(file_path, 'r') as f:
            for line in f:
                # Skip empty lines and comments
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        
        return urls
        
    except Exception as e:
        logger.error(f"Error reading URLs from file: {e}")
        return []

async def check_url_sync():
    """Check if URLs in web_content_urls.txt match what's in the vector database"""
    # Get URLs from file
    urls_file = settings.WEB_CONTENT_URLS_FILE
    configured_urls = read_urls_from_file(urls_file)
    
    # Initialize vector database
    db = VectorDB()
    
    # Get all documents
    try:
        # Get all documents in the collection
        results = db.collection.get()
        
        # Extract URLs from metadata
        db_urls = set()
        for metadata in results['metadatas']:
            if metadata.get('source') == 'web' and 'url' in metadata:
                db_urls.add(metadata['url'])
        
        # Print comparison
        print("\n=== URL Synchronization Check ===")
        print(f"\nURLs in {urls_file}:")
        for i, url in enumerate(configured_urls):
            print(f"{i+1}. {url}")
        
        print(f"\nURLs in vector database:")
        for i, url in enumerate(sorted(db_urls)):
            print(f"{i+1}. {url}")
        
        # Check for differences
        configured_urls_set = set(configured_urls)
        missing_in_db = configured_urls_set - db_urls
        extra_in_db = db_urls - configured_urls_set
        
        if missing_in_db:
            print("\nURLs in file but missing from database:")
            for i, url in enumerate(missing_in_db):
                print(f"{i+1}. {url}")
        
        if extra_in_db:
            print("\nURLs in database but not in file:")
            for i, url in enumerate(extra_in_db):
                print(f"{i+1}. {url}")
        
        if not missing_in_db and not extra_in_db:
            print("\nAll URLs are synchronized properly!")
        
    except Exception as e:
        logger.error(f"Error checking vector database: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(check_url_sync())