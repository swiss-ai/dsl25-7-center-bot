import os
import sys
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib
from src.utils.logger import setup_logger
from src.utils.config import Config
from src.storage.chroma_client import ChromaDBClient
from chromadb.utils import embedding_functions

# Add the v1 directory to path to import airtable_scraper
sys.path.append(os.path.join(os.path.dirname(__file__), 'v1'))
from airtable_scraper import AirtableScraper, fetch_airtable_for_embedding

logger = setup_logger(__name__)

class AirtableConnector:
    def __init__(self):
        """Initialize Airtable connector with ChromaDB"""
        self.api_key = Config.AIRTABLE_API_KEY
        self.base_id = Config.AIRTABLE_BASE_ID
        
        # Initialize ChromaDB client
        self.chroma_client = ChromaDBClient()
        
        # Initialize Airtable scraper for direct searches
        self.scraper = AirtableScraper(self.api_key)
        
        # Use sentence transformers for embeddings
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Get or create Airtable collection
        self.collection = self.chroma_client.get_or_create_collection(
            collection_name="airtable_records",
            embedding_function=self.embedding_function,
            metadata={"source": "airtable", "description": "Airtable base records"}
        )
        
        logger.info("Airtable connector initialized")
    
    def _generate_doc_id(self, base_id: str, table_name: str, record_id: str) -> str:
        """Generate a unique document ID based on base, table, and record"""
        hash_input = f"{base_id}:{table_name}:{record_id}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _enhance_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance metadata with additional fields for better citation"""
        enhanced = metadata.copy()
        
        # Add timestamp
        enhanced["indexed_at"] = datetime.now().isoformat()
        
        # Add Airtable URL if we have the necessary info
        if all(key in enhanced for key in ["base_id", "table_id", "record_id"]):
            # Airtable URLs follow this pattern
            base_id = enhanced["base_id"]
            table_id = enhanced["table_id"]
            record_id = enhanced["record_id"]
            enhanced["airtable_url"] = f"https://airtable.com/{base_id}/{table_id}/{record_id}"
        
        # Add a more user-friendly URL for the base
        if "base_id" in enhanced:
            enhanced["base_url"] = f"https://airtable.com/{enhanced['base_id']}"
        
        # Ensure all required fields
        enhanced["source_type"] = "airtable"
        enhanced["source"] = "airtable"
        
        return enhanced
    
    async def sync_airtable_content(self, include_tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sync Airtable content to ChromaDB"""
        try:
            logger.info(f"Starting Airtable sync for base: {self.base_id}")
            
            # Fetch content from Airtable
            documents = fetch_airtable_for_embedding(
                base_id=self.base_id,
                api_key=self.api_key,
                include_tables=include_tables,
                chunk_size=1000
            )
            
            if not documents:
                logger.warning("No documents retrieved from Airtable")
                return {"status": "error", "message": "No documents retrieved"}
            
            # Prepare documents for ChromaDB
            ids = []
            contents = []
            metadatas = []
            
            for doc in documents:
                metadata = doc["metadata"]
                
                # Generate unique ID
                doc_id = self._generate_doc_id(
                    metadata["base_id"],
                    metadata["table_name"],
                    metadata["record_id"]
                )
                
                ids.append(doc_id)
                contents.append(doc["page_content"])
                metadatas.append(self._enhance_metadata(metadata))
            
            # Clear existing Airtable documents from this base
            try:
                # Get existing documents count
                existing_count = self.collection.count()
                logger.info(f"Collection currently has {existing_count} documents")
                
                # Delete all existing documents from this base
                if existing_count > 0:
                    # Query all documents from this base_id
                    results = self.collection.get(
                        where={"base_id": self.base_id}
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
            
            logger.info(f"Successfully indexed {len(documents)} documents from Airtable")
            
            # Get table summary
            tables_indexed = {}
            for metadata in metadatas:
                table_name = metadata.get("table_name", "Unknown")
                tables_indexed[table_name] = tables_indexed.get(table_name, 0) + 1
            
            return {
                "status": "success",
                "documents_indexed": len(documents),
                "base_id": self.base_id,
                "tables_indexed": tables_indexed,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing Airtable content: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search Airtable content in ChromaDB"""
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
            logger.error(f"Error searching Airtable content: {e}")
            return []
    
    def direct_search(self, query: str, table_name: Optional[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Perform direct search against Airtable API (real-time data)
        
        Args:
            query: Search query
            table_name: Optional specific table to search
            max_results: Maximum results to return
            
        Returns:
            List of search results with metadata
        """
        try:
            logger.info(f"Performing direct Airtable search for: {query}")
            
            # Get all tables
            tables = self.scraper.get_table_list(self.base_id)
            
            if table_name:
                # Filter to specific table
                tables = [t for t in tables if t.get("name") == table_name]
            
            all_results = []
            query_lower = query.lower()
            
            # Search through each table
            for table in tables:
                table_id = table.get("id")
                table_name = table.get("name")
                
                # Get records from table
                records = self.scraper.get_table_records(self.base_id, table_id, max_records=100)
                
                # Search through records
                for record in records:
                    fields = record.get("fields", {})
                    record_text = ""
                    
                    # Build searchable text from all fields
                    for field_name, field_value in fields.items():
                        if isinstance(field_value, list):
                            field_text = " ".join(str(item) for item in field_value)
                        else:
                            field_text = str(field_value)
                        record_text += f" {field_text}"
                    
                    # Check if query matches
                    if query_lower in record_text.lower():
                        # Format as result
                        formatted_content = f"# {table_name} Record\n\n"
                        for field_name, field_value in fields.items():
                            if isinstance(field_value, list):
                                field_text = ", ".join(str(item) for item in field_value)
                            else:
                                field_text = str(field_value)
                            formatted_content += f"**{field_name}**: {field_text}\n\n"
                        
                        result = {
                            "content": formatted_content.strip(),
                            "metadata": self._enhance_metadata({
                                "base_id": self.base_id,
                                "table_id": table_id,
                                "table_name": table_name,
                                "record_id": record.get("id"),
                                "source_type": "airtable",
                                "search_type": "direct"
                            }),
                            "score": 1.0  # Direct match
                        }
                        
                        all_results.append(result)
                        
                        if len(all_results) >= max_results:
                            break
                
                if len(all_results) >= max_results:
                    break
            
            logger.info(f"Direct search found {len(all_results)} results")
            return all_results[:max_results]
            
        except Exception as e:
            logger.error(f"Error in direct Airtable search: {e}")
            return []
    
    def search_with_deduplication(self, query: str, n_results: int = 5) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Search both ChromaDB cache and direct API, with deduplication
        
        Returns:
            Tuple of (cached_results, direct_results) with duplicates marked
        """
        # Get cached results from ChromaDB
        cached_results = self.search(query, n_results)
        
        # Get direct results from API
        direct_results = self.direct_search(query, max_results=n_results)
        
        # Mark duplicates in direct results
        for direct_result in direct_results:
            direct_metadata = direct_result.get("metadata", {})
            direct_record_id = direct_metadata.get("record_id")
            
            # Check if this record exists in cached results
            is_duplicate = False
            for cached_result in cached_results:
                cached_metadata = cached_result.get("metadata", {})
                if cached_metadata.get("record_id") == direct_record_id:
                    is_duplicate = True
                    break
            
            # Mark as duplicate if found in cache
            if is_duplicate:
                direct_result["metadata"]["is_duplicate"] = True
                direct_result["metadata"]["duplicate_source"] = "cached"
            else:
                direct_result["metadata"]["is_duplicate"] = False
        
        return cached_results, direct_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the Airtable collection"""
        try:
            count = self.collection.count()
            
            # Get sample metadata to show what tables are indexed
            sample = self.collection.get(limit=10)
            
            table_names = set()
            base_ids = set()
            if sample["metadatas"]:
                for metadata in sample["metadatas"]:
                    if "table_name" in metadata:
                        table_names.add(metadata["table_name"])
                    if "base_id" in metadata:
                        base_ids.add(metadata["base_id"])
            
            return {
                "total_documents": count,
                "collection_name": "airtable_records",
                "tables": list(table_names),
                "bases": list(base_ids),
                "last_check": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting Airtable stats: {e}")
            return {"error": str(e)}