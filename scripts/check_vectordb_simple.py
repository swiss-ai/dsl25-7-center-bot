#!/usr/bin/env python3
"""
Simple script to check what URLs are in the vector database
"""
import os
import sys
from collections import defaultdict

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import vector database
from src.db.vector_db import VectorDB

def main():
    """Check URLs in vector database"""
    # Initialize vector database
    db = VectorDB()
    
    # Get total count
    count = db.count()
    print(f"\nTotal documents in vector database: {count}")
    
    # Get all documents
    try:
        results = db.collection.get()
        
        # Group by URL and source type
        url_counts = defaultdict(lambda: defaultdict(int))
        source_types = set()
        sources = set()
        
        for metadata in results['metadatas']:
            url = metadata.get('url', 'No URL')
            source = metadata.get('source', 'Unknown')
            source_type = metadata.get('source_type', 'Unknown')
            
            url_counts[url][source_type] += 1
            source_types.add(source_type)
            sources.add(source)
        
        # Print summary
        print(f"\nFound {len(url_counts)} unique URLs")
        print(f"Source types: {', '.join(source_types)}")
        print(f"Sources: {', '.join(sources)}")
        
        # Print URLs grouped by source type
        print("\nURLs in vector database:")
        for i, (url, type_counts) in enumerate(sorted(url_counts.items())):
            type_str = ", ".join([f"{type_name}: {count}" for type_name, count in type_counts.items()])
            print(f"{i+1}. {url} ({type_str})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()