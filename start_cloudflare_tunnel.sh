#!/bin/bash

# Script to create a Cloudflare tunnel to expose the local server
# This uses cloudflared, Cloudflare's tunnel client

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared not found. Installing..."
    
    # Check OS and install appropriately
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install cloudflared
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        # Check for package manager and install
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu
            curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
            sudo dpkg -i cloudflared.deb
            rm cloudflared.deb
        elif command -v dnf &> /dev/null; then
            # Fedora/RHEL
            sudo dnf install -y https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-x86_64.rpm
        else
            echo "Unsupported Linux distribution. Please install cloudflared manually."
            exit 1
        fi
    else
        echo "Unsupported OS. Please install cloudflared manually."
        exit 1
    fi
fi

# Default port is 8000
PORT=${1:-8000}

echo "Starting Cloudflare tunnel for port $PORT..."
echo "This will create a public URL that forwards to your local server."
echo "Use this URL for Slack event subscriptions."
echo ""
echo "Press Ctrl+C to stop the tunnel."
echo ""

# Start the tunnel
cloudflared tunnel --url http://localhost:$PORT

# Note: This is an ephemeral tunnel (temporary)
# For production, you should create a permanent tunnel with authentication
# See: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/