#!/usr/bin/env python3
import os
import asyncio
import sys
from dotenv import load_dotenv

# Add airtable directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "airtable"))

try:
    # Import the Airtable scraper directly
    from airtable_scraper import AirtableScraper, fetch_airtable_for_embedding
except ImportError as e:
    print(f"Error importing Airtable scraper: {e}")
    sys.exit(1)

async def main():
    # Load environment variables
    load_dotenv()
    
    # Get API key and base ID
    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = os.getenv("AIRTABLE_BASE_ID")
    
    if not api_key or not base_id:
        print("Error: AIRTABLE_API_KEY or AIRTABLE_BASE_ID not set in environment")
        sys.exit(1)
    
    # Create scraper
    scraper = AirtableScraper(api_key)
    
    # Get tables
    print("Getting tables...")
    tables = scraper.get_table_list(base_id)
    
    if not tables:
        print("No tables found or error connecting to Airtable")
        sys.exit(1)
        
    print(f"Found {len(tables)} tables:")
    for table in tables:
        table_id = table.get("id")
        table_name = table.get("name")
        print(f"  - {table_name} (ID: {table_id})")
        
        # Get records
        records = scraper.get_table_records(base_id, table_id, max_records=5)
        print(f"    Records: {len(records)}")
        
        # Print first record if available
        if records:
            record = records[0]
            record_id = record.get("id")
            fields = record.get("fields", {})
            print(f"    Sample record (ID: {record_id}):")
            for field_name, field_value in fields.items():
                if isinstance(field_value, list):
                    value_str = ", ".join(str(v) for v in field_value[:3])
                    if len(field_value) > 3:
                        value_str += f"... ({len(field_value)} items)"
                else:
                    value_str = str(field_value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                print(f"      {field_name}: {value_str}")
            
            print("")
    
    # Search functionality
    query = sys.argv[1] if len(sys.argv) > 1 else None
    if query:
        print(f"\nSearch test for: '{query}'")
        print("This is a basic search (not semantic). Looking for exact matches in fields.")
        
        for table in tables:
            table_id = table.get("id")
            table_name = table.get("name")
            
            # Basic search implementation
            records = scraper.get_table_records(base_id, table_id)
            matches = []
            
            for record in records:
                fields = record.get("fields", {})
                found = False
                
                for field_name, field_value in fields.items():
                    value_str = str(field_value).lower()
                    if query.lower() in value_str:
                        matches.append(record)
                        found = True
                        break
            
            if matches:
                print(f"\nFound {len(matches)} matches in table '{table_name}':")
                for match in matches[:3]:  # Show up to 3 matches
                    record_id = match.get("id")
                    fields = match.get("fields", {})
                    print(f"  Record ID: {record_id}")
                    for field_name, field_value in fields.items():
                        if isinstance(field_value, list):
                            value_str = ", ".join(str(v) for v in field_value[:3])
                            if len(field_value) > 3:
                                value_str += f"... ({len(field_value)} items)"
                        else:
                            value_str = str(field_value)
                            if len(value_str) > 100:
                                value_str = value_str[:100] + "..."
                        print(f"    {field_name}: {value_str}")
                    print("")

if __name__ == "__main__":
    asyncio.run(main())