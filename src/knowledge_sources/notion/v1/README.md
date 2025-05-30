# Notion Integration

This folder contains the necessary components to integrate Notion data into the knowledge bot.
Notion's REST API facilitates direct interactions with workspace elements through programming.

## Setup
Create a new integration (internal or public) in Notion’s integrations dashboard: <https://www.notion.com/my-integrations>.
1. Click + New integration
2. Enter the integration name and select the associated workspace for the new integration.
3. API requests require an API secret to be successfully authenticated. Visit the Configuration tab to get your integration’s API secret (or “Internal Integration Secret”).

## Environment variables
In your .env file, add the following variables:

NOTION_KEY= <your-notion-api-key>
NOTION_PAGE_ID=<parent-page-id>

### Available Function

1. `fetch_notion_page_for_embedding` - Fetch information from a Notion page as well as its subpages before embeding 
   - Parameters:
     - `page_id`: ID of the Notion Page (defaults to env variable)

### Note

No MCP tools available for Notion since pages are typically really large and contain a wide range of information.
Thus, we rely on Chroma DB and traditional RAG architecture for this data source.