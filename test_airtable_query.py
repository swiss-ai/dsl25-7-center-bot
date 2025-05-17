#!/usr/bin/env python3
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Try src-prefixed imports first
    try:
        from src.db.vector_db import VectorDB
        from src.services.knowledge.document_processor import DocumentProcessor
        from src.services.knowledge.datasources.airtable_manager import AirtableManager
    except ImportError:
        # Fall back to direct imports
        from db.vector_db import VectorDB
        from services.knowledge.document_processor import DocumentProcessor
        from services.knowledge.datasources.airtable_manager import AirtableManager
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

async def test_airtable_query(query="project"):
    """Test a query against Airtable."""
    try:
        # Initialize vector database
        vector_db = VectorDB(collection_name="documents")
        
        # Initialize document processor
        document_processor = DocumentProcessor(vector_db=vector_db)
        
        # Initialize Airtable manager
        airtable_manager = AirtableManager(
            document_processor=document_processor,
            vector_db=vector_db
        )
        
        print(f"Searching Airtable for: '{query}'")
        
        # Search for records
        results = await airtable_manager.search_airtable_records(
            query=query,
            n_results=5
        )
        
        print("\nResults:")
        print(results)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Get query from command line argument
    query = sys.argv[1] if len(sys.argv) > 1 else "project"
    
    # Run the test
    asyncio.run(test_airtable_query(query))