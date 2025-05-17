#!/usr/bin/env python3

import os
import sys
import json
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

def format_metadata(metadata):
    """Format metadata for display"""
    if not metadata:
        return "None"
    
    # Convert to pretty formatted JSON
    return json.dumps(metadata, indent=2)

def main():
    print("ChromaDB Inspection Tool")
    print("=======================\n")
    
    # Load environment variables
    load_dotenv('/home/.env')  # Adjust path if needed
    
    # Get ChromaDB path from environment
    chroma_dir = os.getenv('CHROMA_PERSIST_DIRECTORY', './db/chroma')
    
    # Convert relative path to absolute
    if not os.path.isabs(chroma_dir):
        base_dir = os.getcwd()
        chroma_dir = os.path.join(base_dir, chroma_dir)
    
    print(f"ChromaDB directory: {chroma_dir}")
    
    # Check if directory exists
    if not os.path.exists(chroma_dir):
        print(f"Error: ChromaDB directory not found at {chroma_dir}")
        print("Create the directory or check your CHROMA_PERSIST_DIRECTORY setting.")
        return
    
    # Initialize Chroma client
    try:
        client = chromadb.PersistentClient(path=chroma_dir)
        print("Successfully connected to ChromaDB\n")
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        return
    
    # List collections
    try:
        collections = client.list_collections()
        print(f"Found {len(collections)} collections:")
        
        if not collections:
            print("No collections found in the database.")
            return
            
        # Process each collection
        for idx, collection in enumerate(collections, 1):
            coll_name = collection.name
            print(f"\n{idx}. Collection: {coll_name}")
            
            # Get collection details
            try:
                count = collection.count()
                print(f"   Document count: {count}")
                
                if count == 0:
                    print("   No documents in this collection")
                    continue
                
                # Get sample documents
                print(f"   Fetching up to 5 sample documents...")
                results = collection.get(limit=5)
                
                # Print document details
                ids = results.get('ids', [])
                embeddings = results.get('embeddings', [None] * len(ids))
                metadatas = results.get('metadatas', [None] * len(ids))
                documents = results.get('documents', [None] * len(ids))
                
                for i in range(len(ids)):
                    doc_id = ids[i]
                    metadata = metadatas[i] if i < len(metadatas) else None
                    document = documents[i] if i < len(documents) else None
                    
                    print(f"\n   Document {i+1}:")
                    print(f"   - ID: {doc_id}")
                    
                    # Print metadata if available
                    if metadata:
                        print("   - Metadata:")
                        for key, value in metadata.items():
                            # Truncate long values
                            if isinstance(value, str) and len(value) > 100:
                                value = value[:100] + "..."
                            print(f"     {key}: {value}")
                    else:
                        print("   - Metadata: None")
                    
                    # Print document content (truncated)
                    if document:
                        doc_preview = document[:200] + "..." if len(document) > 200 else document
                        doc_preview = doc_preview.replace('\n', ' ')
                        print(f"   - Content: {doc_preview}")
                    else:
                        print("   - Content: None")
                
                # Check for more documents
                if count > 5:
                    print(f"\n   ... and {count - 5} more documents")
                
            except Exception as e:
                print(f"   Error inspecting collection: {e}")
    
    except Exception as e:
        print(f"Error listing collections: {e}")

if __name__ == "__main__":
    main()