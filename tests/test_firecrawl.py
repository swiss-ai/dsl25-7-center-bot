#!/usr/bin/env python3
"""
Test script for Firecrawl integration
"""
import os
import asyncio
import logging
from typing import Dict, Any, List
import pprint
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_firecrawl():
    """Test the Firecrawl API integration"""
    try:
        # First try importing the API version
        try:
            from firecrawl import FirecrawlApp
            print("\nFound FirecrawlApp (API version)")
            firecrawl_type = "api"
        except ImportError:
            # Then try the crawler version
            try:
                from firecrawl import Crawler
                print("\nFound Crawler (legacy version)")
                firecrawl_type = "crawler"
            except ImportError:
                print("\nNo firecrawl implementation found")
                return False
        
        # Use provided API key
        api_key = os.getenv("FIRECRAWL_API_KEY", "fc-434b6c04d3d443dfa1b25ff5182ab038")
        print(f"Using Firecrawl API key: {api_key[:5]}...{api_key[-5:]}")
        
        # Test URLs
        test_urls = [
            "https://ai.ethz.ch/",
            "https://ethz.ch/en/news-and-events/events.html"
        ]
        
        # Test based on implementation type
        if firecrawl_type == "api":
            # Initialize the Firecrawl app
            app = FirecrawlApp(api_key=api_key)
            
            for url in test_urls:
                print(f"\nTesting API scrape for URL: {url}")
                try:
                    # Perform scraping with a short timeout
                    result = app.scrape_url(url, params={"timeout": 10000})
                    
                    # Print the raw result for debugging
                    print(f"Result type: {type(result)}")
                    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
                    print(f"Result content (first 500 chars): {str(result)[:500]}...")
                    
                    # Extract and print information based on the result format
                    if result and isinstance(result, dict):
                        if 'html' in result:
                            # Parse HTML format
                            soup = BeautifulSoup(result['html'], 'html.parser')
                            title = soup.title.string if soup.title else "No title"
                            print(f"Title: {title}")
                            print(f"Content length: {len(result['html'])} bytes")
                            print(f"Status code: {result.get('statusCode', 'Unknown')}")
                            
                            # Extract text content
                            text = ""
                            for p in soup.find_all('p'):
                                text += p.get_text() + "\n"
                            
                            print(f"Sample text: {text[:200]}...")
                        
                        elif 'text' in result:
                            # Some APIs return text instead of html
                            print(f"Text content available, length: {len(result['text'])} bytes")
                            print(f"Sample: {result['text'][:200]}...")
                        
                        elif 'markdown' in result:
                            # The new API returns markdown
                            print(f"Markdown content available, length: {len(result['markdown'])} bytes")
                            print(f"Sample: {result['markdown'][:200]}...")
                            
                            if 'metadata' in result:
                                print(f"Metadata: {result['metadata']}")
                        
                        else:
                            print(f"Unknown result format, keys: {result.keys()}")
                    else:
                        print(f"Failed to get content from {url}")
                    
                except Exception as e:
                    print(f"Error scraping {url}: {e}")
            
        elif firecrawl_type == "crawler":
            # For each URL, create and test a crawler
            for url in test_urls:
                print(f"\nTesting crawler for URL: {url}")
                try:
                    # Initialize crawler
                    crawler = Crawler(
                        start_url=url,
                        max_depth=1,
                        max_pages=3,
                        respect_robots_txt=False,
                        follow_subdomains=True,
                        delay=1.0,
                        concurrency=1
                    )
                    
                    # Run the crawler asynchronously
                    print("Starting crawler...")
                    pages = asyncio.run(crawler.run())
                    
                    # Print results
                    print(f"Crawled {len(pages)} pages")
                    
                    # Print info about each page
                    for i, page in enumerate(pages):
                        if i >= 2:  # Limit to first 2 pages for brevity
                            print(f"...and {len(pages) - 2} more pages")
                            break
                            
                        print(f"\nPage {i+1}: {page.url}")
                        print(f"Status: {page.response.status_code if page.response else 'No response'}")
                        
                        if page.response and page.response.status_code == 200:
                            # Get content sample
                            content = page.response.text[:200] + "..." if page.response.text else "No content"
                            print(f"Content sample: {content}")
                    
                except Exception as e:
                    print(f"Error crawling {url}: {e}")
        
        print("\nFirecrawl test completed successfully!")
        return True
        
    except ImportError:
        print("\nFirecrawl module not properly installed or incompatible.")
        print("Please check installation with: pip install firecrawl")
        return False
    
    except Exception as e:
        print(f"\nUnexpected error during Firecrawl test: {e}")
        return False

async def test_firecrawl_manager():
    """Test the FirecrawlManager integration"""
    try:
        # Import manager
        from src.services.knowledge.datasources.firecrawl_manager import FirecrawlManager
        print("\nTesting FirecrawlManager integration")
        
        # Initialize manager
        manager = FirecrawlManager(
            config_path="/Users/em/Desktop/dsl25-7-center-bot/config/crawl_config.yaml"
        )
        
        # Print manager status
        status = manager.get_crawl_status()
        print("\nFirecrawl Manager Status:")
        for key, value in status.items():
            if key != "last_crawl_times":  # Skip verbose last crawl times
                print(f"- {key}: {value}")
        
        # Test direct URL crawl
        print("\nTesting manual URL crawl:")
        test_url = "https://ai.ethz.ch/"
        print(f"Crawling URL: {test_url}")
        
        # Run the crawl
        result = await manager.crawl_url_now(test_url)
        
        # Print results
        print("\nCrawl results:")
        print(f"Status: {result.get('status')}")
        print(f"URL: {result.get('url')}")
        print(f"Pages crawled: {result.get('pages_crawled')}")
        print(f"Pages processed: {result.get('pages_processed')}")
        
        print("\nFirecrawl Manager test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\nError testing FirecrawlManager: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n=== Firecrawl Integration Test ===")
    
    # Choose which test to run
    test_type = input("Choose test type (1=API/Crawler test, 2=Manager test): ").strip()
    
    if test_type == "2":
        # Run the manager test with asyncio
        success = asyncio.run(test_firecrawl_manager())
    else:
        # Run the API/Crawler test
        success = test_firecrawl()
    
    if success:
        print("\nTEST PASSED: Firecrawl integration works correctly!")
    else:
        print("\nTEST FAILED: Please check Firecrawl setup and dependencies.")