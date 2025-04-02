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
from services.knowledge.datasources.gdrive import GoogleDriveMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Validate environment variables
validate_settings()

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
gdrive_mcp = None

# Include routers
app.include_router(slack_router, prefix="/api/slack", tags=["slack"])

# Knowledge routes are added in the startup event after document_processor is initialized

@app.get("/")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

@app.get("/status")
async def status():
    """Return the status of various components."""
    global vector_db, gdrive_mcp
    
    # Check if MCP Google Drive server is running
    gdrive_status = "not_initialized"
    if gdrive_mcp:
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
    
    status_info = {
        "status": "operational",
        "components": {
            "database": "operational",
            "vector_db": "operational" if vector_db else "not_initialized",
            "rate_limiter": "operational" if settings.RATE_LIMIT_ENABLED else "disabled",
            "google_drive": gdrive_status,
            "google_drive_type": "mcp" if settings.MCP_GDRIVE_ENABLED else "legacy"
        },
        "document_count": vector_db.count() if vector_db else 0
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
    global vector_db, document_processor, gdrive_mcp
    
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
    
    # Initialize Google Drive integration
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
                
        except Exception as e:
            logger.error(f"Error initializing MCP Google Drive integration: {e}")
            # Log the full traceback for better debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            gdrive_mcp = None
            
    # Legacy direct Google Drive integration
    elif settings.GOOGLE_CREDENTIALS_PATH and settings.GOOGLE_TOKEN_PATH:
        logger.info("Initializing Legacy Google Drive integration...")
        try:
            gdrive_mcp = GoogleDriveMCP(
                credentials_path=settings.GOOGLE_CREDENTIALS_PATH,
                token_path=settings.GOOGLE_TOKEN_PATH,
                document_processor=document_processor
            )
            logger.info("Legacy Google Drive integration initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Legacy Google Drive integration: {e}")
            gdrive_mcp = None
    
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