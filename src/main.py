import uvicorn
import logging
import asyncio
import os
import traceback
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.slack_routes import router as slack_router
from config.settings import settings, validate_settings
from db.init_db import init_db, create_test_data
from db.vector_db import VectorDB
from middleware.rate_limit import RateLimiter
from services.knowledge.document_processor import DocumentProcessor
from services.knowledge.datasources import GoogleDriveManager, GoogleDriveMCP
from services.slack.mcp_bot import initialize_mcp_client, start_socket_mode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Validate environment variables
try:
    validate_settings()
except Exception as e:
    logger.error(f"Settings validation error: {e}")
    # We'll continue running with default settings

app = FastAPI(title="AI Center Bot")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(
    RateLimiter,
    redis_url=settings.REDIS_URL if settings.USE_REDIS else None,
    max_requests=settings.MAX_REQUESTS_PER_MINUTE
)

# Initialize global services
vector_db = None
document_processor = None
gdrive_manager = None
gdrive_mcp = None  # Legacy Google Drive integration
web_content_manager = None
web_content_sync_service = None
firecrawl_manager = None
notion_manager = None
mcp_slack_client = None  # New MCP Slack client

# Include routers
app.include_router(slack_router, prefix="/api/slack", tags=["slack"])

# Knowledge routes are added in the startup event after document_processor is initialized

@app.get("/")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

@app.get("/status")
async def status():
    """Return the status of various components."""
    global vector_db, gdrive_manager, gdrive_mcp, web_content_manager, web_content_sync_service, firecrawl_manager, notion_manager, mcp_slack_client
    
    # Check Google Drive status
    gdrive_status = "not_initialized"
    if gdrive_manager and hasattr(gdrive_manager, "service") and gdrive_manager.service:
        gdrive_status = "operational"
    elif gdrive_mcp:
        if hasattr(gdrive_mcp, "service") and gdrive_mcp.service:  # Legacy integration
            gdrive_status = "operational"
        elif hasattr(gdrive_mcp, "_is_server_running"):  # MCP integration
            try:
                if await gdrive_mcp._is_server_running():
                    gdrive_status = "operational"
                else:
                    gdrive_status = "server_not_running"
            except Exception as e:
                logger.error(f"Error checking MCP server status: {e}")
                gdrive_status = f"error: {str(e)}"
    
    # Check if Web Content Manager is initialized
    web_content_status = "not_initialized"
    if web_content_manager:
        if web_content_manager.web_fetch and web_content_manager.web_fetch.is_running:
            web_content_status = "operational"
        else:
            web_content_status = "server_not_running"
    
    # Check web content sync status
    web_sync_status = "not_initialized"
    last_sync = None
    if web_content_sync_service:
        if web_content_sync_service.is_running:
            web_sync_status = "operational"
        else:
            web_sync_status = "not_running"
        
        if web_content_sync_service.last_sync_time:
            last_sync = web_content_sync_service.last_sync_time.isoformat()
    
    # Check firecrawl status
    firecrawl_status = "not_initialized"
    firecrawl_info = {}
    if firecrawl_manager:
        try:
            status = firecrawl_manager.get_crawl_status()
            firecrawl_status = "operational" if status.get("is_running", False) else "not_running"
            firecrawl_info = {
                "sites_configured": status.get("sites_configured", 0),
                "sites_crawled": status.get("sites_crawled", 0),
                "current_crawls": status.get("current_crawls", [])
            }
        except Exception as e:
            logger.error(f"Error getting firecrawl status: {e}")
            firecrawl_status = f"error: {str(e)}"
    
    # Check notion status
    notion_status = "not_initialized"
    notion_info = {}
    if notion_manager:
        notion_status = "operational" if settings.NOTION_ENABLED and settings.NOTION_API_KEY else "not_configured"
        notion_info = {
            "enabled": settings.NOTION_ENABLED,
            "pages_configured": len(notion_manager.configured_pages) if notion_manager.configured_pages else 0
        }
    
    # Check MCP Slack bot status
    mcp_slack_status = "not_initialized"
    if mcp_slack_client:
        mcp_slack_status = "operational" if mcp_slack_client.session is not None else "server_not_running"
    
    # Determine Google Drive type
    if settings.GOOGLE_DRIVE_ENABLED:
        gdrive_type = "new"
    elif settings.MCP_GDRIVE_ENABLED:
        gdrive_type = "mcp"
    else:
        gdrive_type = "legacy"
    
    # Determine MCP availability
    try:
        import mcp
        MCP_AVAILABLE = True
    except ImportError:
        MCP_AVAILABLE = False
    
    status_info = {
        "status": "operational",
        "components": {
            "database": "operational",
            "vector_db": "operational" if vector_db else "not_initialized",
            "rate_limiter": "operational" if settings.RATE_LIMIT_ENABLED else "disabled",
            "google_drive": gdrive_status,
            "google_drive_type": gdrive_type,
            "web_content": web_content_status,
            "web_content_sync": web_sync_status,
            "firecrawl": firecrawl_status,
            "notion": notion_status,
            "mcp_slack_bot": mcp_slack_status
        },
        "document_count": vector_db.count() if vector_db else 0,
        "google_drive": {
            "enabled": settings.GOOGLE_DRIVE_ENABLED,
            "credentials_configured": bool(settings.GOOGLE_CREDENTIALS_PATH and settings.GOOGLE_TOKEN_PATH),
            "max_files_per_sync": settings.GOOGLE_DRIVE_MAX_FILES
        },
        "web_content": {
            "enabled": settings.WEB_CONTENT_ENABLED,
            "last_sync": last_sync,
            "sync_interval": f"{settings.WEB_CONTENT_SYNC_INTERVAL}s"
        },
        "firecrawl": {
            "enabled": settings.FIRECRAWL_ENABLED,
            "available": "yes" if 'FIRECRAWL_AVAILABLE' in globals() and FIRECRAWL_AVAILABLE else "no",
            **firecrawl_info
        },
        "notion": {
            "enabled": settings.NOTION_ENABLED,
            "api_key_configured": bool(settings.NOTION_API_KEY),
            **notion_info
        },
        "mcp_slack_bot": {
            "enabled": os.getenv("SLACK_APP_TOKEN") is not None,
            "mcp_available": MCP_AVAILABLE,
            "app_token_configured": os.getenv("SLACK_APP_TOKEN") is not None,
            "bot_token_configured": os.getenv("SLACK_BOT_TOKEN") is not None
        }
    }
    
    return status_info

