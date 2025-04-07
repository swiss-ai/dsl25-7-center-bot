#!/usr/bin/env python3
"""
Script to search the vector database for specific content
"""
import os
import sys
import argparse

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import vector database
from src.db.vector_db import VectorDB

def main():
    """Search the vector database"""
    parser = argparse.ArgumentParser(description="Search the vector database")
    parser.add_argument("query", help="The search query")
    parser.add_argument("--n", type=int, default=3, help="Number of results to return")
    parser.add_argument("--source", help="Filter by source (e.g., 'web')")
    parser.add_argument("--source_type", help="Filter by source type (e.g., 'firecrawl')")
    parser.add_argument("--url", help="Filter by URL")
    
    args = parser.parse_args()
    
    # Initialize vector database
    db = VectorDB()
    
    # Prepare filter criteria
    filter_criteria = {}
    if args.source:
        filter_criteria["source"] = args.source
    if args.source_type:
        filter_criteria["source_type"] = args.source_type
    if args.url:
        filter_criteria["url"] = args.url
    
    print(f"\nSearching for: '{args.query}'")
    if filter_criteria:
        print(f"Filters: {filter_criteria}")
    
    # Search
    results = db.search(
        query=args.query,
        n_results=args.n,
        filter_criteria=filter_criteria or None
    )
    
    # Display results
    if not results or not results.get("documents") or not results["documents"][0]:
        print("\nNo results found.")
        return
    
    print(f"\nFound {len(results['documents'][0])} results:")
    
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        print(f"\nResult {i+1}:")
        print(f"URL: {meta.get('url', 'No URL')}")
        print(f"Title: {meta.get('title', 'No title')}")
        print(f"Source type: {meta.get('source_type', 'Unknown')}")
        
        # Display content snippet
        if len(doc) > 300:
            print(f"Content: {doc[:300]}...\n")
        else:
            print(f"Content: {doc}\n")

if __name__ == "__main__":
    # If no arguments, provide help
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    main()