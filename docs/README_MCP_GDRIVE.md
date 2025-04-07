# MCP Google Drive Integration

This document explains how to set up and use the MCP Google Drive integration for the AI Center Bot.

## What is MCP Google Drive?

The MCP (Machine Context Protocol) Google Drive integration allows Claude to access files from your Google Drive, including **PDF files that are automatically converted to markdown**. This makes it possible to search and retrieve information from PDF documents that were previously difficult to work with.

## Prerequisites

- Node.js 14+ and npm 
- Google account with access to Google Drive
- Google Cloud Platform project with the Google Drive API enabled

## Installation

### Automatic Installation

We've created an installation script that will set up everything you need:

```bash
chmod +x ./install_mcp_gdrive.sh
./install_mcp_gdrive.sh
```

The script will:
1. Check if Node.js and npm are installed
2. Install the MCP Google Drive server
3. Create/update the MCP configuration file
4. Update your `.env` file with the necessary settings
5. Guide you through OAuth setup

### Manual Installation

If you prefer to set things up manually:

1. Install the MCP Google Drive server:
   ```bash
   npm install -g @modelcontextprotocol/server-gdrive
   ```

2. Create a `mcp_config.json` file:
   ```json
   {
     "mcpServers": {
       "gdrive": {
         "command": "npx",
         "args": [
           "-y",
           "@modelcontextprotocol/server-gdrive"
         ]
       }
     }
   }
   ```

3. Update your `.env` file:
   ```
   # MCP Google Drive Integration
   MCP_GDRIVE_ENABLED=true
   MCP_CONFIG_PATH=/absolute/path/to/mcp_config.json
   ```

4. Set up OAuth:
   ```bash
   npx @modelcontextprotocol/server-gdrive auth
   ```

## How It Works

Once set up, the integration:

1. Starts the MCP Google Drive server in the background when your application starts
2. Handles authentication with Google Drive
3. Provides search capabilities for files in your Google Drive
4. Automatically converts PDF files to markdown for better integration with Claude

## Troubleshooting

### Server Won't Start

If the server won't start:

1. Check if port 3000 is already in use (the MCP server uses this port)
2. Ensure Node.js and npm are correctly installed
3. Check the logs for specific error messages

```bash
# Check if port 3000 is in use
lsof -i :3000

# Test the MCP server directly
npx @modelcontextprotocol/server-gdrive
```

### Authentication Issues

If you're having authentication issues:

1. Run the auth command again: `npx @modelcontextprotocol/server-gdrive auth`
2. Ensure your Google Cloud Platform project has the Google Drive API enabled
3. Make sure your OAuth credentials are set up correctly (Desktop application type)

### PDF Conversion Not Working

If PDF conversion isn't working:

1. Make sure the file is a valid PDF
2. Check if the PDF is text-based (scanned PDFs may not convert properly)
3. Try accessing the file directly in Google Drive to ensure you have permission

## Advanced Configuration

### Changing the Server Port

If you need to change the port:

```bash
# Set environment variable before starting your app
export MCP_GDRIVE_PORT=3001
```

Then update the MCPGoogleDrive class to use this port instead of the default 3000.

### Custom OAuth Scopes

If you need additional OAuth scopes, you can authorize with specific scopes:

```bash
npx @modelcontextprotocol/server-gdrive auth --scopes drive.readonly,drive.metadata.readonly
```

## Security Considerations

- The MCP Google Drive integration runs locally and does not expose your files to external servers
- OAuth tokens are stored securely on your local machine
- The server only has access to files that you have permission to access
- The server is only accessible from localhost

## For Developers

If you're developing or modifying the integration:

1. The main integration code is in `src/services/knowledge/datasources/mcp_gdrive.py`
2. MCP tools are defined in `src/services/mcp/gdrive.py`
3. Server initialization happens in `src/main.py`

## Further Reading

- [Machine Context Protocol Documentation](https://github.com/anthropics/anthropic-cookbook/tree/main/machine_context_protocol)
- [MCP Google Drive Server Repository](https://github.com/anthropics/anthropic-tools/tree/main/packages/server-gdrive)