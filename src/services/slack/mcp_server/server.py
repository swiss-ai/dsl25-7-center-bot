# MCP server for Slack integration
import asyncio
import sys
import json
import os
import logging
from typing import Dict, Any, List, Optional
from slack_sdk import WebClient
from dotenv import load_dotenv

# Import knowledge tools
try:
    # Adjust path for imports based on execution context
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "../../../.."))
    sys.path.append(project_root)
    
    # Try relative imports first (when run within the app)
    try:
        from services.knowledge.document_processor import DocumentProcessor
        from services.knowledge.datasources.web_content import WebContentManager
        from services.knowledge.datasources.gdrive import GoogleDriveManager
        from services.mcp.web_fetch import MCPWebFetch
        from db.vector_db import VectorDB
        KNOWLEDGE_TOOLS_AVAILABLE = True #should be True
        logging.info("Using relative imports for knowledge tools")
    except ImportError:
        # Fall back to absolute imports (when run directly)
        from src.services.knowledge.document_processor import DocumentProcessor
        from src.services.knowledge.datasources.web_content import WebContentManager
        from src.services.knowledge.datasources.gdrive import GoogleDriveManager
        from src.services.mcp.web_fetch import MCPWebFetch
        from src.db.vector_db import VectorDB
        KNOWLEDGE_TOOLS_AVAILABLE = True #should be True
        logging.info("Using absolute imports for knowledge tools")
except ImportError as e:
    KNOWLEDGE_TOOLS_AVAILABLE = False
    logging.error(f"Error importing knowledge tools: {e}")

# Initialize knowledge components
document_processor = None
gdrive_manager = None
web_content_manager = None
vector_db = None

# Try to get components from main if available
try:
    import src.main as main_module
    
    # Check if main module already has initialized components
    if hasattr(main_module, 'document_processor') and main_module.document_processor:
        document_processor = main_module.document_processor
        logging.info("Using document_processor from main module")
    
    if hasattr(main_module, 'gdrive_manager') and main_module.gdrive_manager:
        gdrive_manager = main_module.gdrive_manager
        logging.info("Using gdrive_manager from main module")
    elif hasattr(main_module, 'gdrive_mcp') and main_module.gdrive_mcp:
        gdrive_manager = main_module.gdrive_mcp  # Fallback to MCP version
        logging.info("Using gdrive_mcp from main module as fallback")
    
    if hasattr(main_module, 'web_content_manager') and main_module.web_content_manager:
        web_content_manager = main_module.web_content_manager
        logging.info("Using web_content_manager from main module")
    
    if hasattr(main_module, 'vector_db') and main_module.vector_db:
        vector_db = main_module.vector_db
        logging.info("Using vector_db from main module")
except ImportError:
    logging.warning("Could not import main module for component access")

# Initialize components locally if not available from main
if not document_processor and KNOWLEDGE_TOOLS_AVAILABLE:
    try:
        # Initialize vector database
        if not vector_db:
            vector_db = VectorDB(collection_name="documents")
            logging.info("Initialized vector_db locally")
        
        # Initialize document processor
        document_processor = DocumentProcessor(vector_db=vector_db)
        logging.info("Initialized document_processor locally")
        
        # Initialize Google Drive integration if credentials exist
        if not gdrive_manager and os.getenv("GOOGLE_CREDENTIALS_PATH") and os.getenv("GOOGLE_TOKEN_PATH"):
            gdrive_manager = GoogleDriveManager(
                document_processor=document_processor,
                vector_db=vector_db,
                credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH"),
                token_path=os.getenv("GOOGLE_TOKEN_PATH"),
                sync_file=os.getenv("GOOGLE_DRIVE_SYNC_FILE", "gdrive_last_sync.json")
            )
            logging.info("Initialized gdrive_manager locally")
        
        # Initialize Web Content Manager
        if not web_content_manager:
            web_fetch = MCPWebFetch()
            web_content_manager = WebContentManager(
                document_processor=document_processor,
                web_fetch=web_fetch
            )
            logging.info("Initialized web_content_manager locally")
        
    except Exception as e:
        logging.error(f"Error initializing knowledge tools: {e}")
        # Don't reset components that might have been imported from main
        if not document_processor:
            document_processor = None
        if not gdrive_manager:
            gdrive_manager = None
        if not web_content_manager:
            web_content_manager = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="mcp_server.log"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Force UTF-8 encoding for stdout and stderr
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

