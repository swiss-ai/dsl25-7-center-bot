import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import sys
import json
import asyncio
import base64

from src.storage.chroma_client import ChromaDBClient
from src.utils.config import Config
from src.utils.logger import setup_logger
from chromadb.utils import embedding_functions

# Import email functions using importlib to avoid naming conflicts
import importlib.util
import pathlib

v1_path = os.path.join(os.path.dirname(__file__), 'v1')
email_module_path = os.path.join(v1_path, 'email.py')

spec = importlib.util.spec_from_file_location("email_module", email_module_path)
email_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(email_module)

# Extract the functions we need
_load_creds = email_module._load_creds
_get_plain_body = email_module._get_plain_body
_split = email_module._split
SCOPES = email_module.SCOPES

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = setup_logger(__name__)

class EmailConnector:
    """Connector to sync Gmail emails and store in ChromaDB for similarity search."""
    
    def __init__(self):
        """Initialize the Email connector."""
        self.collection_name = "email_content"
        self.chroma_client = ChromaDBClient()
        
        # Use sentence transformers for embeddings
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Get or create Email collection
        self.collection = self.chroma_client.get_or_create_collection(
            collection_name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"source": "email", "description": "Gmail emails"}
        )
        
        # Gmail service will be initialized when needed
        self.gmail_service = None
        self.credentials = None
        
        # Track last history ID for incremental sync
        self.last_history_id_file = os.path.join(os.path.dirname(__file__), 'v1', 'last_history_id.json')
        
        logger.info(f"EmailConnector initialized with collection: {self.collection_name}")
    
    def _generate_doc_id(self, message_id: str) -> str:
        """Generate a unique document ID based on Gmail message ID."""
        return f"email_{message_id}"
    
    def _enhance_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance metadata with additional fields for better citations."""
        enhanced = metadata.copy()
        
        # Add source type for filtering
        enhanced["source_type"] = "email"
        
        # Add indexing timestamp
        enhanced["indexed_at"] = datetime.now().isoformat()
        
        # Generate Gmail URL if message_id exists
        if "message_id" in enhanced:
            enhanced["gmail_url"] = f"https://mail.google.com/mail/u/0/#inbox/{enhanced['message_id']}"
        
        return enhanced
    
    def _load_last_history_id(self) -> Optional[str]:
        """Load the last processed history ID."""
        if os.path.exists(self.last_history_id_file):
            try:
                with open(self.last_history_id_file, 'r') as f:
                    data = json.load(f)
                    return data.get('last_history_id')
            except:
                pass
        return None
    
    def _save_last_history_id(self, history_id: str):
        """Save the last processed history ID."""
        os.makedirs(os.path.dirname(self.last_history_id_file), exist_ok=True)
        with open(self.last_history_id_file, 'w') as f:
            json.dump({'last_history_id': history_id, 'timestamp': datetime.now().isoformat()}, f)
    
    async def _initialize_gmail_service(self) -> bool:
        """Initialize Gmail service with authentication."""
        try:
            # Use the same credentials as Google Drive
            creds_path = os.path.join(os.path.dirname(__file__), '..', 'google_drive', 'v1', 'credentials.json')
            token_path = os.path.join(os.path.dirname(__file__), 'v1', 'token.json')
            
            if not os.path.exists(creds_path):
                logger.error("Gmail credentials.json not found")
                return False
            
            self.credentials = _load_creds(creds_path, token_path)
            self.gmail_service = build("gmail", "v1", credentials=self.credentials, cache_discovery=False)
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            return False
    
    def _extract_email_headers(self, headers: List[Dict[str, str]]) -> Dict[str, str]:
        """Extract relevant headers from email."""
        header_dict = {h["name"].lower(): h["value"] for h in headers}
        return {
            "from": header_dict.get("from", ""),
            "to": header_dict.get("to", ""),
            "subject": header_dict.get("subject", "No Subject"),
            "date": header_dict.get("date", ""),
            "message_id": header_dict.get("message-id", ""),
        }
    
    async def sync_gmail_emails(self, max_emails: int = 100) -> Dict[str, Any]:
        """Sync Gmail emails to ChromaDB."""
        try:
            logger.info("Starting Gmail email sync")
            
            # Initialize Gmail service if needed
            if not self.gmail_service:
                if not await self._initialize_gmail_service():
                    return {
                        "status": "error",
                        "message": "Failed to initialize Gmail service. Please check credentials.",
                        "emails_indexed": 0
                    }
            
            # Get user profile for initial history ID
            profile = self.gmail_service.users().getProfile(userId="me").execute()
            current_history_id = profile["historyId"]
            
            # Load last history ID or use current if first sync
            last_history_id = self._load_last_history_id()
            if not last_history_id:
                # First sync - get recent messages
                logger.info("First sync - fetching recent messages")
                messages_response = self.gmail_service.users().messages().list(
                    userId="me",
                    maxResults=max_emails,
                    labelIds=["INBOX"]
                ).execute()
                
                messages = messages_response.get("messages", [])
                emails_indexed = 0
                errors = []
                
                for msg_ref in messages:
                    try:
                        # Get full message
                        msg = self.gmail_service.users().messages().get(
                            userId="me",
                            id=msg_ref["id"],
                            format="full"
                        ).execute()
                        
                        # Skip if already in DB
                        doc_id = self._generate_doc_id(msg["id"])
                        existing = self.collection.get(ids=[doc_id])
                        if existing and existing["ids"]:
                            continue
                        
                        # Extract email content
                        headers = self._extract_email_headers(msg["payload"]["headers"])
                        body = _get_plain_body(msg)
                        
                        if not body.strip():
                            continue
                        
                        # Split into fresh and quoted content
                        try:
                            fresh_content, quoted_content = _split(body)
                        except Exception as e:
                            # Fallback if talon fails
                            logger.warning(f"Talon extraction failed, using full body: {e}")
                            fresh_content = body
                            quoted_content = ""
                        
                        # Combine for storage but mark sections
                        full_content = f"Subject: {headers['subject']}\n\n"
                        full_content += f"From: {headers['from']}\n"
                        full_content += f"To: {headers['to']}\n"
                        full_content += f"Date: {headers['date']}\n\n"
                        full_content += f"--- Message Content ---\n{fresh_content}\n"
                        
                        if quoted_content:
                            full_content += f"\n--- Quoted/Previous Content ---\n{quoted_content}"
                        
                        # Prepare metadata
                        metadata = {
                            "message_id": msg["id"],
                            "thread_id": msg.get("threadId", ""),
                            "subject": headers["subject"],
                            "from": headers["from"],
                            "to": headers["to"],
                            "date": headers["date"],
                            "snippet": msg.get("snippet", "")[:200],
                            "labels": ",".join(msg.get("labelIds", [])),
                            "has_attachments": any(part.get("filename") for part in msg["payload"].get("parts", [])),
                        }
                        
                        # Store in ChromaDB
                        self.collection.add(
                            documents=[full_content],
                            metadatas=[self._enhance_metadata(metadata)],
                            ids=[doc_id]
                        )
                        emails_indexed += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to process message {msg_ref['id']}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                
                # Save current history ID for next sync
                self._save_last_history_id(current_history_id)
                
                return {
                    "status": "success",
                    "message": f"Initial sync completed. Indexed {emails_indexed} emails",
                    "emails_indexed": emails_indexed,
                    "errors": errors
                }
                
            else:
                # Incremental sync using history
                logger.info(f"Incremental sync from history ID: {last_history_id}")
                
                try:
                    history_response = self.gmail_service.users().history().list(
                        userId="me",
                        startHistoryId=last_history_id,
                        historyTypes=["messageAdded"]
                    ).execute()
                    
                    emails_indexed = 0
                    errors = []
                    
                    for history in history_response.get("history", []):
                        for msg_added in history.get("messagesAdded", []):
                            try:
                                msg_id = msg_added["message"]["id"]
                                
                                # Get full message
                                msg = self.gmail_service.users().messages().get(
                                    userId="me",
                                    id=msg_id,
                                    format="full"
                                ).execute()
                                
                                # Skip sent messages
                                if "SENT" in msg.get("labelIds", []):
                                    continue
                                
                                # Extract content and store
                                headers = self._extract_email_headers(msg["payload"]["headers"])
                                body = _get_plain_body(msg)
                                
                                if not body.strip():
                                    continue
                                
                                try:
                                    fresh_content, quoted_content = _split(body)
                                except Exception as e:
                                    # Fallback if talon fails
                                    logger.warning(f"Talon extraction failed, using full body: {e}")
                                    fresh_content = body
                                    quoted_content = ""
                                
                                full_content = f"Subject: {headers['subject']}\n\n"
                                full_content += f"From: {headers['from']}\n"
                                full_content += f"To: {headers['to']}\n"
                                full_content += f"Date: {headers['date']}\n\n"
                                full_content += f"--- Message Content ---\n{fresh_content}\n"
                                
                                if quoted_content:
                                    full_content += f"\n--- Quoted/Previous Content ---\n{quoted_content}"
                                
                                metadata = {
                                    "message_id": msg["id"],
                                    "thread_id": msg.get("threadId", ""),
                                    "subject": headers["subject"],
                                    "from": headers["from"],
                                    "to": headers["to"],
                                    "date": headers["date"],
                                    "snippet": msg.get("snippet", "")[:200],
                                    "labels": ",".join(msg.get("labelIds", [])),
                                    "has_attachments": any(part.get("filename") for part in msg["payload"].get("parts", [])),
                                }
                                
                                doc_id = self._generate_doc_id(msg["id"])
                                self.collection.add(
                                    documents=[full_content],
                                    metadatas=[self._enhance_metadata(metadata)],
                                    ids=[doc_id]
                                )
                                emails_indexed += 1
                                
                            except Exception as e:
                                error_msg = f"Failed to process message in history: {str(e)}"
                                logger.error(error_msg)
                                errors.append(error_msg)
                    
                    # Update history ID
                    self._save_last_history_id(current_history_id)
                    
                    return {
                        "status": "success",
                        "message": f"Incremental sync completed. Indexed {emails_indexed} new emails",
                        "emails_indexed": emails_indexed,
                        "errors": errors
                    }
                    
                except Exception as e:
                    if "startHistoryId" in str(e):
                        # History too old, do a fresh sync
                        logger.warning("History ID too old, clearing for fresh sync next time")
                        os.remove(self.last_history_id_file)
                        return await self.sync_gmail_emails(max_emails)
                    else:
                        raise
                        
        except Exception as e:
            logger.error(f"Error during Gmail sync: {e}")
            return {
                "status": "error",
                "message": str(e),
                "emails_indexed": 0
            }
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search email content using similarity search."""
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
            logger.error(f"Error searching email content: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the email collection."""
        try:
            # Get collection count
            collection_data = self.collection.get()
            doc_count = len(collection_data["ids"]) if collection_data and "ids" in collection_data else 0
            
            # Get unique senders
            unique_senders = set()
            subjects = []
            if collection_data and "metadatas" in collection_data:
                for metadata in collection_data["metadatas"]:
                    if metadata:
                        if "from" in metadata:
                            unique_senders.add(metadata["from"])
                        if "subject" in metadata:
                            subjects.append(metadata["subject"])
            
            # Get last sync info
            last_sync_info = {}
            if os.path.exists(self.last_history_id_file):
                try:
                    with open(self.last_history_id_file, 'r') as f:
                        last_sync_info = json.load(f)
                except:
                    pass
            
            return {
                "collection_name": self.collection_name,
                "total_emails": doc_count,
                "unique_senders": len(unique_senders),
                "sample_subjects": subjects[:5],
                "last_sync": last_sync_info.get("timestamp", "Never")
            }
            
        except Exception as e:
            logger.error(f"Error getting email stats: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }