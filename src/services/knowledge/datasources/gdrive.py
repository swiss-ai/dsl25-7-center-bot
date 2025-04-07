import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO
import tempfile
import re
import datetime

from services.knowledge.document_processor import DocumentProcessor

# Add a placeholder GoogleDriveManager class to fix import errors
class GoogleDriveManager:
    """
    Google Drive content management for the vector database.
    This is a placeholder to fix import errors.
    """
    
    def __init__(self, document_processor=None, vector_db=None):
        self.document_processor = document_processor
        self.vector_db = vector_db

logger = logging.getLogger(__name__)

# Define the scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# File MIME types and their handlers
SUPPORTED_MIME_TYPES = {
    'application/vnd.google-apps.document': 'export_google_doc',
    'application/vnd.google-apps.spreadsheet': 'export_google_sheet',
    'application/vnd.google-apps.presentation': 'export_google_presentation',
    'application/pdf': 'download_pdf',
    'text/plain': 'download_text',
    'text/markdown': 'download_text',
    'text/csv': 'download_text',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'download_binary',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'download_binary',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'download_binary'
}

# Export MIME types for Google Workspace files
EXPORT_MIME_TYPES = {
    'application/vnd.google-apps.document': 'text/plain',
    'application/vnd.google-apps.spreadsheet': 'text/csv',
    'application/vnd.google-apps.presentation': 'text/plain'
}

class GoogleDriveMCP:
    """Google Drive integration for the MCP protocol."""
    
    def __init__(
        self, 
        credentials_path: str = None, 
        token_path: str = None,
        document_processor: Optional[DocumentProcessor] = None
    ):
        """
        Initialize the Google Drive client.
        
        Args:
            credentials_path: Path to the client_secret.json file
            token_path: Path to save/load the user's access token
            document_processor: Optional DocumentProcessor for storing documents
        """
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH')
        self.token_path = token_path or os.getenv('GOOGLE_TOKEN_PATH')
        self.service = None
        self.document_processor = document_processor
        
        # If credential paths provided, authenticate
        if self.credentials_path and self.token_path:
            self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive."""
        creds = None
        
        # Load saved credentials if they exist
        if os.path.exists(self.token_path):
            with open(self.token_path, 'r') as token:
                creds = Credentials.from_authorized_user_info(
                    json.load(token), SCOPES
                )
        
        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build the service
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("Google Drive API authenticated successfully")
    
    async def list_files(
        self, 
        query: str = None, 
        page_size: int = 10, 
        order_by: str = "modifiedTime desc",
        fields: str = "files(id, name, mimeType, modifiedTime, createdTime, description, webViewLink)"
    ) -> List[Dict[str, Any]]:
        """
        List files in Google Drive.
        
        Args:
            query: Search query (Google Drive Query Language)
            page_size: Number of files to return
            order_by: Sort order
            fields: Fields to include in the response
            
        Returns:
            List of file metadata
        """
        if not self.service:
            logger.error("Google Drive API not authenticated")
            return []
        
        try:
            # Execute the request in a separate thread
            loop = asyncio.get_event_loop()
            request = self.service.files().list(
                q=query,
                pageSize=page_size,
                orderBy=order_by,
                fields=f"nextPageToken, {fields}"
            )
            
            response = await loop.run_in_executor(None, request.execute)
            
            return response.get('files', [])
        
        except Exception as e:
            logger.error(f"Error listing files from Google Drive: {e}")
            return []
    
    async def search_files(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of file metadata
        """
        # Format the query for Google Drive's query language
        # This searches in file name and full-text content
        formatted_query = f"fullText contains '{query}' or name contains '{query}'"
        
        # Log the exact query being used
        logger.info(f"Searching Google Drive with query: {formatted_query}")
        
        results = await self.list_files(
            query=formatted_query,
            page_size=max_results
        )
        
        # Log what was found
        if results:
            logger.info(f"Found {len(results)} files in Google Drive matching '{query}'")
            for i, file in enumerate(results):
                logger.info(f"  {i+1}. {file.get('name', 'Untitled')} ({file.get('mimeType', 'Unknown type')})")
        else:
            logger.info(f"No files found in Google Drive matching '{query}'")
            
        return results
    
    async def get_file_content(self, file_id: str, mime_type: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        Get the content of a file from Google Drive.
        
        Args:
            file_id: The ID of the file
            mime_type: Optional MIME type to specify format
            
        Returns:
            Tuple of (content, metadata)
        """
        if not self.service:
            logger.error("Google Drive API not authenticated")
            return "", {}
        
        try:
            # Get file metadata
            loop = asyncio.get_event_loop()
            file_request = self.service.files().get(
                fileId=file_id, 
                fields="id, name, mimeType, description, modifiedTime, createdTime, webViewLink, owners"
            )
            file_metadata = await loop.run_in_executor(None, file_request.execute)
            
            # Determine how to handle the file based on MIME type
            actual_mime_type = mime_type or file_metadata.get('mimeType')
            handler_name = SUPPORTED_MIME_TYPES.get(actual_mime_type)
            
            if not handler_name:
                logger.warning(f"Unsupported MIME type: {actual_mime_type}")
                return f"Unsupported file type: {actual_mime_type}", file_metadata
            
            # Call the appropriate handler method
            handler_method = getattr(self, handler_name, None)
            if handler_method:
                content = await handler_method(file_id, file_metadata)
                return content, file_metadata
            else:
                logger.error(f"Handler method {handler_name} not found")
                return "", file_metadata
        
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return f"Error: {str(e)}", {}
    
    async def export_google_doc(self, file_id: str, metadata: Dict[str, Any]) -> str:
        """Export a Google Doc to plain text."""
        try:
            loop = asyncio.get_event_loop()
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType='text/plain'
            )
            
            file_content = BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                # Execute downloader in thread pool
                status, done = await loop.run_in_executor(None, downloader.next_chunk)
            
            return file_content.getvalue().decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error exporting Google Doc: {e}")
            return f"Error exporting Google Doc: {str(e)}"
    
    async def export_google_sheet(self, file_id: str, metadata: Dict[str, Any]) -> str:
        """Export a Google Sheet to CSV."""
        try:
            loop = asyncio.get_event_loop()
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType='text/csv'
            )
            
            file_content = BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                # Execute downloader in thread pool
                status, done = await loop.run_in_executor(None, downloader.next_chunk)
            
            return file_content.getvalue().decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error exporting Google Sheet: {e}")
            return f"Error exporting Google Sheet: {str(e)}"
    
    async def export_google_presentation(self, file_id: str, metadata: Dict[str, Any]) -> str:
        """Export a Google Presentation to plain text."""
        try:
            loop = asyncio.get_event_loop()
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType='text/plain'
            )
            
            file_content = BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                # Execute downloader in thread pool
                status, done = await loop.run_in_executor(None, downloader.next_chunk)
            
            return file_content.getvalue().decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error exporting Google Presentation: {e}")
            return f"Error exporting Google Presentation: {str(e)}"
    
    async def download_text(self, file_id: str, metadata: Dict[str, Any]) -> str:
        """Download a text file."""
        try:
            loop = asyncio.get_event_loop()
            request = self.service.files().get_media(fileId=file_id)
            
            file_content = BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                # Execute downloader in thread pool
                status, done = await loop.run_in_executor(None, downloader.next_chunk)
            
            return file_content.getvalue().decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error downloading text file: {e}")
            return f"Error downloading text file: {str(e)}"
    
    async def download_pdf(self, file_id: str, metadata: Dict[str, Any]) -> str:
        """Download a PDF file and extract text."""
        try:
            # Get direct download link instead of using MediaIoBaseDownload
            # This approach is less likely to have SSL issues
            file_name = metadata.get('name', 'unknown')
            
            # Instead of trying to download directly, use the webViewLink for PDFs
            # and provide information about the file
            web_link = metadata.get('webViewLink', '')
            
            # For now, use a placeholder with the link to the file
            # In a production system, you'd use PyPDF2 or a similar library to extract text
            text = f"""## PDF File: {file_name}
            
This is a PDF document in your Google Drive. Due to current limitations, the text content cannot be extracted automatically.

You can view this document directly in Google Drive: {web_link}

File properties:
- Created: {metadata.get('createdTime', 'Unknown')}
- Modified: {metadata.get('modifiedTime', 'Unknown')}
- Size: {metadata.get('size', 'Unknown')} bytes

To fully extract PDF content, you would need to implement a PDF extraction library like PyPDF2, pdfplumber, or pymupdf.
"""
            return text
        
        except Exception as e:
            logger.error(f"Error handling PDF file: {e}")
            return f"Error handling PDF file {metadata.get('name', 'unknown')}: {str(e)}"
    
    async def download_binary(self, file_id: str, metadata: Dict[str, Any]) -> str:
        """Handle a binary file (DOCX, XLSX, PPTX)."""
        try:
            file_name = metadata.get('name', 'unknown')
            file_type = metadata.get('mimeType', 'unknown')
            web_link = metadata.get('webViewLink', '')
            
            # For now, provide information about the file without downloading
            text = f"""## Binary File: {file_name}
            
This is a binary document ({file_type}) in your Google Drive. Due to current limitations, the text content cannot be extracted automatically.

You can view this document directly in Google Drive: {web_link}

File properties:
- Type: {file_type}
- Created: {metadata.get('createdTime', 'Unknown')}
- Modified: {metadata.get('modifiedTime', 'Unknown')}
- Size: {metadata.get('size', 'Unknown')} bytes

To fully extract content from this file type, you would need specialized libraries like python-docx, openpyxl, or similar.
"""
            return text
        except Exception as e:
            logger.error(f"Error handling binary file: {e}")
            return f"Error handling binary file {metadata.get('name', 'unknown')}: {str(e)}"
    
    async def process_file_to_vector_db(self, file_id: str) -> bool:
        """
        Process a file and add it to the vector database.
        
        Args:
            file_id: The ID of the file
            
        Returns:
            bool: Success status
        """
        if not self.document_processor:
            logger.error("Document processor not available")
            return False
        
        try:
            # Get the file content and metadata
            content, metadata = await self.get_file_content(file_id)
            
            if not content:
                logger.error(f"Failed to get content for file {file_id}")
                return False
            
            # Prepare metadata for the document processor
            doc_metadata = {
                "doc_id": f"gdrive_{file_id}",
                "title": metadata.get("name", "Untitled Google Drive Document"),
                "source": "google_drive",
                "url": metadata.get("webViewLink", ""),
                "author": self._get_authors(metadata),
                "created_at": metadata.get("createdTime", ""),
                "modified_at": metadata.get("modifiedTime", ""),
                "mime_type": metadata.get("mimeType", ""),
                "description": metadata.get("description", ""),
                "tags": ["google_drive"]
            }
            
            # Process the document
            chunk_ids = await self.document_processor.process_document(
                content=content,
                metadata=doc_metadata
            )
            
            logger.info(f"Added Google Drive file {file_id} to vector database in {len(chunk_ids)} chunks")
            return True
        
        except Exception as e:
            logger.error(f"Error processing Google Drive file {file_id}: {e}")
            return False
    
    async def sync_recent_files(self, query: str = None, max_files: int = 20) -> int:
        """
        Sync recent files to the vector database.
        
        Args:
            query: Optional query to filter files
            max_files: Maximum number of files to sync
            
        Returns:
            int: Number of files synced
        """
        if not self.document_processor:
            logger.error("Document processor not available")
            return 0
        
        # Default query to get files of supported types, ordered by most recent
        default_query = "trashed = false and ("
        mime_types = list(SUPPORTED_MIME_TYPES.keys())
        for i, mime_type in enumerate(mime_types):
            if i > 0:
                default_query += " or "
            default_query += f"mimeType = '{mime_type}'"
        default_query += ")"
        
        # Combine with provided query if any
        combined_query = default_query
        if query:
            combined_query = f"({default_query}) and ({query})"
        
        # Get file list
        files = await self.list_files(
            query=combined_query,
            page_size=max_files,
            order_by="modifiedTime desc"
        )
        
        if not files:
            logger.info("No files found to sync")
            return 0
        
        # Process each file
        synced_count = 0
        for file in files:
            success = await self.process_file_to_vector_db(file['id'])
            if success:
                synced_count += 1
        
        logger.info(f"Synced {synced_count} Google Drive files to vector database")
        return synced_count
    
    def _get_authors(self, metadata: Dict[str, Any]) -> str:
        """Extract author information from file metadata."""
        owners = metadata.get("owners", [])
        if not owners:
            return "Unknown"
        
        names = [owner.get("displayName", "Unknown") for owner in owners]
        return ", ".join(names)