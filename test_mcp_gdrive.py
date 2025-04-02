#!/usr/bin/env python3
"""
Test script for the MCP Google Drive integration.
This script will start the MCP server, search for files, and retrieve file content.
"""

import os
import sys
import json
import asyncio
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add the src directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

async def test_mcp_gdrive():
    """Test the MCP Google Drive integration."""
    # Load environment variables
    load_dotenv()
    
    # Check if MCP_CONFIG_PATH is set
    mcp_config_path = os.getenv("MCP_CONFIG_PATH")
    if not mcp_config_path:
        logger.error("MCP_CONFIG_PATH environment variable not set")
        logger.info("Please run the install_mcp_gdrive.sh script or set the variable manually")
        return False
    
    # Check if the config file exists
    if not os.path.exists(mcp_config_path):
        logger.error(f"MCP config file not found: {mcp_config_path}")
        logger.info("Please run the install_mcp_gdrive.sh script to create the config file")
        return False
    
    logger.info(f"Using MCP config file: {mcp_config_path}")
    
    try:
        # Import the MCPGoogleDrive class
        from src.services.knowledge.datasources.mcp_gdrive import MCPGoogleDrive
        
        # Create an instance of MCPGoogleDrive
        logger.info("Creating MCPGoogleDrive instance...")
        gdrive = MCPGoogleDrive(mcp_config_path=mcp_config_path)
        
        # Start the MCP server
        logger.info("Starting MCP server...")
        server_started = await gdrive.start_server()
        
        if not server_started:
            logger.error("Failed to start MCP server")
            return False
        
        logger.info("MCP server started successfully")
        
        # Test searching for files
        logger.info("Searching for PDF files...")
        search_query = "mimeType='application/pdf'"
        files = await gdrive.search_files(search_query, max_results=5)
        
        if not files:
            logger.warning("No PDF files found")
        else:
            logger.info(f"Found {len(files)} PDF files")
            
            # Print file details
            for i, file in enumerate(files):
                logger.info(f"File {i+1}: {file.get('name')} ({file.get('mimeType')})")
                
            # Test getting file content for the first PDF
            if files:
                pdf_file = files[0]
                logger.info(f"Getting content for PDF file: {pdf_file.get('name')}")
                
                content, metadata = await gdrive.get_file_content(pdf_file.get('id'))
                
                if content:
                    logger.info(f"Successfully retrieved content ({len(content)} characters)")
                    logger.info("First 200 characters of content:")
                    logger.info(content[:200])
                else:
                    logger.error("Failed to retrieve file content")
        
        # Stop the server
        logger.info("Stopping MCP server...")
        gdrive.stop_server()
        logger.info("Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error testing MCP Google Drive: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    asyncio.run(test_mcp_gdrive())