class SlackTools:
    @staticmethod
    async def post_message(channel_id: str, text: str) -> Dict[str, Any]:
        """Post a message to a Slack channel."""
        try:
            response = slack_client.chat_postMessage(channel=channel_id, text=text)
            return {"ok": True, "message": response.data}
        except Exception as e:
            logger.error(f"Error posting message: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def reply_to_thread(channel_id: str, thread_ts: str, text: str) -> Dict[str, Any]:
        """Reply to a thread in a Slack channel."""
        try:
            response = slack_client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts
            )
            return {"ok": True, "message": response.data}
        except Exception as e:
            logger.error(f"Error replying to thread: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def get_channel_history(channel_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get the message history for a channel."""
        try:
            response = slack_client.conversations_history(channel=channel_id, limit=limit)
            return {"ok": True, "messages": response.data.get("messages", [])}
        except Exception as e:
            logger.error(f"Error getting channel history: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def get_thread_replies(channel_id: str, thread_ts: str) -> Dict[str, Any]:
        """Get replies to a thread."""
        try:
            response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts)
            return {"ok": True, "messages": response.data.get("messages", [])}
        except Exception as e:
            logger.error(f"Error getting thread replies: {e}")
            return {"ok": False, "error": str(e)}
    
    @staticmethod
    async def add_reaction(channel_id: str, timestamp: str, reaction: str) -> Dict[str, Any]:
        """Add a reaction to a message."""
        try:
            response = slack_client.reactions_add(
                channel=channel_id,
                timestamp=timestamp,
                name=reaction
            )
            return {"ok": True, "message": response.data}
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            return {"ok": False, "error": str(e)}

# Tool schemas
TOOLS = [
    {
        "name": "slack_post_message",
        "description": "Post a message to a Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel to post to"},
                "text": {"type": "string", "description": "The text of the message to post"}
            },
            "required": ["channel_id", "text"]
        }
    },
    {
        "name": "slack_reply_to_thread",
        "description": "Reply to a thread in a Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "thread_ts": {"type": "string", "description": "The timestamp of the thread to reply to"},
                "text": {"type": "string", "description": "The text of the message to post"}
            },
            "required": ["channel_id", "thread_ts", "text"]
        }
    },
    {
        "name": "slack_get_channel_history",
        "description": "Get recent messages from a Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "limit": {"type": "integer", "description": "Maximum number of messages to return"}
            },
            "required": ["channel_id"]
        }
    },
    {
        "name": "slack_get_thread_replies",
        "description": "Get all replies in a thread",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "thread_ts": {"type": "string", "description": "The timestamp of the thread"}
            },
            "required": ["channel_id", "thread_ts"]
        }
    },
    {
        "name": "slack_add_reaction",
        "description": "Add a reaction emoji to a message",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "The ID of the channel"},
                "timestamp": {"type": "string", "description": "The timestamp of the message"},
                "reaction": {"type": "string", "description": "Name of the emoji (without colons)"}
            },
            "required": ["channel_id", "timestamp", "reaction"]
        }
    },
    {
        "name": "search",
        "description": "Search for information in the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "source": {"type": "string", "description": "The source to search (all, web, drive, notion)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_document",
        "description": "Fetch a specific document from the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "The ID of the document"},
                "source": {"type": "string", "description": "The source system (drive, web, notion)"}
            },
            "required": ["document_id", "source"]
        }
    },
    {
        "name": "web_fetch",
        "description": "Fetch content from a URL and add it to the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "gdrive_search",
        "description": "Search for files in Google Drive",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Maximum number of results to return"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "gdrive_get_file",
        "description": "Get content from a Google Drive file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "The ID of the file to fetch"}
            },
            "required": ["file_id"]
        }
    }
]

