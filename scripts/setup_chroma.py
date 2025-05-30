#!/usr/bin/env python3
"""Setup ChromaDB collections for the Slack bot"""

import os
import sys
import yaml
import chromadb
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def load_config():
    """Load ChromaDB configuration"""
    config_path = Path(__file__).parent.parent / "config" / "chroma.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_collections():
    """Initialize ChromaDB collections"""
    config = load_config()
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(
        path=config['chroma']['persist_directory']
    )
    
    # Create collections for each knowledge source
    for source, collection_config in config['collections'].items():
        try:
            collection = client.create_collection(
                name=collection_config['name'],
                metadata=collection_config['metadata']
            )
            print(f"Created collection: {collection_config['name']}")
        except Exception as e:
            print(f"Collection {collection_config['name']} may already exist: {e}")

if __name__ == "__main__":
    setup_collections()
    print("ChromaDB setup complete!")