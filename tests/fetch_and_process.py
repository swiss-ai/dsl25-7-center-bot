#!/usr/bin/env python3
"""
Script to manually fetch and process URLs from web_content_urls.txt
"""
import os
import sys
import asyncio
import logging
import uuid
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Import vector database
from src.db.vector_db import VectorDB

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to URL file
URLS_FILE = os.path.join(parent_dir, 'web_content_urls.txt')

def read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from file."""
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
        
        logger.info(f"Read {len(urls)} URLs from {file_path}")
        return urls
        
    except Exception as e:
        logger.error(f"Error reading URLs from file: {e}")
        return []

def fetch_url(url: str) -> Dict[str, Any]:
    """Fetch and convert a URL to markdown content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        logger.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to extract title
        title = soup.title.string if soup.title else "Web Page"
        
        # Try to extract body text
        body = soup.body if soup.body else soup
        
        # Remove script and style tags
        for script in body(["script", "style", "noscript", "svg", "iframe"]):
            script.extract()
        
        # Convert to simple markdown
        text = body.get_text(separator='\n')
        # Clean up text
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        
        # Add title and source at the top
        markdown = f"# {title}\n\nSource: {url}\n\n{text}"
        
        return {
            "status": "success",
            "title": title,
            "url": url,
            "content": markdown
        }
    
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return {
            "status": "error",
            "url": url,
            "error": str(e)
        }

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

async def process_url(url: str, vector_db: VectorDB):
    """Process a single URL."""
    # Fetch the URL
    fetch_result = fetch_url(url)
    
    if fetch_result["status"] != "success":
        return fetch_result
    
    content = fetch_result["content"]
    
    # Generate a document ID
    doc_id = f"web_{uuid.uuid4()}"
    
    # Prepare metadata
    metadata = {
        "doc_id": doc_id,
        "source": "web", 
        "source_type": "web_page",
        "url": url,
        "title": fetch_result["title"],
        "author": "Web Content",
        "created_at": datetime.now().isoformat(),
        "synchronized_at": datetime.now().isoformat()
    }
    
    # Process and store the document
    try:
        chunks, chunk_metadatas = chunk_document(content, metadata)
        chunk_ids = vector_db.add_documents(
            documents=chunks,
            metadatas=chunk_metadatas
        )
        
        return {
            "status": "success",
            "url": url,
            "doc_id": doc_id,
            "title": fetch_result["title"],
            "chunks": len(chunk_ids)
        }
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        return {
            "status": "error",
            "url": url,
            "error": str(e)
        }

async def main():
    """Main function."""
    print("\n=== Sync ETH URLs to Vector Database ===")
    
    # Initialize vector database
    vector_db = VectorDB()
    
    # Read URLs from file
    urls = read_urls_from_file(URLS_FILE)
    
    if not urls:
        print("No URLs to process!")
        return
    
    print(f"\nFound {len(urls)} URLs to process:")
    for i, url in enumerate(urls):
        print(f"{i+1}. {url}")
    
    # Process each URL
    results = []
    for url in urls:
        print(f"\nProcessing: {url}")
        result = await process_url(url, vector_db)
        results.append(result)
        print(f"Result: {result['status']}")
        if result['status'] == 'success':
            print(f"Title: {result.get('title', 'No title')}")
            print(f"Chunks: {result.get('chunks', 0)}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    # Summarize results
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    
    print(f"\nProcessing complete: {success_count} succeeded, {error_count} failed")
    
    # Check what's in the database now
    print("\n=== URLs in Vector Database After Sync ===")
    db_results = vector_db.collection.get()
    
    # Extract URLs from metadata
    db_urls = {}
    for i, metadata in enumerate(db_results['metadatas']):
        if metadata.get('source') == 'web' and 'url' in metadata:
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

if __name__ == "__main__":
    asyncio.run(main())