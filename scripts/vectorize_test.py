#!/usr/bin/env python3
"""
Test script to fetch a URL with Firecrawl and add it to the vector database
"""
import os
import sys
import asyncio
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Import our classes
from src.db.vector_db import VectorDB

async def main():
    """Main function."""
    print("\n=== Firecrawl Vectorization Test ===")
    
    # Initialize vector database
    vector_db = VectorDB()
    
    # Check if Firecrawl is available
    try:
        from firecrawl import FirecrawlApp
        
        # Use API key
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            print("ERROR: No FIRECRAWL_API_KEY found in environment")
            return
        
        print(f"Using Firecrawl API key: {api_key[:5]}...{api_key[-5:]}")
        
        # Initialize Firecrawl
        app = FirecrawlApp(api_key=api_key)
        
        # Test URL
        url = "https://ai.ethz.ch/"
        print(f"\nFetching content from: {url}")
        
        # Fetch content
        result = app.scrape_url(url, params={"timeout": 10000})
        
        if not result or not isinstance(result, dict) or 'markdown' not in result:
            print("Error: Failed to get markdown content")
            return
        
        print(f"Content fetched successfully ({len(result['markdown'])} bytes)")
        
        # Prepare for vectorization
        doc_id = f"web_{uuid.uuid4()}"
        content = result['markdown']
        
        # Get title from metadata
        title = result['metadata'].get('title', 'No title')
        print(f"Page title: {title}")
        
        # Prepare metadata
        metadata = {
            "doc_id": doc_id,
            "source": "web",
            "source_type": "firecrawl",
            "url": url,
            "title": title,
            "crawled_at": datetime.now().isoformat(),
            "content_type": "markdown"
        }
        
        # Process the document into chunks
        print("\nChunking document...")
        chunks, chunk_metadatas = chunk_document(content, metadata)
        print(f"Document split into {len(chunks)} chunks")
        
        # Add to vector database
        print("\nAdding to vector database...")
        chunk_ids = vector_db.add_documents(
            documents=chunks,
            metadatas=chunk_metadatas
        )
        
        print(f"Added {len(chunk_ids)} chunks to vector database")
        
        # Test a search
        print("\nTesting search...")
        query = "ETH AI Center research"
        results = vector_db.search(
            query=query,
            n_results=2,
            filter_criteria={"source_type": "firecrawl"}
        )
        
        # Display results
        if results and "documents" in results and results["documents"] and results["documents"][0]:
            print(f"Found {len(results['documents'][0])} results for query: '{query}'")
            for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                print(f"\nResult {i+1}:")
                print(f"URL: {meta.get('url', 'No URL')}")
                print(f"Title: {meta.get('title', 'No title')}")
                print(f"Sample content: {doc[:100]}...")
        else:
            print("No search results found")
        
        print("\nVectorization test completed successfully!")
        
    except ImportError:
        print("Error: Firecrawl package not available")
    except Exception as e:
        print(f"Error during test: {e}")

def chunk_document(content: str, metadata: Dict[str, Any], chunk_size: int = 500, chunk_overlap: int = 50):
    """Split a document into overlapping chunks."""
    import re
    # Split on paragraphs first, then by size
    paragraphs = re.split(r'\n\s*\n', content)
    
    chunks = []
    chunk_metadatas = []
    current_chunk = ""
    
    for i, para in enumerate(paragraphs):
        # If adding this paragraph would exceed chunk size, save current chunk and start a new one
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            
            # Create metadata for this chunk
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_id"] = f"{metadata['doc_id']}_{len(chunks)}"
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadatas.append(chunk_metadata)
            
            # Start new chunk with overlap
            words = current_chunk.split()
            overlap_words = words[-min(chunk_overlap, len(words)):]
            current_chunk = " ".join(overlap_words)
        
        # Add paragraph to current chunk
        if current_chunk:
            current_chunk += "\n\n" + para
        else:
            current_chunk = para
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
        chunk_metadata = metadata.copy()
        chunk_metadata["chunk_id"] = f"{metadata['doc_id']}_{len(chunks)}"
        chunk_metadata["chunk_index"] = len(chunks)
        chunk_metadatas.append(chunk_metadata)
    
    return chunks, chunk_metadatas

if __name__ == "__main__":
    asyncio.run(main())