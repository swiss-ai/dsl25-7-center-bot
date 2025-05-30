import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import sys
import json

from src.storage.chroma_client import ChromaDBClient
from src.utils.config import Config
from src.utils.logger import setup_logger
from chromadb.utils import embedding_functions

# Add the v1 directory to path to import existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'v1'))
from auth.google_auth import get_drive_service
from sync import get_files_to_update, mark_file_synced, load_synced
from chunking.splitter import chunk_text
# from extractor.pdf import extract_text_from_pdf  # Commented out - requires PyMuPDF
from extractor.markdown import extract_text_from_md
from extractor.docs import extract_text_from_docs
from extractor.sheets import extract_text_from_sheets
from extractor.slides import extract_text_from_slides
from extractor.text import extract_text_from_txt
# from extractor.docx import extract_text_from_docx  # Commented out - requires python-docx
# from extractor.pptx import extract_text_from_pptx  # Commented out - requires python-pptx
# from extractor.xlsx import extract_text_from_xlsx  # Commented out - requires openpyxl

logger = setup_logger(__name__)

class GoogleDriveConnector:
    """Connector to sync Google Drive content and store in ChromaDB for similarity search."""
    
    def __init__(self):
        """Initialize the Google Drive connector."""
        self.collection_name = "google_drive_content"
        self.chroma_client = ChromaDBClient()
        
        # Use sentence transformers for embeddings
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Get or create Google Drive collection
        self.collection = self.chroma_client.get_or_create_collection(
            collection_name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"source": "google_drive", "description": "Google Drive documents"}
        )
        
        # File type extractors mapping
        self.extractors = {
            # '.pdf': extract_text_from_pdf,  # Commented out - requires PyMuPDF
            '.md': extract_text_from_md,
            '.gdoc': extract_text_from_docs,
            '.gsheet': extract_text_from_sheets,
            '.gslides': extract_text_from_slides,
            '.txt': extract_text_from_txt,
            # '.docx': extract_text_from_docx,  # Commented out - requires python-docx
            # '.pptx': extract_text_from_pptx,  # Commented out - requires python-pptx
            # '.xlsx': extract_text_from_xlsx,  # Commented out - requires openpyxl
        }
        
        logger.info(f"GoogleDriveConnector initialized with collection: {self.collection_name}")
    
    def _generate_doc_id(self, file_id: str, chunk_index: int) -> str:
        """Generate a unique document ID based on file ID and chunk index."""
        return f"gdrive_{file_id}_{chunk_index}"
    
    def _enhance_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance metadata with additional fields for better citations."""
        enhanced = metadata.copy()
        
        # Add source type for filtering
        enhanced["source_type"] = "google_drive"
        
        # Add indexing timestamp
        enhanced["indexed_at"] = datetime.now().isoformat()
        
        # Generate Google Drive URL if file_id exists
        if "file_id" in enhanced:
            enhanced["google_drive_url"] = f"https://drive.google.com/file/d/{enhanced['file_id']}/view"
        
        return enhanced
    
    async def sync_google_drive_content(self) -> Dict[str, Any]:
        """Sync Google Drive content."""
        try:
            logger.info("Starting Google Drive content sync")
            
            # Check if credentials exist
            creds_path = os.path.join(os.path.dirname(__file__), 'v1', 'credentials.json')
            if not os.path.exists(creds_path):
                return {
                    "status": "error",
                    "message": "Google Drive credentials.json not found. Please set up OAuth credentials.",
                    "documents_indexed": 0
                }
            
            # Get Drive service
            try:
                service = get_drive_service()
                logger.info("Authenticated to Google Drive successfully")
            except Exception as e:
                logger.error(f"Failed to authenticate to Google Drive: {e}")
                return {
                    "status": "error",
                    "message": f"Authentication failed: {str(e)}",
                    "documents_indexed": 0
                }
            
            # Get files to update
            files_to_update = get_files_to_update(service)
            logger.info(f"Found {len(files_to_update)} files to process")
            
            if not files_to_update:
                return {
                    "status": "success",
                    "message": "No new or updated files to sync",
                    "documents_indexed": 0,
                    "files_processed": 0
                }
            
            # Clear existing documents for files that will be updated
            existing_ids = []
            try:
                all_docs = self.collection.get()
                if all_docs and "ids" in all_docs and "metadatas" in all_docs:
                    for i, metadata in enumerate(all_docs["metadatas"]):
                        if metadata and "file_id" in metadata:
                            for file in files_to_update:
                                if metadata["file_id"] == file["id"]:
                                    existing_ids.append(all_docs["ids"][i])
                    
                    if existing_ids:
                        self.collection.delete(ids=existing_ids)
                        logger.info(f"Cleared {len(existing_ids)} existing documents for updated files")
            except Exception as e:
                logger.warning(f"Error clearing existing documents: {e}")
            
            # Process each file
            documents_indexed = 0
            files_processed = 0
            errors = []
            
            for file in files_to_update:
                file_name = file['name']
                file_id = file['id']
                ext = os.path.splitext(file_name)[-1].lower()
                mime_type = file.get("mimeType", "")
                
                logger.info(f"Processing: {file_name} (ID: {file_id})")
                
                if ext in self.extractors:
                    try:
                        # Extract text using appropriate extractor
                        extractor = self.extractors[ext]
                        text = extractor(service, file_id)
                        
                        if not text or not text.strip():
                            logger.warning(f"No text extracted from {file_name}")
                            continue
                        
                        # Chunk the text
                        chunks = chunk_text(text, chunk_size=1000, overlap=200)
                        
                        # Store each chunk in ChromaDB
                        for i, chunk in enumerate(chunks):
                            doc_id = self._generate_doc_id(file_id, i)
                            
                            metadata = {
                                "file_id": file_id,
                                "file_name": file_name,
                                "chunk_index": i,
                                "total_chunks": len(chunks),
                                "file_type": ext,
                                "mime_type": mime_type,
                                "modified_time": file.get('modifiedTime', ''),
                            }
                            
                            self.collection.add(
                                documents=[chunk],
                                metadatas=[self._enhance_metadata(metadata)],
                                ids=[doc_id]
                            )
                            documents_indexed += 1
                        
                        # Mark file as synced
                        mark_file_synced(file)
                        files_processed += 1
                        logger.info(f"Successfully indexed {file_name} ({len(chunks)} chunks)")
                        
                    except Exception as e:
                        error_msg = f"Failed to process {file_name}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({"file": file_name, "error": str(e)})
                else:
                    logger.info(f"Skipped unsupported file type: {file_name} ({ext})")
            
            return {
                "status": "success",
                "message": f"Synced {files_processed} files from Google Drive",
                "documents_indexed": documents_indexed,
                "files_processed": files_processed,
                "total_files_checked": len(files_to_update),
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error during Google Drive sync: {e}")
            return {
                "status": "error",
                "message": str(e),
                "documents_indexed": 0
            }
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search Google Drive content using similarity search."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            if not results or not results["documents"] or not results["documents"][0]:
                return []
            
            formatted_results = []
            for i in range(len(results["documents"][0])):
                result = {
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                }
                formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching Google Drive content: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the Google Drive collection."""
        try:
            # Get collection count
            collection_data = self.collection.get()
            doc_count = len(collection_data["ids"]) if collection_data and "ids" in collection_data else 0
            
            # Get unique files
            unique_files = {}
            if collection_data and "metadatas" in collection_data:
                for metadata in collection_data["metadatas"]:
                    if metadata and "file_id" in metadata:
                        file_id = metadata["file_id"]
                        if file_id not in unique_files:
                            unique_files[file_id] = {
                                "name": metadata.get("file_name", "Unknown"),
                                "type": metadata.get("file_type", "Unknown"),
                                "chunks": 0
                            }
                        unique_files[file_id]["chunks"] += 1
            
            # Load sync status
            sync_file_path = os.path.join(os.path.dirname(__file__), 'v1', 'last_sync.json')
            last_sync_info = {}
            if os.path.exists(sync_file_path):
                try:
                    with open(sync_file_path, 'r') as f:
                        last_sync_info = json.load(f)
                except:
                    pass
            
            return {
                "collection_name": self.collection_name,
                "total_documents": doc_count,
                "unique_files": len(unique_files),
                "files_list": list(unique_files.values())[:10],  # First 10 files
                "total_synced_files": len(last_sync_info)
            }
            
        except Exception as e:
            logger.error(f"Error getting Google Drive stats: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }