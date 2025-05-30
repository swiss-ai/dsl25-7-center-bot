import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
from src.utils.logger import setup_logger
from src.utils.config import Config
from src.storage.chroma_client import ChromaDBClient
from chromadb.utils import embedding_functions

# Add the v1 directory to path to import notion_scraper
sys.path.append(os.path.join(os.path.dirname(__file__), 'v1'))
from notion_scraper import NotionScraper, fetch_notion_page_for_embedding

logger = setup_logger(__name__)

class NotionConnector:
    def __init__(self):
        """Initialize Notion connector with ChromaDB"""
        self.api_key = Config.NOTION_API_KEY
        self.page_id = Config.NOTION_PAGES
        
        # Initialize ChromaDB client
        self.chroma_client = ChromaDBClient()
        
        # Use sentence transformers for embeddings
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Get or create Notion collection
        self.collection = self.chroma_client.get_or_create_collection(
            collection_name="notion_pages",
            embedding_function=self.embedding_function,
            metadata={"source": "notion", "description": "Notion pages and content"}
        )
        
        logger.info("Notion connector initialized")
    
    def _generate_doc_id(self, page_id: str, content: str) -> str:
        """Generate a unique document ID based on page and content"""
        hash_input = f"{page_id}:{content[:100]}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _enhance_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance metadata with additional fields for better citation"""
        enhanced = metadata.copy()
        
        # Add timestamp
        enhanced["indexed_at"] = datetime.now().isoformat()
        
        # Add Notion URL if we have page_id
        if "page_id" in enhanced:
            # Notion URLs follow this pattern
            page_id = enhanced["page_id"].replace("-", "")
            enhanced["notion_url"] = f"https://www.notion.so/{page_id}"
        
        # Ensure all required fields
        enhanced["source_type"] = "notion"
        enhanced["source"] = "notion"
        
        return enhanced
    
    async def sync_notion_content(self) -> Dict[str, Any]:
        """Sync Notion content to ChromaDB"""
        try:
            logger.info(f"Starting Notion sync for page: {self.page_id}")
            
            # Fetch content from Notion
            documents = fetch_notion_page_for_embedding(
                page_id=self.page_id,
                api_key=self.api_key,
                chunk_size=1000
            )
            
            if not documents:
                logger.warning("No documents retrieved from Notion")
                return {"status": "error", "message": "No documents retrieved"}
            
            # Prepare documents for ChromaDB
            ids = []
            contents = []
            metadatas = []
            
            for doc in documents:
                # Generate unique ID
                doc_id = self._generate_doc_id(
                    doc["metadata"]["page_id"], 
                    doc["page_content"]
                )
                
                ids.append(doc_id)
                contents.append(doc["page_content"])
                metadatas.append(self._enhance_metadata(doc["metadata"]))
            
            # Clear existing Notion documents (optional - remove if you want to keep history)
            # You might want to implement a more sophisticated deduplication strategy
            try:
                # Get existing documents count
                existing_count = self.collection.count()
                logger.info(f"Collection currently has {existing_count} documents")
                
                # Delete all existing documents from this page
                if existing_count > 0:
                    # Query all documents from this page_id
                    results = self.collection.get(
                        where={"page_id": self.page_id}
                    )
                    if results["ids"]:
                        self.collection.delete(ids=results["ids"])
                        logger.info(f"Deleted {len(results['ids'])} existing documents")
            except Exception as e:
                logger.warning(f"Error clearing existing documents: {e}")
            
            # Add documents to ChromaDB
            self.collection.add(
                ids=ids,
                documents=contents,
                metadatas=metadatas
            )
            
            logger.info(f"Successfully indexed {len(documents)} documents from Notion")
            
            return {
                "status": "success",
                "documents_indexed": len(documents),
                "page_id": self.page_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing Notion content: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search Notion content in ChromaDB"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching Notion content: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the Notion collection"""
        try:
            count = self.collection.count()
            
            # Get sample metadata to show what pages are indexed
            sample = self.collection.get(limit=5)
            
            page_titles = set()
            if sample["metadatas"]:
                for metadata in sample["metadatas"]:
                    if "page_title" in metadata:
                        page_titles.add(metadata["page_title"])
            
            return {
                "total_documents": count,
                "collection_name": "notion_pages",
                "sample_pages": list(page_titles),
                "last_check": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting Notion stats: {e}")
            return {"error": str(e)}