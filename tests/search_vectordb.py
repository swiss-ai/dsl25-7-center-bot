#!/usr/bin/env python3
"""
Test script to search the vector database for ETH AI Center content
"""
import os
import sys
import asyncio
import logging

# Add the parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Import vector database
from src.db.vector_db import VectorDB

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def search_vector_db():
    """Search the vector database for ETH AI Center content"""
    # Initialize vector database
    vector_db = VectorDB()
    
    # Define search queries
    search_queries = [
        "ETH AI Center",
        "ETH AI Center events",
        "ETH AI Center research",
        "ETH AI Center mission",
        "ETH Zurich AI events"
    ]
    
    # Search for each query
    for query in search_queries:
        print(f"\n=== Searching for: '{query}' ===\n")
        
        try:
            # Search with filter for web source
            results = vector_db.search(
                query=query,
                n_results=3,
                filter_criteria={"source": "web"}
            )
            
            if not results or not results.get("documents") or not results["documents"][0]:
                print("No results found.")
                continue
            
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if "distances" in results else None
            
            # Display results
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                url = meta.get("url", "No URL")
                title = meta.get("title", "Untitled")
                score = distances[i] if distances else None
                
                print(f"Result {i+1}: {title}")
                print(f"URL: {url}")
                if score is not None:
                    print(f"Score: {score:.4f}")
                print(f"Content snippet: {doc[:200]}...\n")
        
        except Exception as e:
            logger.error(f"Error searching for {query}: {e}")
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(search_vector_db())