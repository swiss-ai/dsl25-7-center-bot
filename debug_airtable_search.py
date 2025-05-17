#!/usr/bin/env python3
import asyncio
import os
import sys
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.db.vector_db import VectorDB
    print("✅ Successfully imported VectorDB")
except ImportError as e:
    print(f"❌ Error importing VectorDB: {e}")
    sys.exit(1)

# Check available collections in Chroma
def check_collections():
    """Check available collections in Chroma."""
    try:
        from chromadb import PersistentClient
        
        # Get the Chroma persist directory from env or use default
        persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "./db/chroma")
        
        # Connect to Chroma
        client = PersistentClient(path=persist_dir)
        
        # List collections
        collections = client.list_collections()
        print(f"\nFound {len(collections)} collections in Chroma:")
        for collection in collections:
            collection_name = collection.name
            try:
                count = collection.count()
                print(f"  - {collection_name}: {count} documents")
            except:
                print(f"  - {collection_name}: Error getting count")
                
    except Exception as e:
        print(f"Error checking collections: {e}")

# Check for airtable entries in a collection
def check_airtable_entries(collection_name="documents"):
    """Check for airtable entries in a collection."""
    try:
        from chromadb import PersistentClient
        
        # Get the Chroma persist directory from env or use default
        persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "./db/chroma")
        
        # Connect to Chroma
        client = PersistentClient(path=persist_dir)
        
        # Get collection
        try:
            collection = client.get_collection(collection_name)
        except:
            print(f"❌ Collection '{collection_name}' not found")
            return
            
        # Query for airtable entries
        try:
            result = collection.get(where={"source": "airtable"})
            
            if not result or not result["ids"]:
                print(f"❌ No airtable entries found in collection '{collection_name}'")
                return
                
            print(f"✅ Found {len(result['ids'])} airtable entries in collection '{collection_name}'")
            
            # Show some of the entries
            for i in range(min(3, len(result["ids"]))):
                doc_id = result["ids"][i]
                metadata = result["metadatas"][i] if "metadatas" in result else {}
                
                print(f"\nDocument {i+1}:")
                print(f"  ID: {doc_id}")
                print(f"  Source: {metadata.get('source', 'unknown')}")
                print(f"  Table: {metadata.get('table_name', 'unknown')}")
                
                # Print a snippet of the document
                doc_content = result["documents"][i] if "documents" in result else "No content"
                if isinstance(doc_content, str) and len(doc_content) > 100:
                    doc_snippet = doc_content[:100] + "..."
                else:
                    doc_snippet = doc_content
                print(f"  Content: {doc_snippet}")
                
        except Exception as e:
            print(f"❌ Error querying for airtable entries: {e}")
            
    except Exception as e:
        print(f"❌ Error checking airtable entries: {e}")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Check collections
    print("\n🔍 Checking Chroma collections...")
    check_collections()
    
    # Check for airtable entries
    print("\n🔍 Checking for Airtable entries in default collection...")
    check_airtable_entries()
    
    # Also check in test_airtable collection if we ran the test script
    print("\n🔍 Checking for Airtable entries in test_airtable collection...")
    check_airtable_entries("test_airtable")