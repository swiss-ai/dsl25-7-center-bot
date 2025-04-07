"""
MCP Google Drive integration using the official MCP Google Drive server.
"""
import os
import json
import logging
import asyncio
import subprocess
import requests
import time
import socket
from typing import Dict, List, Any, Optional, Tuple
import shutil
import psutil
import platform

logger = logging.getLogger(__name__)

# Add a placeholder class to fix import errors
class MCPGDriveManager:
    """
    MCP Google Drive content management for the vector database.
    This is a placeholder to fix import errors.
    """
    
    def __init__(self, document_processor=None, vector_db=None):
        self.document_processor = document_processor
        self.vector_db = vector_db
        
    async def sync_all_documents(self):
        """Placeholder for syncing all Google Drive documents"""
        logger.warning("MCPGDriveManager.sync_all_documents: This is a placeholder method")
        return {"status": "not_implemented"}

class MCPGoogleDrive:
    """Integration with MCP Google Drive server."""
    
    def __init__(self, mcp_config_path: str = None):
        """
        Initialize the MCP Google Drive client.
        
        Args:
            mcp_config_path: Path to the MCP config file
        """
        self.mcp_config_path = mcp_config_path or os.getenv('MCP_CONFIG_PATH')
        self.server_process = None
        self.base_url = "http://localhost:3000"  # Default MCP server URL
        self.server_startup_lock = asyncio.Lock()
        
    async def start_server(self):
        """
        Start the MCP Google Drive server.
        
        Returns:
            bool: True if server started successfully, False otherwise
        """
        # Use a lock to prevent multiple concurrent startup attempts
        async with self.server_startup_lock:
            # Check if server is already running
            if await self._is_server_running():
                logger.info("MCP Google Drive server is already running")
                return True
            
            # Check if npx is available
            if not shutil.which("npx"):
                logger.error("npx command not found. Make sure Node.js is installed.")
                self._log_system_info()
                return False
                
            try:
                # Check if port 3000 is in use
                if self._is_port_in_use(3000):
                    logger.warning("Port 3000 is already in use")
                    
                    # Try to identify the process using port 3000
                    process_info = self._get_process_using_port(3000)
                    if process_info:
                        logger.info(f"Port 3000 is used by: {process_info}")
                    
                    # If it's a node process, it might be our server already running
                    if process_info and "node" in process_info.lower():
                        logger.info("It looks like the MCP server might already be running")
                        
                        # Test if it's actually the MCP server
                        try:
                            response = requests.get(f"{self.base_url}/info", timeout=2)
                            if response.status_code == 200:
                                logger.info("Confirmed MCP server is already running")
                                return True
                        except Exception as e:
                            logger.warning(f"Port 3000 is in use but doesn't seem to be our MCP server: {e}")
                    
                    # We need to kill the process or use a different port
                    logger.warning("Please terminate the process using port 3000 and try again")
                    return False
                
                # Read the MCP config file
                if not os.path.exists(self.mcp_config_path):
                    logger.error(f"MCP config file not found: {self.mcp_config_path}")
                    return False
                    
                with open(self.mcp_config_path, 'r') as f:
                    config = json.load(f)
                
                # Get the command and args for the Google Drive server
                gdrive_config = config.get('mcpServers', {}).get('gdrive', {})
                command = gdrive_config.get('command')
                args = gdrive_config.get('args', [])
                
                if not command:
                    logger.error("Google Drive MCP server command not found in config")
                    return False
                
                # Start the server process
                direct_cmd = ["npx", "-y", "@modelcontextprotocol/server-gdrive"]
                logger.info(f"Starting MCP Google Drive server: {' '.join(direct_cmd)}")
                
                # Try using the direct command first
                try:
                    # Use shell=False for security and better process management
                    self.server_process = subprocess.Popen(
                        direct_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=False,
                        preexec_fn=None if platform.system() == 'Windows' else os.setsid
                    )
                    logger.info(f"Server process started with PID: {self.server_process.pid}")
                except Exception as start_error:
                    logger.error(f"Error starting server with direct command: {start_error}")
                    
                    # Fall back to config command
                    cmd = [command] + args
                    logger.info(f"Falling back to config command: {' '.join(cmd)}")
                    try:
                        self.server_process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=False,
                            preexec_fn=None if platform.system() == 'Windows' else os.setsid
                        )
                        logger.info(f"Server process started with PID: {self.server_process.pid}")
                    except Exception as fallback_error:
                        logger.error(f"Error starting server with fallback command: {fallback_error}")
                        return False
                
                # Wait for the server to start
                max_retries = 10
                retry_delay = 2  # seconds
                
                for i in range(max_retries):
                    logger.info(f"Waiting for server to start (attempt {i+1}/{max_retries})...")
                    
                    # Check if process is still running
                    if self.server_process.poll() is not None:
                        returncode = self.server_process.poll()
                        logger.error(f"Server process exited early with code: {returncode}")
                        
                        # Try to read any output
                        stdout, stderr = "", ""
                        try:
                            stdout, stderr = self.server_process.communicate(timeout=1)
                        except Exception:
                            pass
                        
                        if stdout:
                            logger.error(f"Server stdout: {stdout.decode() if isinstance(stdout, bytes) else stdout}")
                        if stderr:
                            logger.error(f"Server stderr: {stderr.decode() if isinstance(stderr, bytes) else stderr}")
                        
                        return False
                    
                    # Wait a bit before checking
                    await asyncio.sleep(retry_delay)
                    
                    # Test if server is responsive
                    try:
                        response = requests.get(f"{self.base_url}/info", timeout=2)
                        if response.status_code == 200:
                            logger.info("MCP Google Drive server started successfully")
                            # Start a background task to monitor the server
                            asyncio.create_task(self._monitor_server())
                            return True
                        else:
                            logger.warning(f"MCP Google Drive server returned status code: {response.status_code}")
                    except (requests.RequestException, ConnectionError) as e:
                        logger.debug(f"Server not ready yet (attempt {i+1}): {e}")
                
                # After all retries, log the server output for debugging
                if self.server_process:
                    try:
                        # Check if it's still running
                        if self.server_process.poll() is None:
                            # Send a signal to terminate (don't kill yet)
                            if platform.system() == "Windows":
                                # Windows - use taskkill
                                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.server_process.pid)], 
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            else:
                                # Unix/Linux - use SIGTERM
                                import signal
                                os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                            
                            # Give it a moment to terminate gracefully
                            await asyncio.sleep(1)
                        
                        # Read any output
                        stdout, stderr = self.server_process.communicate(timeout=2)
                        if stdout:
                            logger.error(f"Server stdout: {stdout.decode() if isinstance(stdout, bytes) else stdout}")
                        if stderr:
                            logger.error(f"Server stderr: {stderr.decode() if isinstance(stderr, bytes) else stderr}")
                    except Exception as e:
                        logger.error(f"Error when trying to read server output: {e}")
                
                logger.error("Failed to start MCP Google Drive server after multiple attempts")
                return False
                    
            except Exception as e:
                logger.error(f"Error starting MCP Google Drive server: {e}")
                return False
    
    async def _monitor_server(self):
        """Background task to monitor the server and restart if needed."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            if not self.server_process or self.server_process.poll() is not None:
                logger.warning("MCP server is not running. Attempting to restart...")
                await self.start_server()
    
    async def _is_server_running(self) -> bool:
        """Check if the MCP server is running and responsive."""
        try:
            response = requests.get(f"{self.base_url}/info", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def _get_process_using_port(self, port: int) -> str:
        """Get information about the process using a port."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    connections = proc.connections(kind='inet')
                    for conn in connections:
                        if conn.laddr.port == port:
                            cmd = " ".join(proc.cmdline()) if proc.cmdline() else proc.name()
                            return f"PID {proc.pid}: {cmd}"
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            logger.error(f"Error getting process for port {port}: {e}")
        return ""
    
    def _log_system_info(self):
        """Log system information for debugging."""
        try:
            logger.info(f"System: {platform.system()} {platform.release()}")
            logger.info(f"Python: {platform.python_version()}")
            
            # Check Node.js and NPM
            try:
                node_version = subprocess.run(["node", "--version"], capture_output=True, text=True)
                npm_version = subprocess.run(["npm", "--version"], capture_output=True, text=True)
                logger.info(f"Node.js: {node_version.stdout.strip()}")
                logger.info(f"NPM: {npm_version.stdout.strip()}")
            except:
                logger.info("Could not determine Node.js and NPM versions")
            
            # Get path info
            logger.info(f"PATH: {os.environ.get('PATH', 'Not available')}")
            
            # Check npx specifically
            npx_path = shutil.which("npx")
            logger.info(f"npx path: {npx_path or 'Not found'}")
            
            # Check for MCP package
            try:
                npm_list = subprocess.run(["npm", "list", "-g", "@modelcontextprotocol/server-gdrive"], 
                                          capture_output=True, text=True)
                logger.info(f"MCP package (global): {npm_list.stdout}")
                
                npm_list_local = subprocess.run(["npm", "list", "@modelcontextprotocol/server-gdrive"], 
                                                capture_output=True, text=True)
                logger.info(f"MCP package (local): {npm_list_local.stdout}")
            except:
                logger.info("Could not check for MCP package installation")
            
        except Exception as e:
            logger.error(f"Error logging system info: {e}")
    
    def stop_server(self):
        """Stop the MCP Google Drive server."""
        if self.server_process:
            logger.info(f"Stopping MCP Google Drive server (PID: {self.server_process.pid})")
            
            try:
                # Graceful termination first
                if platform.system() == "Windows":
                    # Windows - use taskkill
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.server_process.pid)], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    # Unix/Linux - use SIGTERM for graceful termination
                    import signal
                    os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                
                # Wait a bit for the process to terminate
                for _ in range(5):
                    if self.server_process.poll() is not None:
                        break
                    time.sleep(0.5)
                
                # If still running, force kill
                if self.server_process.poll() is None:
                    logger.warning("Server did not terminate gracefully, forcing termination")
                    self.server_process.kill()
                
                self.server_process = None
                logger.info("MCP Google Drive server stopped")
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
    
    async def search_files(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of file metadata
        """
        logger.info(f"Searching Google Drive via MCP for: '{query}'")
        
        # Check if server is running
        if not await self._is_server_running():
            logger.warning("MCP Google Drive server is not running")
            # Try to start it
            logger.info("Attempting to start the server...")
            server_started = await self.start_server()
            if not server_started:
                logger.error("Failed to start MCP Google Drive server")
                return await self._fallback_search(query, max_results)
        
        try:
            # Log the URL we're trying to connect to
            search_url = f"{self.base_url}/v1/tools/search"
            logger.info(f"Making request to MCP server: POST {search_url}")
            
            # Add timeout to prevent hanging
            response = requests.post(
                search_url,
                json={"query": query},
                timeout=10
            )
            
            # Log the response status
            logger.info(f"MCP server response status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error searching files: {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return await self._fallback_search(query, max_results)
            
            # Parse the response
            result = response.json()
            logger.info(f"Response JSON: {json.dumps(result)[:200]}...")  # Log first 200 chars
            
            files = result.get('files', [])
            
            # Limit results if needed
            if max_results and len(files) > max_results:
                files = files[:max_results]
                
            # Log what was found
            if files:
                logger.info(f"Found {len(files)} files in Google Drive matching '{query}'")
                for i, file in enumerate(files):
                    logger.info(f"  {i+1}. {file.get('name', 'Untitled')} ({file.get('mimeType', 'Unknown type')})")
            else:
                logger.info(f"No files found in Google Drive matching '{query}'")
                
            return files
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            
            # If the server crashed, log that
            if self.server_process and self.server_process.poll() is not None:
                returncode = self.server_process.poll()
                logger.error(f"MCP server process exited with code: {returncode}")
                
                # Try to read any output
                stdout, stderr = "", ""
                try:
                    stdout, stderr = self.server_process.communicate(timeout=1)
                except Exception:
                    pass
                
                if stdout:
                    logger.error(f"Server stdout: {stdout.decode() if isinstance(stdout, bytes) else stdout}")
                if stderr:
                    logger.error(f"Server stderr: {stderr.decode() if isinstance(stderr, bytes) else stderr}")
            
            # Try fallback search method
            return await self._fallback_search(query, max_results)
    
    async def _fallback_search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Fallback search method using direct command line invocation."""
        logger.info("Attempting fallback search using direct MCP command...")
        try:
            # Run the search command directly with NPX
            result = subprocess.run(
                ["npx", "-y", "@modelcontextprotocol/server-gdrive", "search", query],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                logger.info("Fallback search successful")
                logger.info(f"Fallback search output: {result.stdout[:200]}...")  # Log first 200 chars
                
                # Try to parse JSON output
                try:
                    output_lines = result.stdout.strip().split('\n')
                    json_line = next((l for l in output_lines if l.startswith('{')), None)
                    if json_line:
                        files_data = json.loads(json_line)
                        files = files_data.get('files', [])
                        
                        if files:
                            logger.info(f"Found {len(files)} files via fallback method")
                            return files[:max_results] if max_results else files
                except Exception as parse_err:
                    logger.error(f"Error parsing fallback search result: {parse_err}")
            else:
                logger.error(f"Fallback search failed: {result.stderr}")
        except Exception as fallback_err:
            logger.error(f"Error during fallback search: {fallback_err}")
        
        # If all else fails, return empty list
        return []
    
    async def get_file_content(self, file_id: str) -> Tuple[str, Dict[str, Any]]:
        """
        Get the content of a file from Google Drive.
        
        Args:
            file_id: The ID of the file
            
        Returns:
            Tuple of (content, metadata)
        """
        # Check if server is running
        if not await self._is_server_running():
            logger.warning("MCP Google Drive server is not running when getting file content")
            # Try to start it
            server_started = await self.start_server()
            if not server_started:
                logger.error("Failed to start MCP Google Drive server for file content")
                return "", {}
        
        try:
            # Make request to MCP server to get file metadata
            metadata_url = f"{self.base_url}/v1/resources/gdrive:///{file_id}"
            logger.info(f"Getting file metadata from: GET {metadata_url}")
            
            metadata_response = requests.get(
                metadata_url,
                timeout=10
            )
            
            if metadata_response.status_code != 200:
                logger.error(f"Error getting file metadata: {metadata_response.status_code}")
                logger.error(f"Response content: {metadata_response.text}")
                return "", {}
            
            metadata = metadata_response.json()
            logger.info(f"Got metadata for file: {metadata.get('name', 'Unknown')}")
            
            # Check if it's a PDF file - MCP server will convert to markdown
            if metadata.get('mimeType') == 'application/pdf':
                logger.info("PDF file detected - MCP server will convert to markdown")
            
            # Make request to MCP server to get file content
            content_url = f"{self.base_url}/v1/resources/gdrive:///{file_id}/content"
            logger.info(f"Getting file content from: GET {content_url}")
            
            content_response = requests.get(
                content_url,
                timeout=30  # Longer timeout for content, especially for PDF conversion
            )
            
            if content_response.status_code != 200:
                logger.error(f"Error getting file content: {content_response.status_code}")
                logger.error(f"Response content: {content_response.text}")
                return "", metadata
            
            content = content_response.text
            logger.info(f"Retrieved file content ({len(content)} characters)")
            
            # For PDFs, check if we got proper markdown conversion
            if metadata.get('mimeType') == 'application/pdf' and len(content) > 0:
                logger.info("PDF conversion successful")
            
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return "", {}
    
    async def list_files(
        self, 
        query: str = None, 
        page_size: int = 10, 
        order_by: str = "modifiedTime desc"
    ) -> List[Dict[str, Any]]:
        """
        List files in Google Drive.
        
        Args:
            query: Search query (Google Drive Query Language)
            page_size: Number of files to return
            order_by: Sort order
            
        Returns:
            List of file metadata
        """
        # For MCP integration, we'll just use the search endpoint
        return await self.search_files(query or "", page_size)
    
    async def sync_recent_files(self, query: str = None, max_files: int = 20) -> int:
        """
        Sync recent files from Google Drive to the knowledge base.
        
        Args:
            query: Optional query to filter files
            max_files: Maximum number of files to sync
            
        Returns:
            Number of files synced
        """
        # This method would be implemented if you need to sync files to your knowledge base
        logger.info(f"Sync requested with query '{query}' and max_files {max_files}")
        logger.warning("File sync not implemented for MCP Google Drive integration")
        return 0

# Add a function to easily create an instance
async def create_mcp_gdrive(mcp_config_path: str = None) -> MCPGoogleDrive:
    """
    Factory function to create and initialize an MCPGoogleDrive instance.
    
    Args:
        mcp_config_path: Path to the MCP config file
        
    Returns:
        Initialized MCPGoogleDrive instance
    """
    gdrive = MCPGoogleDrive(mcp_config_path=mcp_config_path)
    await gdrive.start_server()
    return gdrive