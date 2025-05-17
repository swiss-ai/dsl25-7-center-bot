import os
import logging
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("airtable_scraper.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

class AirtableScraper:
    """Airtable content scraper with output suitable for embedding"""
    
    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
    def get_table_list(self, base_id: str) -> List[Dict[str, Any]]:
        """Get list of tables in a base"""
        url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            return data.get("tables", [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting tables for base {base_id}: {str(e)}")
            return []
    
    def get_table_records(self, base_id: str, table_id: str, max_records: int = 100) -> List[Dict[str, Any]]:
        """Get records from a table with pagination support"""
        table_name = self._get_table_name(base_id, table_id)
        if not table_name:
            logger.error(f"Could not find table name for ID {table_id}")
            return []
            
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}?maxRecords={max_records}"
        all_records = []
        
        try:
            while url:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                all_records.extend(data.get("records", []))
                
                # Handle pagination
                if data.get("offset"):
                    url = f"https://api.airtable.com/v0/{base_id}/{table_name}?maxRecords={max_records}&offset={data['offset']}"
                else:
                    url = None
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting records for table {table_id}: {str(e)}")
        
        return all_records
    
    def _get_table_name(self, base_id: str, table_id: str) -> Optional[str]:
        """Get the name of a table from its ID"""
        tables = self.get_table_list(base_id)
        
        for table in tables:
            if table.get("id") == table_id:
                return table.get("name")
        
        return None
    
    def get_table_schema(self, base_id: str, table_id: str) -> Dict[str, Any]:
        """Get the schema (fields) of a table"""
        tables = self.get_table_list(base_id)
        
        for table in tables:
            if table.get("id") == table_id:
                return {
                    "id": table.get("id"),
                    "name": table.get("name"),
                    "fields": table.get("fields", [])
                }
        
        return {
            "id": table_id,
            "name": "Unknown",
            "fields": []
        }
    
    def extract_record_content(self, record: Dict[str, Any], table_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Format record data for readability and embedding"""
        record_id = record.get("id", "unknown")
        fields = record.get("fields", {})
        
        # Format data with field names from schema
        formatted_data = {}
        
        for field in table_schema.get("fields", []):
            field_name = field.get("name")
            field_id = field.get("id")
            
            if field_name in fields:
                formatted_data[field_name] = fields[field_name]
        
        return {
            "id": record_id,
            "data": formatted_data
        }
    
    def retrieve_base_content(self, base_id: str, include_tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Retrieve content from all tables in a base"""
        try:
            # Get all tables
            tables = self.get_table_list(base_id)
            
            base_data = {
                "id": base_id,
                "tables": []
            }
            
            for table in tables:
                table_id = table.get("id")
                table_name = table.get("name")
                
                # Skip if we're only including specific tables
                if include_tables and table_name not in include_tables:
                    continue
                
                # Get table schema and records
                table_schema = self.get_table_schema(base_id, table_id)
                records = self.get_table_records(base_id, table_id)
                
                formatted_records = []
                for record in records:
                    formatted_record = self.extract_record_content(record, table_schema)
                    formatted_records.append(formatted_record)
                
                table_data = {
                    "id": table_id,
                    "name": table_name,
                    "schema": table_schema.get("fields", []),
                    "records": formatted_records
                }
                
                base_data["tables"].append(table_data)
            
            return base_data
            
        except Exception as e:
            logger.error(f"Error retrieving base content for {base_id}: {str(e)}")
            return {
                "id": base_id,
                "error": str(e),
                "tables": []
            }
    
    def get_embedding_documents(self, base_data: Dict[str, Any], chunk_size: int = 1000) -> List[Dict[str, Any]]:
        """
        Convert base data to documents ready for embedding
        
        Each document will contain:
        - page_content: The text content to be embedded
        - metadata: Information about the source (base ID, table name, etc.)
        """
        documents = []
        
        for table in base_data.get("tables", []):
            table_name = table.get("name")
            table_id = table.get("id")
            
            # Create a document for each record
            for record in table.get("records", []):
                record_id = record.get("id")
                record_data = record.get("data", {})
                
                # Format record data as text
                record_text = f"# {table_name} Record\n\n"
                
                for field_name, field_value in record_data.items():
                    # Handle different field types
                    if isinstance(field_value, list):
                        field_text = ", ".join(str(item) for item in field_value)
                    else:
                        field_text = str(field_value)
                    
                    record_text += f"**{field_name}**: {field_text}\n\n"
                
                # Create document with metadata
                documents.append({
                    "page_content": record_text.strip(),
                    "metadata": {
                        "base_id": base_data.get("id"),
                        "table_id": table_id,
                        "table_name": table_name,
                        "record_id": record_id,
                        "source_type": "airtable"
                    }
                })
        
        return documents


def fetch_airtable_for_embedding(
    base_id: str = AIRTABLE_BASE_ID, 
    api_key: str = AIRTABLE_API_KEY,
    include_tables: Optional[List[str]] = None,
    chunk_size: int = 1000
) -> List[Dict[str, Any]]:
    """
    Fetch Airtable content and prepare it for embedding
    
    Args:
        base_id: ID of the Airtable base to fetch
        api_key: Airtable API key
        include_tables: Optional list of table names to include (all if None)
        chunk_size: Target size for text chunks
        
    Returns:
        List of documents ready for embedding
    """
    try:
        scraper = AirtableScraper(api_key)
        base_data = scraper.retrieve_base_content(base_id, include_tables)
        embedding_documents = scraper.get_embedding_documents(base_data, chunk_size)
        
        logger.info(f"Generated {len(embedding_documents)} embedding documents from base {base_id}")
        return embedding_documents
    except Exception as e:
        logger.error(f"Error in fetch_airtable_for_embedding: {str(e)}")
        return [{
            "page_content": f"Error fetching Airtable base: {str(e)}",
            "metadata": {"base_id": base_id, "error": True}
        }]


def format_base_data_as_text(base_data: Dict[str, Any]) -> str:
    """
    Format base data as readable text (for debugging)
    """
    result = f"Base ID: {base_data['id']}\n\n"
    
    if not base_data.get("tables"):
        result += "EMPTY CONTENT\n"
    else:
        for table in base_data.get("tables", []):
            table_name = table.get("name")
            result += f"## Table: {table_name}\n\n"
            
            # Show schema
            result += "### Schema:\n"
            for field in table.get("schema", []):
                field_name = field.get("name")
                field_type = field.get("type")
                result += f"- {field_name} ({field_type})\n"
            
            result += "\n### Records:\n"
            for record in table.get("records", []):
                result += f"- Record ID: {record['id']}\n"
                for field_name, field_value in record.get("data", {}).items():
                    result += f"  - {field_name}: {field_value}\n"
                result += "\n"
    
    return result


if __name__ == "__main__":
    # Example usage
    base_id = AIRTABLE_BASE_ID
    
    # Get documents ready for embedding
    embedding_docs = fetch_airtable_for_embedding(base_id)
    
    print(f"Generated {len(embedding_docs)} documents for embedding")
    
    # Print first document
    if embedding_docs:
        print("\nSample document:")
        print(f"Content: {embedding_docs[0]['page_content']}")
        print(f"Metadata: {embedding_docs[0]['metadata']}")
    
    # For debugging: save all documents to a file
    with open("airtable_embedding_docs.txt", "w", encoding="utf-8") as f:
        for i, doc in enumerate(embedding_docs):
            f.write(f"--- DOCUMENT {i+1} ---\n")
            f.write(f"Metadata: {doc['metadata']}\n\n")
            f.write(doc['page_content'])
            f.write("\n\n" + "-"*50 + "\n\n")
    
    logger.info(f"Embedding documents saved to airtable_embedding_docs.txt")