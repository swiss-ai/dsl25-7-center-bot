#!/usr/bin/env python3
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add airtable directory to path
airtable_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, airtable_path)

# Import the Airtable scraper
from airtable_scraper import AirtableScraper

class AirtableDirectSearch:
    """
    Class for directly searching Airtable records without using vector database.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_id: Optional[str] = None):
        """Initialize the Airtable direct search."""
        self.api_key = api_key or os.getenv("AIRTABLE_API_KEY")
        self.base_id = base_id or os.getenv("AIRTABLE_BASE_ID")
        
        if not self.api_key:
            logger.error("Airtable API key not found. Set AIRTABLE_API_KEY in environment variables.")
        elif not self.base_id:
            logger.error("Airtable Base ID not found. Set AIRTABLE_BASE_ID in environment variables.")
        else:
            # Initialize the scraper
            self.scraper = AirtableScraper(self.api_key)
            logger.info(f"AirtableDirectSearch initialized for base: {self.base_id}")
    
    async def search_records(self, query: str, table_name: Optional[str] = None, max_results: int = 5) -> str:
        """
        Search for records in Airtable using direct API access.
        
        Args:
            query: The search query
            table_name: Optional specific table to search in
            max_results: Maximum number of results to return
            
        Returns:
            Formatted search results as a string
        """
        if not self.api_key or not self.base_id:
            return "Error: Airtable API key or Base ID not configured"
        
        logger.info(f"Directly searching Airtable for '{query}' in table '{table_name if table_name else 'all'}'")
        
        try:
            # Get list of tables first
            tables = self.scraper.get_table_list(self.base_id)
            
            if not tables:
                return f"Error: No tables found in base {self.base_id}"
            
            # Filter tables by name if specified
            if table_name:
                tables = [table for table in tables if table.get("name") == table_name]
                
                if not tables:
                    return f"Error: Table '{table_name}' not found in base {self.base_id}"
            
            # Search results across all matching tables
            all_matches = []
            
            for table in tables:
                table_id = table.get("id")
                table_name = table.get("name")
                
                # Get table schema
                table_schema = self.scraper.get_table_schema(self.base_id, table_id)
                
                # Get records from table
                records = self.scraper.get_table_records(self.base_id, table_id)
                
                if not records:
                    continue
                
                # Search for matches
                matches = []
                
                for record in records:
                    record_id = record.get("id")
                    fields = record.get("fields", {})
                    
                    # Check if any field matches the query
                    for field_name, field_value in fields.items():
                        # Convert field value to string for comparison
                        if isinstance(field_value, list):
                            value_str = ", ".join(str(item) for item in field_value)
                        else:
                            value_str = str(field_value)
                        
                        # Check if query is in field value (case insensitive)
                        if query.lower() in value_str.lower():
                            # Get the full record content
                            formatted_record = self.scraper.extract_record_content(record, table_schema)
                            
                            # Add to matches
                            matches.append({
                                "table_name": table_name,
                                "record_id": record_id,
                                "record_data": formatted_record["data"]
                            })
                            
                            # Only count each record once
                            break
                
                # Add table matches to overall matches
                all_matches.extend(matches)
            
            # Limit results
            all_matches = all_matches[:max_results]
            
            # Format results
            if not all_matches:
                return f"No Airtable records found for '{query}'"
            
            # Build markdown output
            output = f"## Airtable Search Results for '{query}'\n\n"
            output += f"Found {len(all_matches)} matching records\n\n"
            
            for i, match in enumerate(all_matches):
                table_name = match["table_name"]
                record_id = match["record_id"]
                record_data = match["record_data"]
                
                output += f"### Result {i+1}: {table_name} (Record ID: {record_id})\n\n"
                
                # Format record data
                for field_name, field_value in record_data.items():
                    if isinstance(field_value, dict) and "url" in field_value:
                        # This is likely an attachment
                        output += f"**{field_name}**: [Attachment]({field_value['url']})\n\n"
                    elif isinstance(field_value, list):
                        # Format lists nicely
                        if not field_value:
                            output += f"**{field_name}**: (empty)\n\n"
                        elif isinstance(field_value[0], dict):
                            # List of objects (likely attachments or linked records)
                            output += f"**{field_name}**: {len(field_value)} items\n\n"
                        else:
                            # Regular list
                            items = ", ".join(str(item) for item in field_value[:3])
                            if len(field_value) > 3:
                                items += f"... ({len(field_value)} total)"
                            output += f"**{field_name}**: {items}\n\n"
                    else:
                        # Regular field
                        value_str = str(field_value)
                        if len(value_str) > 200:
                            value_str = value_str[:200] + "..."
                        output += f"**{field_name}**: {value_str}\n\n"
                
                output += "---\n\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Error directly searching Airtable: {e}")
            return f"Error searching Airtable: {str(e)}"

# For testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Get query from command line
    query = sys.argv[1] if len(sys.argv) > 1 else "Alice"
    
    # Create searcher
    searcher = AirtableDirectSearch()
    
    # Run search
    result = asyncio.run(searcher.search_records(query))
    
    # Print result
    print(result)