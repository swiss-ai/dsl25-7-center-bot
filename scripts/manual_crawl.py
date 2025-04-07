#!/usr/bin/env python3
"""
Script to manually trigger website crawling using Firecrawl
"""
import os
import sys
import asyncio
import logging
import argparse
from typing import Optional

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import necessary components
from dotenv import load_dotenv
from src.db.vector_db import VectorDB
from src.services.knowledge.document_processor import DocumentProcessor

# Load environment variables
load_dotenv()

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Manually trigger website crawling")
    parser.add_argument("--url", help="Specific URL to crawl")
    parser.add_argument("--all", action="store_true", help="Crawl all sites in config")
    parser.add_argument("--config", help="Path to crawl configuration file", 
                        default="crawl_config.yaml")
    parser.add_argument("--status", action="store_true", help="Show crawl service status")
    
    args = parser.parse_args()
    
    # Set config path in environment for the service to use
    os.environ["FIRECRAWL_CONFIG_PATH"] = args.config
    
    try:
        # Import here to handle import errors gracefully
        from src.services.knowledge.datasources.firecrawl_manager import FirecrawlManager
        
        # Initialize vector DB and document processor
        vector_db = VectorDB()
        document_processor = DocumentProcessor(vector_db=vector_db)
        
        # Initialize crawl manager
        crawl_manager = FirecrawlManager(
            config_path=args.config,
            document_processor=document_processor,
            vector_db=vector_db
        )
        
        if args.status:
            # Show service status
            status = crawl_manager.get_crawl_status()
            print("\n=== Firecrawl Service Status ===")
            for key, value in status.items():
                print(f"{key}: {value}")
            return
            
        if args.url:
            # Crawl specific URL
            print(f"\n=== Crawling URL: {args.url} ===")
            result = await crawl_manager.crawl_url_now(args.url)
            
            print("\nCrawl Result:")
            for key, value in result.items():
                if key != "details":
                    print(f"{key}: {value}")
                    
            return
            
        if args.all:
            # Crawl all sites in config
            print("\n=== Crawling All Sites ===")
            crawl_manager.refresh_config()  # Make sure we have latest config
            
            # Print sites to be crawled
            sites = crawl_manager.config.get("sites", [])
            print(f"\nFound {len(sites)} sites in configuration:")
            for i, site in enumerate(sites):
                print(f"{i+1}. {site.get('url')}")
            
            # Start crawling
            results = await crawl_manager.crawl_all_sites()
            
            # Print results summary
            print("\nCrawl Completed:")
            print(f"Total Sites: {results.get('total_sites')}")
            print(f"Success: {results.get('success_count')}")
            print(f"Errors: {results.get('error_count')}")
            
            # Print details for each site
            print("\nSite Details:")
            for detail in results.get("details", []):
                print(f"\n{detail.get('url')}")
                print(f"  Status: {detail.get('status')}")
                if detail.get('status') == 'success':
                    print(f"  Pages Crawled: {detail.get('pages_crawled')}")
                    print(f"  Pages Processed: {detail.get('pages_processed')}")
                else:
                    print(f"  Error: {detail.get('error')}")
                    
            # Check what's in the database
            print("\n=== URLs in Vector Database ===")
            results = vector_db.collection.get()
            
            # Extract URLs from metadata
            db_urls = {}
            for i, metadata in enumerate(results['metadatas']):
                if metadata.get('source') == 'web' and metadata.get('source_type') == 'firecrawl' and 'url' in metadata:
                    url = metadata['url']
                    if url not in db_urls:
                        db_urls[url] = {
                            'count': 0,
                            'title': metadata.get('title', 'No title')
                        }
                    db_urls[url]['count'] += 1
            
            for i, (url, info) in enumerate(sorted(db_urls.items())):
                print(f"{i+1}. {url}")
                print(f"   Title: {info['title']}")
                print(f"   Chunks: {info['count']}")
                
            return
            
        # If no arguments provided, show help
        parser.print_help()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        print("\nError: Firecrawl package not installed.")
        print("Please install it with: pip install firecrawl")
        return
        
    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        print(f"\nError: {str(e)}")
        return

if __name__ == "__main__":
    asyncio.run(main())