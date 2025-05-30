#!/usr/bin/env python3
"""Test Email sync functionality"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_sources.email.connector import EmailConnector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def test_email_sync():
    """Test Email sync and search"""
    try:
        # Initialize connector
        logger.info("Initializing Email connector...")
        connector = EmailConnector()
        
        # Get initial stats
        stats = connector.get_stats()
        logger.info(f"Initial stats: {stats}")
        
        # Check if credentials exist (using same as Google Drive)
        creds_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'knowledge_sources', 'google_drive', 'v1', 'credentials.json')
        if not os.path.exists(creds_path):
            logger.error(f"Gmail credentials not found at: {creds_path}")
            logger.info("\nTo set up Gmail integration:")
            logger.info("1. Go to https://console.cloud.google.com/")
            logger.info("2. Enable Gmail API in the same project as Google Drive")
            logger.info("3. Add Gmail scope to existing OAuth credentials")
            logger.info("4. Required scopes: gmail.modify, drive.readonly")
            logger.info("5. Delete existing token files to regenerate with new scopes")
            return
        
        # Perform sync
        logger.info("Starting Gmail email sync...")
        sync_result = await connector.sync_gmail_emails(max_emails=20)  # Limit for testing
        
        logger.info(f"Sync result: {sync_result}")
        
        if sync_result["status"] == "success":
            logger.info(f"Successfully indexed {sync_result.get('emails_indexed', 0)} emails")
            
            # Test search if emails were indexed
            if sync_result.get('emails_indexed', 0) > 0:
                test_queries = [
                    "meeting",
                    "project", 
                    "report",
                    "schedule",
                    "follow up"
                ]
                
                for query in test_queries:
                    logger.info(f"\nSearching for: '{query}'")
                    results = connector.search(query, n_results=3)
                    
                    if results:
                        logger.info(f"Found {len(results)} results:")
                        for i, result in enumerate(results):
                            metadata = result.get("metadata", {})
                            content_preview = result.get("content", "")[:200]
                            logger.info(f"\n[{i+1}] Subject: {metadata.get('subject', 'N/A')}")
                            logger.info(f"    From: {metadata.get('from', 'N/A')}")
                            logger.info(f"    Date: {metadata.get('date', 'N/A')}")
                            logger.info(f"    Gmail URL: {metadata.get('gmail_url', 'N/A')}")
                            logger.info(f"    Content: {content_preview}...")
                    else:
                        logger.info("No results found")
            else:
                logger.info("\nNo emails were indexed. Make sure you have emails in your Gmail inbox.")
            
            # Get final stats
            final_stats = connector.get_stats()
            logger.info(f"\nFinal stats: {final_stats}")
            
        else:
            logger.error(f"Sync failed: {sync_result.get('message', 'Unknown error')}")
            if sync_result.get("errors"):
                for error in sync_result["errors"]:
                    logger.error(f"  - {error}")
                    
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_email_sync())