# Slack Bot with Claude

A Slack bot that uses Claude to respond to messages.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure your `.env` file contains:
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_APP_TOKEN`
- `ANTHROPIC_API_KEY`
- `NOTION_API_KEY` (optional - for Notion integration)
- `NOTION_PAGES` (optional - root page ID to sync)
- `AIRTABLE_API_KEY` (optional - for Airtable integration)
- `AIRTABLE_BASE_ID` (optional - base to sync)

3. Run the bot:
```bash
python -m src.main
```

## Usage

The bot will respond to:
- Direct messages
- Mentions in channels (@bot_name)

## Slack App Configuration

Make sure your Slack app has:
- Socket Mode enabled
- Event subscriptions for:
  - `app_mention`
  - `message` (for channel message tracking)
  - `message.im`
- Bot Token Scopes:
  - `app_mentions:read`
  - `chat:write`
  - `channels:history` (to read channel messages)
  - `channels:read` (to access channel info)
  - `groups:history` (for private channels)
  - `groups:read` (for private channel info)
  - `im:history`
  - `im:read`
  - `users:read` (to get user names)

## Features

- **Conversation History**: The bot maintains conversation context from the last 100 messages (or 24 hours) in each channel
- **Contextual Responses**: When mentioned, the bot uses recent conversation history to provide more relevant responses
- **Direct Messages**: Full conversation support in DMs
- **Channel Awareness**: Tracks all messages in channels where the bot is present
- **Knowledge Base Integration**: 
  - **Notion**: Syncs pages and subpages, provides citations with URLs
  - **Airtable**: Syncs base records from all tables, provides citations with record URLs
  - Automatic hourly updates from all knowledge sources
  - RAG (Retrieval Augmented Generation) for enhanced responses