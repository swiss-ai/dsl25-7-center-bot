import os
import logging
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("notion_scraper.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_KEY = os.getenv("NOTION_KEY")

class NotionScraper:
    """Improved Notion content scraper with output suitable for embedding"""
    
    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        
    def get_page_title(self, page_id: str) -> str:
        """Get the title of a Notion page"""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            # Find title property (could have different names in different pages)
            for prop_name, prop in data["properties"].items():
                if prop["type"] == "title" and prop["title"]:
                    return prop["title"][0]["text"]["content"]
            return "Untitled"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting page title for {page_id}: {str(e)}")
            return "Unknown Title"
    
    def get_child_blocks(self, block_id: str) -> List[Dict[str, Any]]:
        """Get all child blocks with proper pagination handling"""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        all_blocks = []
        
        try:
            while url:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                all_blocks.extend(data["results"])
                
                # Handle pagination properly
                if data.get("has_more", False) and data.get("next_cursor"):
                    url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100&start_cursor={data['next_cursor']}"
                else:
                    url = None
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting child blocks for {block_id}: {str(e)}")
        
        return all_blocks
    
    def extract_block_content(self, block: Dict[str, Any], parent_page_id: str) -> List[Dict[str, Any]]:
        """Extract content from various Notion block types with better handling"""
        content = []
        block_type = block.get("type")
        
        if not block_type:
            return content
            
        block_id = block.get("id", "unknown")
        
        try:
            # Handle text blocks (paragraphs, headings)
            if block_type == "paragraph":
                rich_text = block.get("paragraph", {}).get("rich_text", [])
                text_content = "".join([text.get("text", {}).get("content", "") for text in rich_text])
                if text_content:
                    content.append({
                        "type": "paragraph", 
                        "content": text_content, 
                        "id": block_id, 
                        "parent_page_id": parent_page_id
                    })
                
            # Handle headings
            elif block_type in ["heading_1", "heading_2", "heading_3"]:
                rich_text = block.get(block_type, {}).get("rich_text", [])
                text_content = "".join([text.get("text", {}).get("content", "") for text in rich_text])
                if text_content:
                    content.append({
                        "type": block_type, 
                        "content": text_content, 
                        "id": block_id, 
                        "parent_page_id": parent_page_id
                    })
            
            # Handle bulleted and numbered lists
            elif block_type in ["bulleted_list_item", "numbered_list_item"]:
                rich_text = block.get(block_type, {}).get("rich_text", [])
                text_content = "".join([text.get("text", {}).get("content", "") for text in rich_text])
                if text_content:
                    content.append({
                        "type": block_type, 
                        "content": text_content, 
                        "id": block_id, 
                        "parent_page_id": parent_page_id
                    })
            
            # Handle images
            elif block_type == "image":
                image_block = block.get("image", {})
                image_url = None
                
                if "file" in image_block:
                    image_url = image_block["file"].get("url")
                elif "external" in image_block:
                    image_url = image_block["external"].get("url")
                    
                if image_url:
                    content.append({
                        "type": "image", 
                        "content": image_url, 
                        "id": block_id, 
                        "parent_page_id": parent_page_id
                    })
                    
            # Handle code blocks
            elif block_type == "code":
                rich_text = block.get("code", {}).get("rich_text", [])
                text_content = "".join([text.get("text", {}).get("content", "") for text in rich_text])
                language = block.get("code", {}).get("language", "")
                
                if text_content:
                    content.append({
                        "type": "code", 
                        "content": text_content, 
                        "language": language,
                        "id": block_id, 
                        "parent_page_id": parent_page_id
                    })
                    
            # Handle to-do items
            elif block_type == "to_do":
                rich_text = block.get("to_do", {}).get("rich_text", [])
                text_content = "".join([text.get("text", {}).get("content", "") for text in rich_text])
                checked = block.get("to_do", {}).get("checked", False)
                
                if text_content:
                    content.append({
                        "type": "to_do", 
                        "content": text_content, 
                        "checked": checked,
                        "id": block_id, 
                        "parent_page_id": parent_page_id
                    })
                    
        except Exception as e:
            logger.error(f"Error extracting content from block {block_id}: {str(e)}")
            
        return content
            
    def retrieve_page_content(self, page_id: str, max_depth: int = 5) -> Dict[str, Any]:
        """Retrieve all content from a Notion page"""
        return self._retrieve_content_recursive(page_id, 0, max_depth)
    
    def _retrieve_content_recursive(self, page_id: str, current_depth: int, max_depth: int) -> Dict[str, Any]:
        """Recursively retrieve page content with depth control"""
        if current_depth > max_depth:
            return {"type": "max_depth_reached", "id": page_id}
            
        try:
            # Get page title
            page_title = self.get_page_title(page_id)
            page_data = {
                "id": page_id,
                "title": page_title,
                "content": [],
                "subpages": []
            }
            
            # Get blocks
            blocks = self.get_child_blocks(page_id)
            
            for block in blocks:
                # Handle child page (subpage)
                if block.get("type") == "child_page":
                    subpage_id = block.get("id")
                    subpage_title = block.get("child_page", {}).get("title", "Untitled")
                    
                    # Recursively get subpage content
                    if current_depth < max_depth:
                        subpage_data = self._retrieve_content_recursive(
                            subpage_id, 
                            current_depth + 1, 
                            max_depth
                        )
                        page_data["subpages"].append(subpage_data)
                    else:
                        # Just add reference without recursing
                        page_data["subpages"].append({
                            "id": subpage_id,
                            "title": subpage_title,
                            "type": "reference_only"
                        })
                else:
                    # Extract content from this block
                    block_content = self.extract_block_content(block, page_id)
                    page_data["content"].extend(block_content)
            
            return page_data
            
        except Exception as e:
            logger.error(f"Error retrieving page content for {page_id}: {str(e)}")
            return {
                "id": page_id,
                "error": str(e),
                "content": [],
                "subpages": []
            }
    
    def get_embedding_documents(self, page_data: Dict[str, Any], chunk_size: int = 1000) -> List[Dict[str, Any]]:
        """
        Convert the structured page data to a list of documents ready for embedding
        
        Each document will contain:
        - page_content: The text content to be embedded
        - metadata: Information about the source (page ID, title, etc.)
        
        Args:
            page_data: The structured page data from retrieve_page_content
            chunk_size: Target size for text chunks (approximate)
            
        Returns:
            List of document dictionaries ready for embedding
        """
        documents = []
        
        # Process the current page
        current_chunk = ""
        current_metadata = {
            "page_id": page_data.get("id"),
            "page_title": page_data.get("title"),
            "source_type": "notion"
        }
        
        # Add page title to the chunk
        current_chunk += f"# {page_data.get('title', 'Untitled')}\n\n"
        
        # Process content items
        for item in page_data.get("content", []):
            item_text = ""
            item_type = item.get("type")
            
            # Format different content types appropriately
            if item_type in ["heading_1", "heading_2", "heading_3"]:
                level = int(item_type[-1])
                item_text = f"{'#' * level} {item.get('content')}\n\n"
            elif item_type == "paragraph":
                item_text = f"{item.get('content')}\n\n"
            elif item_type in ["bulleted_list_item", "numbered_list_item"]:
                prefix = "• " if item_type == "bulleted_list_item" else "1. "
                item_text = f"{prefix}{item.get('content')}\n"
            elif item_type == "to_do":
                check_mark = "✓ " if item.get("checked") else "☐ "
                item_text = f"{check_mark}{item.get('content')}\n"
            elif item_type == "code":
                language = item.get("language", "")
                item_text = f"```{language}\n{item.get('content')}\n```\n\n"
            
            # If adding this item would exceed chunk size, save current chunk and start a new one
            if len(current_chunk) + len(item_text) > chunk_size and len(current_chunk) > 0:
                documents.append({
                    "page_content": current_chunk.strip(),
                    "metadata": current_metadata.copy()
                })
                current_chunk = f"# {page_data.get('title', 'Untitled')} (continued)\n\n"
            
            current_chunk += item_text
        
        # Save the last chunk if it has content
        if current_chunk.strip():
            documents.append({
                "page_content": current_chunk.strip(),
                "metadata": current_metadata
            })
        
        # Process subpages recursively
        for subpage in page_data.get("subpages", []):
            if subpage.get("type") != "reference_only":
                subpage_documents = self.get_embedding_documents(subpage, chunk_size)
                documents.extend(subpage_documents)
        
        return documents


def fetch_notion_page_for_embedding(
    page_id: str = NOTION_PAGE_ID, 
    api_key: str = NOTION_KEY, 
    chunk_size: int = 1000
) -> List[Dict[str, Any]]:
    """
    Fetch Notion page content and prepare it for embedding
    
    Args:
        page_id: ID of the Notion page to fetch
        api_key: Notion API key
        chunk_size: Target size for text chunks
        
    Returns:
        List of documents ready for embedding
    """
    try:
        scraper = NotionScraper(api_key)
        page_data = scraper.retrieve_page_content(page_id)
        embedding_documents = scraper.get_embedding_documents(page_data, chunk_size)
        
        logger.info(f"Generated {len(embedding_documents)} embedding documents from page {page_id}")
        return embedding_documents
    except Exception as e:
        logger.error(f"Error in fetch_notion_page_for_embedding: {str(e)}")
        return [{
            "page_content": f"Error fetching Notion page: {str(e)}",
            "metadata": {"page_id": page_id, "error": True}
        }]


def format_page_data_as_text(page_data: Dict[str, Any], indent: int = 0) -> str:
    """
    Helper function to convert the structured page data to readable text
    (For debugging and inspection purposes)
    """
    indent_str = "  " * indent
    result = f"{indent_str}Page ID: {page_data['id']}\n"
    result += f"{indent_str}Title: {page_data['title']}\n\n"
    
    if not page_data.get("content") and not page_data.get("subpages"):
        result += f"{indent_str}EMPTY CONTENT\n"
    else:
        # Format content
        for item in page_data.get("content", []):
            item_type = item.get("type", "unknown")
            
            if item_type == "paragraph":
                result += f"{indent_str}- Paragraph: {item['content']} (ID: {item['id']})\n"
            elif item_type in ["heading_1", "heading_2", "heading_3"]:
                level = item_type[-1]
                result += f"{indent_str}- Heading {level}: {item['content']} (ID: {item['id']})\n"
            elif item_type == "image":
                result += f"{indent_str}- Image URL: {item['content']} (ID: {item['id']})\n"
            elif item_type == "code":
                result += f"{indent_str}- Code ({item.get('language', 'unknown')}): {item['content']} (ID: {item['id']})\n"
            elif item_type in ["bulleted_list_item", "numbered_list_item"]:
                list_type = "Bullet" if item_type == "bulleted_list_item" else "Number"
                result += f"{indent_str}- {list_type} list item: {item['content']} (ID: {item['id']})\n"
            elif item_type == "to_do":
                checked = "✓" if item.get("checked", False) else "☐"
                result += f"{indent_str}- Todo [{checked}]: {item['content']} (ID: {item['id']})\n"
            else:
                result += f"{indent_str}- {item_type}: {item.get('content', 'No content')} (ID: {item['id']})\n"
        
        # Format subpages
        for subpage in page_data.get("subpages", []):
            if subpage.get("type") == "reference_only":
                result += f"\n{indent_str}Subpage: {subpage['title']} (ID: {subpage['id']}) - Not expanded due to depth limit\n"
            else:
                result += f"\n{indent_str}--- SUBPAGE: {subpage['title']} ---\n"
                result += format_page_data_as_text(subpage, indent + 1)
                result += f"{indent_str}--- END SUBPAGE: {subpage['title']} ---\n"
    
    return result


if __name__ == "__main__":
    # Example usage
    page_id = NOTION_PAGE_ID
    
    # Get documents ready for embedding
    embedding_docs = fetch_notion_page_for_embedding(page_id)
    
    print(f"Generated {len(embedding_docs)} documents for embedding")
    
    # Print first document
    if embedding_docs:
        print("\nSample document:")
        print(f"Content: {embedding_docs[0]['page_content']}")
        print(f"Metadata: {embedding_docs[0]['metadata']}")
    
    # For debugging: save all documents to a file
    with open("notion_embedding_docs.txt", "w", encoding="utf-8") as f:
        for i, doc in enumerate(embedding_docs):
            f.write(f"--- DOCUMENT {i+1} ---\n")
            f.write(f"Metadata: {doc['metadata']}\n\n")
            f.write(doc['page_content'])
            f.write("\n\n" + "-"*50 + "\n\n")
    
    logger.info(f"Embedding documents saved to notion_embedding_docs.txt")