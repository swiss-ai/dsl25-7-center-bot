#!/bin/bash
# Setup script for Google Drive MCP server

echo "Setting up Google Drive MCP server..."

# Create the server directory
mkdir -p server

# Install the MCP Google Drive server
npm install -g @modelcontextprotocol/server-gdrive

echo "Google Drive MCP server installed"
echo ""
echo "NEXT STEPS:"
echo "1. Create a Google Cloud project at https://console.cloud.google.com/projectcreate"
echo "2. Enable the Google Drive API at https://console.cloud.google.com/workspace-api/products"
echo "3. Configure an OAuth consent screen (internal is fine for testing)"
echo "4. Add OAuth scope https://www.googleapis.com/auth/drive.readonly"
echo "5. Create an OAuth Client ID for application type Desktop App"
echo "6. Download the JSON file of your client's OAuth keys"
echo "7. Rename the key file to gcp-oauth.keys.json and place it in the project root"
echo "8. Run the authentication command: npx @modelcontextprotocol/server-gdrive auth"
echo "9. Complete the authentication flow in your browser"
echo ""
echo "After completing these steps, update your .env file with:"
echo "MCP_GDRIVE_ENABLED=true"
echo ""