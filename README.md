# AI Center Bot

A comprehensive Slack bot that integrates with Claude and various knowledge sources to answer questions and provide information.

## Features

- Slack integration for natural conversations
- Claude integration with MCP (Machine Controlled Protocol)
- Knowledge base with vector search
- Google Drive integration for document access
- Rate limiting and conversation history

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 16+ (for Google Drive MCP server)
- Google Cloud account (for Google Drive integration)
- Slack workspace with admin access
- Anthropic API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/aicenter-bot.git
cd aicenter-bot
```

2. Set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file using `example.env` as a template:
```bash
cp example.env .env
```

5. Update the `.env` file with your credentials:
```
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here

# Anthropic Claude API
ANTHROPIC_API_KEY=your-claude-api-key-here

# MCP Google Drive Configuration
MCP_GDRIVE_ENABLED=true
MCP_CONFIG_PATH=/path/to/mcp_config.json
```

### Google Drive Integration

For Google Drive integration using MCP:

1. Run the setup script:
```bash
./setup_gdrive_mcp.sh
```

2. Follow the on-screen instructions to set up the Google Drive API credentials.

3. Authenticate with Google Drive:
```bash
npx @modelcontextprotocol/server-gdrive auth
```

4. Complete the authentication flow in your browser.

### Running the Bot

1. Start the server:
```bash
cd src
python main.py
```

2. The server will be available at `http://localhost:8000`.

### Exposing the API with Cloudflare Tunnel

To expose your local API to the internet (for Slack webhooks):

1. Install Cloudflare Tunnel:
```bash
# macOS
brew install cloudflared

# Linux
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/
```

2. For quick development use, start a temporary tunnel:
```bash
./start_cloudflare_tunnel.sh --quick
```

3. Cloudflare will generate a temporary URL (like `https://abcd-123-xyz.trycloudflare.com`) that you can use to access your local API from the internet.

#### Setting Up a Persistent Named Tunnel (Optional)

For production, you might want to set up a persistent named tunnel:

1. Create a tunnel and get a tunnel token:
```bash
cloudflared tunnel create aicenter-bot
```

2. Edit the `cloudflared-config.yml` file and uncomment the tunnel-token line with your token:
```yaml
tunnel: aicenter-bot
credentials-file: ~/.cloudflared/cert.pem
tunnel-token: your-tunnel-token
no-autoupdate: true

ingress:
  - hostname: your-custom-domain.com  # Optional, requires DNS setup
    service: http://localhost:8000
  - service: http_status:404
```

3. Start the tunnel with the config file:
```bash
./start_cloudflare_tunnel.sh --config
```

4. (Optional) To use a custom domain, add a DNS CNAME record in your Cloudflare dashboard pointing to your tunnel.

## Usage

### Slash Commands

- `/drive search <query>` - Search for files in Google Drive
- `/drive sync [max_files]` - Sync recent files to the knowledge base
- `/aicenter search <query>` - Search the knowledge base
- `/aicenter status` - Check system status

### Direct Interaction

You can interact with the bot in two ways:
- Direct messages in Slack
- Mentioning the bot in a channel (e.g., @AICenterBot)

The bot will respond to natural language queries, search for information in the knowledge base and Google Drive, and provide helpful responses.

## License

This project is licensed under the MIT License - see the LICENSE file for details.