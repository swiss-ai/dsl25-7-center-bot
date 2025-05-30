import asyncio
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.knowledge_sources.notion.connector import NotionConnector
from src.knowledge_sources.airtable.connector import AirtableConnector
from src.knowledge_sources.web_scraper.connector import WebScraperConnector
from src.knowledge_sources.google_drive.connector import GoogleDriveConnector
from src.knowledge_sources.email.connector import EmailConnector
from src.utils.logger import setup_logger
from src.utils.config import Config

logger = setup_logger(__name__)

class KnowledgeSyncManager:
    def __init__(self):
        """Initialize the sync manager with scheduler"""
        self.scheduler = AsyncIOScheduler()
        self.notion_connector = NotionConnector()
        self.airtable_connector = AirtableConnector()
        self.web_scraper_connector = WebScraperConnector()
        self.google_drive_connector = GoogleDriveConnector()
        self.email_connector = EmailConnector()
        self.sync_interval_hours = 1  # Default to sync every hour
        
        logger.info("Knowledge sync manager initialized")
    
    async def sync_notion(self):
        """Sync Notion content"""
        try:
            logger.info("Starting scheduled Notion sync...")
            result = await self.notion_connector.sync_notion_content()
            
            if result["status"] == "success":
                logger.info(f"Notion sync completed: {result['documents_indexed']} documents indexed")
            else:
                logger.error(f"Notion sync failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled Notion sync: {e}")
    
    async def sync_airtable(self):
        """Sync Airtable content"""
        try:
            logger.info("Starting scheduled Airtable sync...")
            result = await self.airtable_connector.sync_airtable_content()
            
            if result["status"] == "success":
                logger.info(f"Airtable sync completed: {result['documents_indexed']} documents indexed")
                logger.info(f"Tables indexed: {result.get('tables_indexed', {})}")
            else:
                logger.error(f"Airtable sync failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled Airtable sync: {e}")
    
    async def sync_web_content(self):
        """Sync web scraper content"""
        try:
            logger.info("Starting scheduled web content sync...")
            result = await self.web_scraper_connector.sync_web_content()
            
            if result["status"] == "success":
                logger.info(f"Web content sync completed: {result['synced_count']} URLs synced")
            else:
                logger.error(f"Web content sync failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled web content sync: {e}")
    
    async def sync_google_drive(self):
        """Sync Google Drive content"""
        try:
            logger.info("Starting scheduled Google Drive sync...")
            result = await self.google_drive_connector.sync_google_drive_content()
            
            if result["status"] == "success":
                logger.info(f"Google Drive sync completed: {result['documents_indexed']} documents indexed")
                logger.info(f"Files processed: {result.get('files_processed', 0)}")
            else:
                logger.error(f"Google Drive sync failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled Google Drive sync: {e}")
    
    async def sync_email(self):
        """Sync Email content"""
        try:
            logger.info("Starting scheduled Email sync...")
            result = await self.email_connector.sync_gmail_emails()
            
            if result["status"] == "success":
                logger.info(f"Email sync completed: {result['emails_indexed']} emails indexed")
            else:
                logger.error(f"Email sync failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled Email sync: {e}")
    
    async def initial_sync(self):
        """Perform initial sync of all knowledge sources"""
        logger.info("Performing initial knowledge sync...")
        
        # Sync Notion
        if Config.NOTION_API_KEY and Config.NOTION_PAGES:
            await self.sync_notion()
        else:
            logger.warning("Notion credentials not configured, skipping Notion sync")
        
        # Sync Airtable
        if Config.AIRTABLE_API_KEY and Config.AIRTABLE_BASE_ID:
            await self.sync_airtable()
        else:
            logger.warning("Airtable credentials not configured, skipping Airtable sync")
        
        # Sync Web Content
        await self.sync_web_content()  # Always run as it reads from URLs file
        
        # Sync Google Drive
        # Check if credentials exist before attempting sync
        creds_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_sources', 'google_drive', 'v1', 'credentials.json')
        if os.path.exists(creds_path):
            await self.sync_google_drive()
        else:
            logger.warning("Google Drive credentials not configured, skipping Google Drive sync")
        
        # Sync Email
        # Check if credentials exist before attempting sync (use same as Google Drive)
        email_creds_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_sources', 'google_drive', 'v1', 'credentials.json')
        if os.path.exists(email_creds_path):
            await self.sync_email()
        else:
            logger.warning("Email credentials not configured, skipping Email sync")
    
    def start_periodic_sync(self):
        """Start periodic synchronization"""
        # Schedule Notion sync
        if Config.NOTION_API_KEY and Config.NOTION_PAGES:
            self.scheduler.add_job(
                self.sync_notion,
                'interval',
                hours=self.sync_interval_hours,
                id='notion_sync',
                next_run_time=datetime.now()  # Run immediately on start
            )
            logger.info(f"Scheduled Notion sync every {self.sync_interval_hours} hour(s)")
        
        # Schedule Airtable sync
        if Config.AIRTABLE_API_KEY and Config.AIRTABLE_BASE_ID:
            self.scheduler.add_job(
                self.sync_airtable,
                'interval',
                hours=self.sync_interval_hours,
                id='airtable_sync',
                next_run_time=datetime.now()  # Run immediately on start
            )
            logger.info(f"Scheduled Airtable sync every {self.sync_interval_hours} hour(s)")
        
        # Schedule Web Content sync
        self.scheduler.add_job(
            self.sync_web_content,
            'interval',
            hours=self.sync_interval_hours,
            id='web_content_sync',
            next_run_time=datetime.now()  # Run immediately on start
        )
        logger.info(f"Scheduled Web Content sync every {self.sync_interval_hours} hour(s)")
        
        # Schedule Google Drive sync if credentials exist
        import os
        creds_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_sources', 'google_drive', 'v1', 'credentials.json')
        if os.path.exists(creds_path):
            self.scheduler.add_job(
                self.sync_google_drive,
                'interval',
                hours=self.sync_interval_hours,
                id='google_drive_sync',
                next_run_time=datetime.now()  # Run immediately on start
            )
            logger.info(f"Scheduled Google Drive sync every {self.sync_interval_hours} hour(s)")
        
        # Schedule Email sync if credentials exist (use same as Google Drive)
        email_creds_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_sources', 'google_drive', 'v1', 'credentials.json')
        if os.path.exists(email_creds_path):
            self.scheduler.add_job(
                self.sync_email,
                'interval',
                hours=self.sync_interval_hours,
                id='email_sync',
                next_run_time=datetime.now()  # Run immediately on start
            )
            logger.info(f"Scheduled Email sync every {self.sync_interval_hours} hour(s)")
        
        # Start the scheduler
        self.scheduler.start()
        logger.info("Periodic sync scheduler started")
    
    def stop_periodic_sync(self):
        """Stop periodic synchronization"""
        self.scheduler.shutdown()
        logger.info("Periodic sync scheduler stopped")
    
    async def manual_sync(self, source: str = "all") -> dict:
        """Manually trigger a sync for specific source or all sources"""
        results = {}
        
        if source in ["notion", "all"]:
            logger.info("Manually triggering Notion sync...")
            results["notion"] = await self.notion_connector.sync_notion_content()
        
        if source in ["airtable", "all"]:
            logger.info("Manually triggering Airtable sync...")
            results["airtable"] = await self.airtable_connector.sync_airtable_content()
        
        if source in ["web_content", "all"]:
            logger.info("Manually triggering Web content sync...")
            results["web_content"] = await self.web_scraper_connector.sync_web_content()
        
        if source in ["google_drive", "all"]:
            logger.info("Manually triggering Google Drive sync...")
            results["google_drive"] = await self.google_drive_connector.sync_google_drive_content()
        
        if source in ["email", "all"]:
            logger.info("Manually triggering Email sync...")
            results["email"] = await self.email_connector.sync_gmail_emails()
        
        return results
    
    def get_sync_status(self) -> dict:
        """Get current sync status and statistics"""
        status = {
            "scheduler_running": self.scheduler.running,
            "scheduled_jobs": [],
            "knowledge_sources": {}
        }
        
        # Get scheduled jobs
        for job in self.scheduler.get_jobs():
            status["scheduled_jobs"].append({
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        # Get Notion stats
        if Config.NOTION_API_KEY:
            status["knowledge_sources"]["notion"] = self.notion_connector.get_stats()
        
        # Get Airtable stats
        if Config.AIRTABLE_API_KEY:
            status["knowledge_sources"]["airtable"] = self.airtable_connector.get_stats()
        
        # Get Web Content stats
        status["knowledge_sources"]["web_content"] = self.web_scraper_connector.get_stats()
        
        # Get Google Drive stats
        status["knowledge_sources"]["google_drive"] = self.google_drive_connector.get_stats()
        
        # Get Email stats
        status["knowledge_sources"]["email"] = self.email_connector.get_stats()
        
        return status