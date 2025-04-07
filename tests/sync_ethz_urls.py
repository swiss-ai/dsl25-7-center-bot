#!/usr/bin/env python3
"""
Manually sync the ETH URLs from web_content_urls.txt to the vector database
"""
import os
import sys
import asyncio
import logging
from typing import Dict, List, Any

# Add the parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Set up environment
os.environ['PYTHONPATH'] = parent_dir

# Import necessary modules
from src.db.vector_db import VectorDB
from dotenv import load_dotenv
from src.config.settings import settings

# Create a modified version of the document processor for testing
class DocumentProcessor:
    def __init__(self, vector_db=None):
        self.vector_db = vector_db or VectorDB(collection_name="documents")
    
    async def process_document(self, content, metadata, chunk_size=500, chunk_overlap=50):
        """Process a document and store it in vector DB"""
        try:
            # Chunk the document
            chunks, chunk_metadatas = self._chunk_document(content, metadata, chunk_size, chunk_overlap)
            
            # Add chunks to vector database
            chunk_ids = self.vector_db.add_documents(
                documents=chunks,
                metadatas=chunk_metadatas
            )
            
            print(f"Processed document {metadata.get('doc_id')} into {len(chunks)} chunks")
            return chunk_ids
        
        except Exception as e:
            print(f"Error processing document: {e}")
            raise e
    
    def _chunk_document(self, content, metadata, chunk_size=500, chunk_overlap=50):
        """Split a document into overlapping chunks"""
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

# Import remaining modules
from src.services.mcp.web_fetch import MCPWebFetch
from src.services.knowledge.web_content_sync import WebContentSyncService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def sync_ethz_urls():
    """Sync the ETH URLs specifically"""
    # Initialize vector DB and document processor
    db = VectorDB()
    document_processor = DocumentProcessor(vector_db=db)
    
    # Initialize web fetcher
    web_fetch = MCPWebFetch()
    
    # Initialize sync service
    sync_service = WebContentSyncService(
        document_processor=document_processor,
        web_fetch=web_fetch
    )
    
    # Start the web fetch server
    server_started = await web_fetch.start_server()
    if not server_started:
        logger.error("Failed to start MCP Web Fetch server")
        return
    
    # Run the sync
    print("\n=== Manual Sync of ETH URLs ===")
    result = await sync_service.sync_all_urls()
    
    # Print results
    print(f"\nSync completed:")
    print(f"- Total URLs: {result['total_urls']}")
    print(f"- Success: {result['success_count']}")
    print(f"- Errors: {result['error_count']}")
    print(f"- Time taken: {result['time_taken']:.2f} seconds")
    
    # Print details of each URL
    print("\nURL details:")
    for i, detail in enumerate(result['details']):
        print(f"\n{i+1}. {detail['url']}")
        print(f"   Status: {detail['status']}")
        if detail['status'] == 'success':
            print(f"   Title: {detail.get('title', 'No title')}")
            print(f"   Chunks: {detail.get('chunks', 0)}")
        else:
            print(f"   Error: {detail.get('error', 'Unknown error')}")
    
    # Now let's check what's in the database
    print("\n=== URLs in Database After Sync ===")
    db_results = db.collection.get()
    
    # Extract URLs from metadata
    db_urls = set()
    for metadata in db_results['metadatas']:
        if metadata.get('source') == 'web' and 'url' in metadata:
            db_urls.add(metadata['url'])
    
    for i, url in enumerate(sorted(db_urls)):
        print(f"{i+1}. {url}")
    
if __name__ == "__main__":
    asyncio.run(sync_ethz_urls())