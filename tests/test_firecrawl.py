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
        from firecrawl import FirecrawlApp
        
        # Use provided API key
        api_key = os.getenv("FIRECRAWL_API_KEY", "fc-434b6c04d3d443dfa1b25ff5182ab038")
        print(f"\nUsing Firecrawl API key: {api_key[:5]}...{api_key[-5:]}")
            
        # Initialize the Firecrawl app
        app = FirecrawlApp(api_key=api_key)
        
        # Test URL scraping
        test_urls = [
            "https://ai.ethz.ch/",
            "https://ethz.ch/en/news-and-events/events.html"
        ]
        
        for url in test_urls:
            print(f"\nTesting scrape for URL: {url}")
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
        
        print("\nFirecrawl test completed successfully!")
        return True
        
    except ImportError:
        print("\nFirecrawl module not properly installed or incompatible.")
        print("Please check installation with: pip install firecrawl")
        return False
    
    except Exception as e:
        print(f"\nUnexpected error during Firecrawl test: {e}")
        return False

if __name__ == "__main__":
    print("\n=== Firecrawl Integration Test ===")
    success = test_firecrawl()
    
    if success:
        print("\nTEST PASSED: Firecrawl integration works correctly!")
    else:
        print("\nTEST FAILED: Please check Firecrawl setup and dependencies.")