async def handle_request():
    """Main MCP server loop."""
    logger.info("🚀 Starting MCP server for Slack integration...")
    
    slack_tools = SlackTools()
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
                
            request = json.loads(line)
            logger.info(f"📥 Received request: {request}")
            
            method = request.get("method")
            request_id = request.get("id")
            
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "sampling": {},
                            "roots": {"listChanged": True}
                        },
                        "serverInfo": {
                            "name": "AI Center Bot MCP Server",
                            "version": "0.1.0"
                        }
                    }
                }
                logger.info("✅ Initialized successfully")
                
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
                logger.info("🧰 Sent tool list")
                
            elif method == "tools/call":
                tool_name = request["params"]["name"]
                arguments = request["params"]["arguments"]
                
                logger.info(f"🔧 Tool call: {tool_name}, args: {arguments}")
                
                try:
                    # Handle Slack tools
                    if tool_name == "slack_post_message":
                        result = await slack_tools.post_message(
                            channel_id=arguments["channel_id"],
                            text=arguments["text"]
                        )
                        
                    elif tool_name == "slack_reply_to_thread":
                        result = await slack_tools.reply_to_thread(
                            channel_id=arguments["channel_id"],
                            thread_ts=arguments["thread_ts"],
                            text=arguments["text"]
                        )
                        
                    elif tool_name == "slack_get_channel_history":
                        result = await slack_tools.get_channel_history(
                            channel_id=arguments["channel_id"],
                            limit=arguments.get("limit", 10)
                        )
                        
                    elif tool_name == "slack_get_thread_replies":
                        result = await slack_tools.get_thread_replies(
                            channel_id=arguments["channel_id"],
                            thread_ts=arguments["thread_ts"]
                        )
                        
                    elif tool_name == "slack_add_reaction":
                        result = await slack_tools.add_reaction(
                            channel_id=arguments["channel_id"],
                            timestamp=arguments["timestamp"],
                            reaction=arguments["reaction"]
                        )
                        
                    # Knowledge tools with actual document processor integration
                    elif tool_name == "search":
                        query = arguments.get("query", "")
                        source_filter = arguments.get("source", "all")
                        
                        if not document_processor:
                            result = {
                                "ok": False,
                                "message": "Document processor not available"
                            }
                        else:
                            try:
                                # Build filter criteria based on source
                                filter_criteria = None
                                if source_filter != "all":
                                    filter_criteria = {"source": source_filter}
                                
                                # Perform the search
                                search_results = await document_processor.search_documents(
                                    query=query,
                                    n_results=5,
                                    filter_criteria=filter_criteria
                                )
                                
                                # Format the results with metadata
                                formatted_results = []
                                if search_results and search_results.get("documents"):
                                    for i, doc in enumerate(search_results["documents"]):
                                        metadata = search_results["metadatas"][i] if "metadatas" in search_results else {}
                                        source_type = metadata.get("source", "knowledge_base")
                                        source_info = {
                                            "type": source_type,
                                            "title": metadata.get("title", "Untitled Document"),
                                            "id": metadata.get("id", search_results["ids"][i] if "ids" in search_results else "unknown"),
                                            "url": metadata.get("url", ""),
                                        }
                                        
                                        # Add date information if available
                                        if "created_at" in metadata:
                                            source_info["created_at"] = metadata.get("created_at")
                                        if "processed_at" in metadata:
                                            source_info["processed_at"] = metadata.get("processed_at")
                                        if "last_modified" in metadata:
                                            source_info["last_modified"] = metadata.get("last_modified")
                                        if "crawled_at" in metadata:
                                            source_info["crawled_at"] = metadata.get("crawled_at")
                                            
                                        formatted_results.append({
                                            "content": doc,
                                            "source": source_info
                                        })
                                
                                result = {
                                    "ok": True,
                                    "results": formatted_results,
                                    "message": f"Found {len(formatted_results)} results for '{query}'" + 
                                              (f" in {source_filter}" if source_filter != "all" else "")
                                }
                            except Exception as e:
                                logger.error(f"Error searching documents: {e}")
                                result = {
                                    "ok": False,
                                    "message": f"Error searching documents: {str(e)}"
                                }
                    
                    elif tool_name == "fetch_document":
                        document_id = arguments.get("document_id", "")
                        source = arguments.get("source", "")
                        
                        if not document_processor or not document_processor.vector_db:
                            result = {
                                "ok": False,
                                "message": "Document processor or vector database not available"
                            }
                        else:
                            try:
                                # Build filter criteria based on source
                                filter_criteria = None
                                if source:
                                    filter_criteria = {"source": source}
                                
                                # Get the document
                                doc_result = document_processor.vector_db.get(
                                    ids=[document_id],
                                    where=filter_criteria
                                )
                                
                                if not doc_result or not doc_result.get("documents") or not doc_result["documents"]:
                                    result = {
                                        "ok": False,
                                        "message": f"Document {document_id} not found."
                                    }
                                else:
                                    # Format the document with metadata
                                    content = doc_result["documents"][0]
                                    metadata = doc_result["metadatas"][0] if "metadatas" in doc_result else {}
                                    
                                    source_type = metadata.get("source", source or "knowledge_base")
                                    source_info = {
                                        "type": source_type,
                                        "title": metadata.get("title", "Untitled Document"),
                                        "id": document_id,
                                        "url": metadata.get("url", ""),
                                    }
                                    
                                    # Add date information if available
                                    if "created_at" in metadata:
                                        source_info["created_at"] = metadata.get("created_at")
                                    if "processed_at" in metadata:
                                        source_info["processed_at"] = metadata.get("processed_at")
                                    if "last_modified" in metadata:
                                        source_info["last_modified"] = metadata.get("last_modified")
                                    if "crawled_at" in metadata:
                                        source_info["crawled_at"] = metadata.get("crawled_at")
                                    
                                    result = {
                                        "ok": True,
                                        "document": {
                                            "content": content,
                                            "source": source_info
                                        },
                                        "message": f"Retrieved document {document_id}"
                                    }
                            except Exception as e:
                                logger.error(f"Error fetching document: {e}")
                                result = {
                                    "ok": False,
                                    "message": f"Error fetching document: {str(e)}"
                                }
                    
                    elif tool_name == "web_fetch":
                        url = arguments.get("url", "")
                        
                        if not web_content_manager:
                            result = {
                                "ok": False,
                                "message": "Web content manager not available"
                            }
                        else:
                            try:
                                # Add URL to knowledge base
                                await web_content_manager.add_url_to_knowledge_base(url)
                                
                                # Then fetch the content
                                content = await web_content_manager.get_web_content(url)
                                
                                if not content:
                                    result = {
                                        "ok": False,
                                        "message": f"Could not fetch content from {url}"
                                    }
                                else:
                                    # Basic metadata for web content
                                    source_info = {
                                        "type": "web",
                                        "title": f"Web Content from {url}",
                                        "url": url,
                                        "fetched_at": web_content_manager.get_current_timestamp()
                                    }
                                    
                                    result = {
                                        "ok": True,
                                        "document": {
                                            "content": content,
                                            "source": source_info
                                        },
                                        "message": f"Fetched content from {url}"
                                    }
                            except Exception as e:
                                logger.error(f"Error fetching web content: {e}")
                                result = {
                                    "ok": False,
                                    "message": f"Error fetching web content: {str(e)}"
                                }
                    
                    elif tool_name == "gdrive_search":
                        query = arguments.get("query", "")
                        max_results = int(arguments.get("max_results", 5))
                        
                        if not gdrive_manager:
                            result = {
                                "ok": False,
                                "message": "Google Drive manager not available"
                            }
                        else:
                            try:
                                # Search files in Google Drive
                                files = await gdrive_manager.search_files(query, max_results=max_results)
                                
                                if not files:
                                    result = {
                                        "ok": False,
                                        "message": f"No files found matching '{query}'"
                                    }
                                else:
                                    # Format results with metadata
                                    formatted_results = []
                                    for file in files:
                                        formatted_results.append({
                                            "content": f"Google Drive file: {file.get('name')}",
                                            "source": {
                                                "type": "google_drive",
                                                "title": file.get('name', 'Untitled'),
                                                "id": file.get('id'),
                                                "mime_type": file.get('mimeType'),
                                                "last_modified": file.get('modifiedTime')
                                            }
                                        })
                                    
                                    result = {
                                        "ok": True,
                                        "results": formatted_results,
                                        "message": f"Found {len(formatted_results)} Google Drive files matching '{query}'"
                                    }
                            except Exception as e:
                                logger.error(f"Error searching Google Drive: {e}")
                                result = {
                                    "ok": False,
                                    "message": f"Error searching Google Drive: {str(e)}"
                                }
                    
                    elif tool_name == "gdrive_get_file":
                        file_id = arguments.get("file_id", "")
                        
                        if not gdrive_manager:
                            result = {
                                "ok": False,
                                "message": "Google Drive manager not available"
                            }
                        else:
                            try:
                                # Get file content and metadata from Google Drive
                                content, metadata = await gdrive_manager.get_file_content(file_id)
                                
                                if not content:
                                    result = {
                                        "ok": False,
                                        "message": f"Could not get content for file {file_id}"
                                    }
                                else:
                                    # Format with metadata
                                    source_info = {
                                        "type": "google_drive",
                                        "title": metadata.get("name", f"Google Drive File {file_id}"),
                                        "id": file_id,
                                        "mime_type": metadata.get("mimeType", "Unknown"),
                                        "last_modified": metadata.get("modifiedTime")
                                    }
                                    
                                    result = {
                                        "ok": True,
                                        "document": {
                                            "content": content,
                                            "source": source_info
                                        },
                                        "message": f"Retrieved Google Drive file {file_id}"
                                    }
                            except Exception as e:
                                logger.error(f"Error getting Google Drive file: {e}")
                                result = {
                                    "ok": False,
                                    "message": f"Error getting Google Drive file: {str(e)}"
                                }
                    
                    else:
                        result = {"ok": False, "error": f"Unknown tool: {tool_name}"}
                    
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                        }
                    }
                except Exception as e:
                    logger.error(f"❌ Error executing tool {tool_name}: {e}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Error executing tool {tool_name}: {str(e)}"
                        }
                    }
            
            else:
                # Unknown method
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}"
                    }
                }
                logger.error(f"❓ Unknown method: {method}")
            
            # Send response
            print(json.dumps(response))
            sys.stdout.flush()
            logger.info(f"📤 Sent response: {response}")
            
        except Exception as e:
            logger.error(f"🔥 Fatal server error: {e}")
            # Send error response
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in locals() else None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(response))
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(handle_request())
