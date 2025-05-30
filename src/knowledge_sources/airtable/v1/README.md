# Airtable Integration

This folder contains the necessary components to integrate Airtable data into the knowledge bot.

## Overview

The Airtable integration allows the bot to:
1. Fetch data from Airtable bases and tables
2. Format the data for embedding in vector databases
3. Search and query Airtable records
4. Use Airtable as a knowledge source for Claude responses

## Files

- `airtable_scraper.py`: Main scraper module that fetches and formats Airtable data
- `server.py`: MCP server that exposes Airtable tools
- `client.py`: MCP client for connecting to the server and processing queries

## Setup

1. Create an Airtable API key from your [Airtable account settings](https://airtable.com/create/tokens)
2. Find your Base ID (can be found in the API documentation section when viewing a base)
3. Add these environment variables to your `.env` file:
   ```
   AIRTABLE_API_KEY=your_api_key_here
   AIRTABLE_BASE_ID=your_base_id_here
   ```

## Usage

### Running the Server

```bash
python airtable/server.py
```

### Running the Client

```bash
python airtable/client.py airtable/server.py
```

### Available Tools

1. `fetch_airtable_base` - Fetch and format content from an entire Airtable base
   - Parameters:
     - `base_id`: ID of the Airtable base (defaults to env variable)
     - `include_tables`: Optional comma-separated list of table names to include

2. `search_airtable_records` - Search for specific records in an Airtable table
   - Parameters:
     - `base_id`: ID of the Airtable base (defaults to env variable)
     - `table_name`: Name of the table to search (required)
     - `query`: Text to search for in record fields

## Integration with Vector DB

The `airtable_scraper.py` module provides functions to format Airtable data for embedding in vector databases, similar to the Notion integration. Use `fetch_airtable_for_embedding()` to get documents ready for embedding.

## Examples

### Fetch Base Content

```python
from airtable.airtable_scraper import fetch_airtable_for_embedding

# Fetch all tables
documents = fetch_airtable_for_embedding(base_id="your_base_id")

# Fetch specific tables
documents = fetch_airtable_for_embedding(
    base_id="your_base_id",
    include_tables=["Projects", "Contacts"]
)
```

### Using with Claude

Once the MCP server is running, Claude can use the Airtable tools to answer questions based on Airtable data:

Example query: "What projects are currently active in our Airtable base?"