import asyncio
import os
from dotenv import load_dotenv
import requests
from mcp import Tool
from mcp.server.fastmcp import FastMCP
from mcp.server import Server

# Load environment variables
load_dotenv()
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_KEY = os.getenv("NOTION_KEY")


mcp = FastMCP("notion")

# Notion API Headers
headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2021-05-13",
}

def log_to_file(message):
    with open("debug_log.txt", "a") as log_file:
        log_file.write(message + "\n")

def get_title(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        log_to_file('title done')
        return data['properties']['title']['title'][0]['text']['content']
    else:
        return 'None'

def get_child_blocks(page_id):
    """Fetch child blocks from a Notion page."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    blocks = []


    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            blocks.extend(data["results"])
            url = data.get("next_cursor")
            if url:
                url = f"{url}?start_cursor={data['next_cursor']}"
        else:
            print(f"Error fetching blocks for page {page_id}: {response.status_code}")
            break

    
    return blocks


def extract_content_from_block(block, parent_page_id):
    """Extracts content from Notion blocks (paragraphs, headings, images)."""
    content = []


    if block["type"] == "paragraph":
        text_content = "".join([text["text"]["content"] for text in block["paragraph"]["text"]])
        content.append({"type": "paragraph", "content": text_content, "id": block["id"], "parent_page_id": parent_page_id})


    elif block["type"] in ["heading_1", "heading_2", "heading_3"]:
        text_content = "".join([text["text"]["content"] for text in block[block["type"]]["text"]])
        content.append({"type": block["type"], "content": text_content, "id": block["id"], "parent_page_id": parent_page_id})


    elif block["type"] == "image":
        image_url = block["image"]["file"]["url"] if "file" in block["image"] else None
        if image_url:
            content.append({"type": "image", "content": image_url, "id": block["id"], "parent_page_id": parent_page_id})


    return content


def retrieve_page_content(page_id, title):
    page_content = []
    
    # Fetch blocks (subpages or child blocks) of the given page
    blocks = get_child_blocks(page_id)
    child_pages_ids = []
    s = ""
    for block in blocks:
        block_content = extract_content_from_block(block, page_id)
        page_content.extend(block_content)
        # If the block is a child page, recursively fetch content from the subpage
        if block['type'] == 'child_page':
            subpage_id = block['id']
            child_pages_ids.append(subpage_id)
            s += retrieve_page_content(subpage_id, block['child_page']['title']) + "\n"
    
    s += f"Page_ID = {page_id} \n Title = {title} \n"
   
    if not page_content and not child_pages_ids:
        s += "EMPTY CONTENT \n"
    else:
        for i in child_pages_ids:
            s += f"  - Parent for page with ID={i} \n"
        for item in page_content:
            if item['type'] == 'paragraph':
                s += f"  - Paragraph: {item['content']} (ID: {item['id']}) \n"
            elif item['type'] == 'image':
                s += f"  - Image URL: {item['content']} (ID: {item['id']}) \n"
    log_to_file('string done')
    return s


@mcp.tool()
async def fetch_notion_page(page_id: str = NOTION_PAGE_ID) -> str:
    """
    Fetch Notion Page of ETH AI Center to retrieve latest news
    """
    content = retrieve_page_content(page_id, get_title(page_id))
    return content


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')

