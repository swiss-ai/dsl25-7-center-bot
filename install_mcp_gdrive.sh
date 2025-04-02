#!/bin/bash

# Install MCP Google Drive Integration Script

set -e

# Colors for output
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
NC="\033[0m" # No Color

# Print header
echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}   MCP Google Drive Integration Setup Script     ${NC}"
echo -e "${GREEN}==================================================${NC}"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is not installed!${NC}"
    echo -e "Please install Node.js from https://nodejs.org/\n"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
if [ "$NODE_VERSION" -lt 14 ]; then
    echo -e "${RED}Node.js version is too old. Please upgrade to Node.js 14 or higher.${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Node.js is installed ($(node -v))"

# Check if NPM is installed
if ! command -v npm &> /dev/null; then
    echo -e "${RED}NPM is not installed!${NC}"
    echo -e "Please install NPM (it usually comes with Node.js)\n"
    exit 1
fi

echo -e "${GREEN}✓${NC} NPM is installed ($(npm -v))"

# Create .env file if it doesn't exist
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    touch "$ENV_FILE"
fi

# Update .env file with MCP settings
echo -e "${YELLOW}Updating .env file with MCP Google Drive settings...${NC}"

# Check if the environment variables already exist
if grep -q "MCP_GDRIVE_ENABLED" "$ENV_FILE"; then
    echo -e "${YELLOW}MCP settings already exist in .env, updating...${NC}"
    # Comment out legacy Google Drive settings
    sed -i.bak 's/^GOOGLE_CREDENTIALS_PATH=/#GOOGLE_CREDENTIALS_PATH=/g' "$ENV_FILE"
    sed -i.bak 's/^GOOGLE_TOKEN_PATH=/#GOOGLE_TOKEN_PATH=/g' "$ENV_FILE"
    # Update MCP settings
    sed -i.bak 's/^MCP_GDRIVE_ENABLED=.*/MCP_GDRIVE_ENABLED=true/g' "$ENV_FILE"
    sed -i.bak "s|^MCP_CONFIG_PATH=.*|MCP_CONFIG_PATH=$(pwd)/mcp_config.json|g" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    # Comment out existing Google Drive settings
    if grep -q "GOOGLE_CREDENTIALS_PATH" "$ENV_FILE"; then
        sed -i.bak 's/^GOOGLE_CREDENTIALS_PATH=/#GOOGLE_CREDENTIALS_PATH=/g' "$ENV_FILE"
        sed -i.bak 's/^GOOGLE_TOKEN_PATH=/#GOOGLE_TOKEN_PATH=/g' "$ENV_FILE"
        rm -f "$ENV_FILE.bak"
    fi
    
    # Add MCP settings
    cat >> "$ENV_FILE" << EOL

# MCP Google Drive Integration
MCP_GDRIVE_ENABLED=true
MCP_CONFIG_PATH=$(pwd)/mcp_config.json
EOL
fi

echo -e "${GREEN}✓${NC} .env file updated with MCP settings"

# Create MCP config file if it doesn't exist
MCP_CONFIG="mcp_config.json"
if [ ! -f "$MCP_CONFIG" ]; then
    echo -e "${YELLOW}Creating MCP config file...${NC}"
    cat > "$MCP_CONFIG" << EOL
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
EOL
    echo -e "${GREEN}✓${NC} MCP config file created"
fi

# Install MCP Google Drive server
echo -e "${YELLOW}Installing MCP Google Drive server...${NC}"
NPM_PATH=$(which npm)
echo -e "Using npm from: $NPM_PATH"

# Try to install MCP server globally first
echo -e "Installing @modelcontextprotocol/server-gdrive globally..."
npm install -g @modelcontextprotocol/server-gdrive

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Global installation failed, trying local installation...${NC}"
    # Create package.json if it doesn't exist
    if [ ! -f "package.json" ]; then
        npm init -y
    fi
    
    # Install locally
    npm install @modelcontextprotocol/server-gdrive
fi

echo -e "${GREEN}✓${NC} MCP Google Drive server installed"

# Test MCP server
echo -e "${YELLOW}Testing MCP Google Drive server...${NC}"

NPX_PATH=$(which npx)
echo -e "Using npx from: $NPX_PATH"

echo -e "Starting server with: npx @modelcontextprotocol/server-gdrive --help"
$NPX_PATH @modelcontextprotocol/server-gdrive --help > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} MCP Google Drive server is working properly"
else
    echo -e "${RED}Error testing MCP Google Drive server${NC}"
    echo -e "Let's try running it directly to see the error:"
    $NPX_PATH @modelcontextprotocol/server-gdrive --help
    exit 1
fi

# Setup OAuth authentication
echo -e "\n${YELLOW}==== Google Drive OAuth Setup ====${NC}"

echo -e "To use the Google Drive MCP server, you need to set up OAuth authentication."
echo -e "Follow these steps:"
echo -e "  1. Go to https://console.cloud.google.com/"
echo -e "  2. Create a new project or select an existing one"
echo -e "  3. Go to 'APIs & Services' > 'Credentials'"
echo -e "  4. Click 'Create Credentials' > 'OAuth client ID'"
echo -e "  5. For Application type, select 'Desktop app'"
echo -e "  6. Name your app and click 'Create'"
echo -e "  7. Download the JSON file\n"

read -p "Have you downloaded the OAuth credentials file? (y/n): " OAUTH_READY
if [[ "$OAUTH_READY" != "y" && "$OAUTH_READY" != "Y" ]]; then
    echo -e "\n${YELLOW}You'll need to complete the OAuth setup later.${NC}"
    echo -e "When ready, run: npx @modelcontextprotocol/server-gdrive auth"
else
    echo -e "\n${YELLOW}Starting OAuth authentication process...${NC}"
    $NPX_PATH @modelcontextprotocol/server-gdrive auth
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} OAuth authentication completed successfully"
    else
        echo -e "${RED}OAuth authentication failed${NC}"
        echo -e "You can try again later with: npx @modelcontextprotocol/server-gdrive auth"
    fi
fi

# Final instructions
echo -e "\n${GREEN}==================================================${NC}"
echo -e "${GREEN}       MCP Google Drive Setup Complete!       ${NC}"
echo -e "${GREEN}==================================================${NC}"

echo -e "\n${YELLOW}What's Next?${NC}"
echo -e "1. Make sure you've completed the OAuth authentication"
echo -e "2. Restart your application to use the MCP Google Drive integration"
echo -e "3. If you encounter any issues, check the logs for details\n"

echo -e "To test the server manually, run: npx @modelcontextprotocol/server-gdrive\n"

echo -e "${GREEN}Done!${NC}"
