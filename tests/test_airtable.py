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

# Setup path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.vector_db import VectorDB
from src.services.knowledge.document_processor import DocumentProcessor
from src.services.knowledge.datasources.airtable_manager import AirtableManager

# Load environment variables
load_dotenv()

async def test_airtable_integration():
    """Test the Airtable integration."""
    # Check if Airtable configuration exists
    airtable_api_key = os.getenv("AIRTABLE_API_KEY")
    airtable_base_id = os.getenv("AIRTABLE_BASE_ID")
    
    if not airtable_api_key or not airtable_base_id:
        logger.error("Airtable API key or base ID not configured")
        print("❌ Airtable configuration missing. Set AIRTABLE_API_KEY and AIRTABLE_BASE_ID in .env file.")
        return
    
    try:
        # Initialize vector database
        vector_db = VectorDB(collection_name="test_airtable")
        
        # Initialize document processor
        document_processor = DocumentProcessor(vector_db=vector_db)
        
        # Initialize Airtable manager
        airtable_manager = AirtableManager(
            document_processor=document_processor,
            vector_db=vector_db
        )
        
        print("✅ Airtable manager initialized")
        
        # Step 1: Sync Airtable base
        print("\n📊 Syncing Airtable base...")
        sync_result = await airtable_manager.sync_airtable_base()
        
        if sync_result.get("status") == "success":
            print(f"✅ Airtable sync completed successfully")
            print(f"   - Documents processed: {sync_result.get('documents', 0)}")
            print(f"   - Chunks created: {sync_result.get('chunks', 0)}")
        else:
            print(f"❌ Airtable sync failed: {sync_result.get('message', 'Unknown error')}")
            return
        
        # Step 2: Search for records
        print("\n🔍 Testing Airtable search...")
        
        # Ask for search query
        query = input("\nEnter search query (or leave empty for default 'project'): ")
        if not query:
            query = "project"
            
        # Search for records
        search_results = await airtable_manager.search_airtable_records(query=query, n_results=5)
        
        # Display results
        print(f"\nSearch results for '{query}':")
        print(search_results)
        
        # Clean up vector database (optional)
        clean = input("\nClean up test database? (y/n): ")
        if clean.lower() == 'y':
            vector_db.collection.delete(where={"source": "airtable"})
            print("✅ Test data cleaned up")
        
    except Exception as e:
        logger.error(f"Error testing Airtable integration: {e}")
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_airtable_integration())