def get_document_processor():
    """Dependency to get the document processor."""
    global document_processor
    return document_processor

def get_gdrive_mcp():
    """Dependency to get the Google Drive MCP instance."""
    global gdrive_mcp
    return gdrive_mcp

def get_gdrive_manager():
    """Dependency to get the Google Drive Manager instance."""
    global gdrive_manager
    return gdrive_manager

def get_web_content_manager():
    """Dependency to get the Web Content Manager instance."""
    global web_content_manager
    return web_content_manager

def get_web_content_sync_service():
    """Dependency to get the Web Content Sync Service instance."""
    global web_content_sync_service
    return web_content_sync_service

def get_firecrawl_manager():
    """Dependency to get the Firecrawl Manager instance."""
    global firecrawl_manager
    return firecrawl_manager

def get_notion_manager():
    """Dependency to get the Notion Manager instance."""
    global notion_manager
    return notion_manager

def get_mcp_slack_client():
    """Dependency to get the MCP Slack client."""
    global mcp_slack_client
    return mcp_slack_client

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred"}
    )

@app.on_event("startup")
async def startup_event():
    """Initialize components on application startup."""
    global vector_db, document_processor, gdrive_manager, gdrive_mcp, firecrawl_manager, notion_manager, mcp_slack_client
    
    logger.info("Initializing database...")
    init_db()
    
    # Create test data if in development mode
    if settings.ENVIRONMENT.lower() == "development":
        create_test_data()
    
    # Initialize vector database
    logger.info("Initializing vector database...")
    vector_db = VectorDB(collection_name="documents")
    
    # Initialize document processor
    document_processor = DocumentProcessor(vector_db=vector_db)
    
    # Initialize new Google Drive integration
    if settings.GOOGLE_DRIVE_ENABLED and settings.GOOGLE_CREDENTIALS_PATH and settings.GOOGLE_TOKEN_PATH:
        logger.info("Initializing Google Drive integration...")
        
        try:
            from services.knowledge.datasources.gdrive import GoogleDriveManager
            
            gdrive_manager = GoogleDriveManager(
                document_processor=document_processor,
                vector_db=vector_db,
                credentials_path=settings.GOOGLE_CREDENTIALS_PATH,
                token_path=settings.GOOGLE_TOKEN_PATH,
                sync_file=settings.GOOGLE_DRIVE_SYNC_FILE
            )
            
            logger.info("Google Drive integration initialized successfully")
            
            # Trigger an initial sync in the background
            async def initial_sync():
                try:
                    await gdrive_manager.sync_recent_files(max_files=settings.GOOGLE_DRIVE_MAX_FILES)
                except Exception as e:
                    logger.error(f"Error during initial Google Drive sync: {e}")
            
            asyncio.create_task(initial_sync())
            logger.info(f"Started initial Google Drive sync (max files: {settings.GOOGLE_DRIVE_MAX_FILES})")
            
        except Exception as e:
            logger.error(f"Error initializing Google Drive integration: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            gdrive_manager = None
    else:
        logger.info("Google Drive integration disabled or credentials not configured")
        gdrive_manager = None
    
    # Initialize legacy Google Drive integration (MCP)
    gdrive_enabled = False
    gdrive_mcp = None
    
    # Legacy MCP Google Drive functionality commented out for now
    """
    if settings.MCP_GDRIVE_ENABLED and settings.MCP_CONFIG_PATH:
        logger.info("Initializing MCP Google Drive integration...")
        try:
            # Import and initialize the MCP Google Drive integration
            from services.knowledge.datasources.mcp_gdrive import MCPGoogleDrive, create_mcp_gdrive
            
            # Verify that the MCP config file exists
            if not os.path.exists(settings.MCP_CONFIG_PATH):
                logger.error(f"MCP config file not found: {settings.MCP_CONFIG_PATH}")
                logger.info("Please run the install_mcp_gdrive.sh script to set up the MCP Google Drive integration")
                gdrive_mcp = None
            else:
                # Create and initialize the MCP Google Drive client
                # We'll start the server in a background task to avoid blocking startup
                gdrive_mcp = MCPGoogleDrive(mcp_config_path=settings.MCP_CONFIG_PATH)
                
                try:
                    # Start the MCP server in a background task
                    server_task = asyncio.create_task(gdrive_mcp.start_server())
                    logger.info("MCP Google Drive integration initialized. Server starting in background...")
                    
                    # We're not awaiting the task, but we can add a callback to log when it's done
                    def server_started_callback(task):
                        try:
                            result = task.result()
                            if result:
                                logger.info("MCP Google Drive server started successfully")
                            else:
                                logger.error("Failed to start MCP Google Drive server")
                        except Exception as e:
                            logger.error(f"Error in MCP Google Drive server startup: {e}")
                    
                    server_task.add_done_callback(server_started_callback)
                    gdrive_enabled = True
                    
                except Exception as server_error:
                    logger.error(f"Error starting MCP Google Drive server: {server_error}")
                    gdrive_mcp = None
                
        except Exception as e:
            logger.error(f"Error initializing MCP Google Drive integration: {e}")
            # Log the full traceback for better debugging
            try:
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            except:
                logger.error("Could not log traceback")
            gdrive_mcp = None
            
    # Legacy direct Google Drive integration
    elif settings.GOOGLE_CREDENTIALS_PATH and settings.GOOGLE_TOKEN_PATH and not settings.GOOGLE_DRIVE_ENABLED:
        logger.info("Legacy Google Drive integration is now deprecated. Please use the new integration by setting GOOGLE_DRIVE_ENABLED=true.")
        gdrive_mcp = None
    """
    
    # Initialize Web Content Manager for web fetching
    logger.info("Initializing Web Content integration...")
    try:
        # Import and initialize the Web Content Manager and MCP Web Fetch
        from services.knowledge.datasources.web_content import WebContentManager
        from services.mcp.web_fetch import MCPWebFetch
        
        # Initialize the web fetch integration
        web_fetch = MCPWebFetch()
        web_content_manager = WebContentManager(
            document_processor=document_processor,
            web_fetch=web_fetch
        )
        
        # Start the web fetch server in a background task
        web_server_task = asyncio.create_task(web_fetch.start_server())
        
        # Add callback to log when it's done
        def web_server_started_callback(task):
            try:
                result = task.result()
                if result:
                    logger.info("MCP Web Fetch server started successfully")
                else:
                    logger.error("Failed to start MCP Web Fetch server")
            except Exception as e:
                logger.error(f"Error in MCP Web Fetch server startup: {e}")
        
        web_server_task.add_done_callback(web_server_started_callback)
        logger.info("Web Content integration initialized. Server starting in background...")
    
    except Exception as e:
        logger.error(f"Error initializing Web Content integration: {e}")
        # Log the full traceback for better debugging
        logger.error(f"Traceback: {traceback.format_exc()}")
        web_content_manager = None

    # Initialize Web Content Sync Service if enabled
    if settings.WEB_CONTENT_ENABLED:
        try:
            import traceback
            # Import and initialize the Web Content Sync Service
            from services.knowledge.web_content_sync import WebContentSyncService
            from services.mcp.web_fetch import MCPWebFetch
            
            # Create and initialize the Web Content Sync Service
            web_fetch = MCPWebFetch()
            web_content_sync_service = WebContentSyncService(
                document_processor=document_processor,
                web_fetch=web_fetch
            )
            
            # Start the scheduled sync in a background task
            sync_task = asyncio.create_task(web_content_sync_service.start_scheduled_sync())
            
            # Also trigger an initial sync
            initial_sync_task = asyncio.create_task(web_content_sync_service.manual_sync())
            
            logger.info(f"Web Content sync service initialized with interval: {settings.WEB_CONTENT_SYNC_INTERVAL}s")
            logger.info(f"Using URLs file: {settings.WEB_CONTENT_URLS_FILE}")
            
        except Exception as e:
            logger.error(f"Error initializing Web Content sync service: {e}")
            try:
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            except:
                logger.error("Could not log traceback")
            web_content_sync_service = None
    else:
        logger.info("Web Content sync service disabled")
        web_content_sync_service = None
    
    # Initialize Firecrawl if enabled
    if settings.FIRECRAWL_ENABLED:
        try:
            # Check if Firecrawl is available
            try:
                from firecrawl import Crawler
                FIRECRAWL_AVAILABLE = True
            except ImportError:
                logger.warning("Firecrawl package not installed. Install with 'pip install firecrawl'")
                FIRECRAWL_AVAILABLE = False
            
            if FIRECRAWL_AVAILABLE:
                # Initialize Firecrawl Manager
                from services.knowledge.datasources.firecrawl_manager import FirecrawlManager
                
                logger.info("Initializing Firecrawl integration...")
                firecrawl_manager = FirecrawlManager(
                    config_path=settings.FIRECRAWL_CONFIG_PATH,
                    document_processor=document_processor,
                    vector_db=vector_db
                )
                
                # Start the crawl service in a background task
                crawl_task = asyncio.create_task(firecrawl_manager.start_crawl_service())
                
                # Add callback to log when it's done
                def crawl_service_started_callback(task):
                    try:
                        result = task.result()
                        if result:
                            logger.info("Firecrawl service started successfully")
                        else:
                            logger.error("Failed to start Firecrawl service")
                    except Exception as e:
                        logger.error(f"Error in Firecrawl service startup: {e}")
                
                crawl_task.add_done_callback(crawl_service_started_callback)
                logger.info(f"Firecrawl integration initialized with config: {settings.FIRECRAWL_CONFIG_PATH}")
            else:
                logger.warning("Firecrawl integration disabled due to missing dependencies")
                firecrawl_manager = None
                
        except Exception as e:
            logger.error(f"Error initializing Firecrawl integration: {e}")
            # Log the full traceback for better debugging
            try:
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            except:
                logger.error("Could not log traceback")
            firecrawl_manager = None
    else:
        logger.info("Firecrawl integration disabled")
        firecrawl_manager = None
    
    # Initialize Notion integration if enabled
    if settings.NOTION_ENABLED:
        try:
            # Initialize Notion Manager
            from services.knowledge.datasources.notion_manager import NotionManager
            
            logger.info("Initializing Notion integration...")
            notion_manager = NotionManager(
                document_processor=document_processor,
                vector_db=vector_db
            )
            
            # Check if API key is configured
            if not settings.NOTION_API_KEY:
                logger.warning("Notion API key not configured. Notion integration will not function properly.")
            elif not settings.NOTION_PAGES:
                logger.warning("No Notion pages configured. Add page IDs to NOTION_PAGES environment variable.")
            else:
                logger.info(f"Notion integration initialized with {len(notion_manager.configured_pages)} configured pages")
                
        except Exception as e:
            logger.error(f"Error initializing Notion integration: {e}")
            # Log the full traceback for better debugging
            logger.error(f"Traceback: {traceback.format_exc()}")
            notion_manager = None
    else:
        logger.info("Notion integration disabled")
        notion_manager = None
    
    # Initialize MCP Slack client and Socket Mode
    try:
        # Check if MCP is available
        try:
            import mcp
            MCP_AVAILABLE = True
        except ImportError:
            logger.warning("MCP library not installed. Install with 'pip install mcp' to use the MCP Slack bot")
            MCP_AVAILABLE = False
        
        # Check if Socket Mode is enabled (requires SLACK_APP_TOKEN)
        SOCKET_MODE_ENABLED = os.getenv("SLACK_APP_TOKEN") is not None
        
        if MCP_AVAILABLE and SOCKET_MODE_ENABLED:
            logger.info("Initializing MCP Slack client...")
            
            # Start the MCP Slack client in a background task
            async def init_mcp_slack():
                try:
                    global mcp_slack_client
                    mcp_slack_client = await initialize_mcp_client(
                        document_processor=document_processor,
                        gdrive_manager=gdrive_manager,
                        web_content_manager=web_content_manager
                    )
                    
                    if mcp_slack_client:
                        logger.info("MCP Slack client initialized successfully")
                        
                        # Start Socket Mode in the background
                        socket_mode_started = await start_socket_mode()
                        if socket_mode_started:
                            logger.info("Socket Mode started successfully")
                        else:
                            logger.error("Failed to start Socket Mode")
                    else:
                        logger.error("Failed to initialize MCP Slack client")
                        
                except Exception as e:
                    logger.error(f"Error initializing MCP Slack client: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Start the initialization in a background task
            asyncio.create_task(init_mcp_slack())
        else:
            if not MCP_AVAILABLE:
                logger.info("MCP Slack bot disabled due to missing MCP library")
            if not SOCKET_MODE_ENABLED:
                logger.info("Socket Mode disabled due to missing SLACK_APP_TOKEN environment variable")
    except Exception as e:
        logger.error(f"Error setting up MCP Slack integration: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Include knowledge routes after document_processor is initialized
    from api.knowledge_routes import router as knowledge_router
    app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
    
    logger.info("Application initialization complete")

if __name__ == "__main__":
    logger.info(f"Starting AI Center Bot on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "main:app", 
        host=settings.API_HOST, 
        port=settings.API_PORT, 
        reload=True
    )