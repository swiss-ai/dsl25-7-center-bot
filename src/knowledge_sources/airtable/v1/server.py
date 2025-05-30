import asyncio
import os
from dotenv import load_dotenv
import requests
from mcp import Tool
from mcp.server.fastmcp import FastMCP
from mcp.server import Server

# Load environment variables
load_dotenv()
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")


mcp = FastMCP("airtable")

# Airtable API Headers
headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
}

def log_to_file(message):
    with open("airtable_debug_log.txt", "a") as log_file:
        log_file.write(message + "\n")

def get_table_list(base_id):
    """Get list of tables in a base"""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        return data.get("tables", [])
        
    except requests.exceptions.RequestException as e:
        log_to_file(f"Error getting tables for base {base_id}: {str(e)}")
        return []

def get_table_records(base_id, table_name, max_records=100):
    """Get records from a table with pagination support"""
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}?maxRecords={max_records}"
    all_records = []
    
    try:
        while url:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            all_records.extend(data.get("records", []))
            
            # Handle pagination
            if data.get("offset"):
                url = f"https://api.airtable.com/v0/{base_id}/{table_name}?maxRecords={max_records}&offset={data['offset']}"
            else:
                url = None
                
    except requests.exceptions.RequestException as e:
        log_to_file(f"Error getting records for table {table_name}: {str(e)}")
    
    return all_records

def format_table_data(table_name, records):
    """Format table data as readable text"""
    result = f"## Table: {table_name}\n\n"
    
    if not records:
        result += "No records found.\n\n"
        return result
    
    # Get all possible field names from records
    field_names = set()
    for record in records:
        for field_name in record.get("fields", {}).keys():
            field_names.add(field_name)
    
    # Format as table
    result += "| id | " + " | ".join(field_names) + " |\n"
    result += "|-----|" + "|".join(["-----" for _ in field_names]) + "|\n"
    
    for record in records:
        row = [record.get("id", "")]
        fields = record.get("fields", {})
        
        for field_name in field_names:
            value = fields.get(field_name, "")
            # Format list values
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            row.append(str(value))
        
        result += "| " + " | ".join(row) + " |\n"
    
    result += "\n"
    return result

def get_base_content(base_id, include_tables=None):
    """Retrieve and format content from an Airtable base"""
    tables = get_table_list(base_id)
    result = f"# Airtable Base: {base_id}\n\n"
    
    if not tables:
        result += "No tables found in this base.\n"
        return result
    
    for table in tables:
        table_id = table.get("id")
        table_name = table.get("name")
        
        # Skip if we're only including specific tables
        if include_tables and table_name not in include_tables:
            continue
        
        # Get records for this table
        records = get_table_records(base_id, table_name)
        
        # Format table data
        result += format_table_data(table_name, records)
    
    return result


@mcp.tool()
async def fetch_airtable_base(base_id: str = AIRTABLE_BASE_ID, include_tables: str = None) -> str:
    """
    Fetch content from an Airtable base
    
    Args:
        base_id: ID of the Airtable base to fetch
        include_tables: Comma-separated list of table names to include (optional)
    
    Returns:
        Formatted base content
    """
    include_table_list = None
    if include_tables:
        include_table_list = [table.strip() for table in include_tables.split(",")]
    
    content = get_base_content(base_id, include_table_list)
    return content


@mcp.tool()
async def search_airtable_records(
    base_id: str = AIRTABLE_BASE_ID, 
    table_name: str = None,
    query: str = None
) -> str:
    """
    Search for records in an Airtable base
    
    Args:
        base_id: ID of the Airtable base to search
        table_name: Name of the table to search (required)
        query: Text to search for in record fields
    
    Returns:
        Matching records formatted as text
    """
    if not table_name:
        return "Error: table_name is required"
    
    # Get records for this table
    records = get_table_records(base_id, table_name)
    
    # Filter records if query is provided
    if query:
        query = query.lower()
        filtered_records = []
        
        for record in records:
            fields = record.get("fields", {})
            
            # Check if any field value contains the query
            for field_name, field_value in fields.items():
                value_str = str(field_value).lower()
                if query in value_str:
                    filtered_records.append(record)
                    break
        
        records = filtered_records
    
    # Format table data
    result = f"# Search Results in {table_name}\n\n"
    result += format_table_data(table_name, records)
    
    return result


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')