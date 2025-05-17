#!/usr/bin/env python3
import asyncio
import os
from dotenv import load_dotenv
import sys

# Add airtable directory to path
airtable_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "airtable")
sys.path.insert(0, airtable_dir)

# Import the direct search module
from direct_search import AirtableDirectSearch

async def test_search():
    # Create searcher
    searcher = AirtableDirectSearch()
    
    # Get search query from command line or use default
    query = sys.argv[1] if len(sys.argv) > 1 else "Alice"
    
    print(f"Searching Airtable for: '{query}'")
    
    # Run search
    results = await searcher.search_records(query)
    
    # Print results
    print("\nResults:")
    print(results)

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_search())