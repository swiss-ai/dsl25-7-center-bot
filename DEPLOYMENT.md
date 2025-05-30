# Slack Bot Docker Deployment Guide

## Prerequisites

1. **Install Docker and Docker Compose**:
   ```bash
   # Ubuntu/Debian
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

2. **Configure Environment Variables**:
   - Copy `.env.example` to `.env`
   - Update all required values in `.env`

## Deployment Steps

### Development Deployment

1. **Start services**:
   ```bash
   ./scripts/docker-dev.sh up
   ```

2. **Check service status**:
   ```bash
   ./scripts/docker-dev.sh status
   ```

3. **View logs**:
   ```bash
   ./scripts/docker-dev.sh logs
   ```

### Production Deployment

1. **Deploy to production**:
   ```bash
   ./scripts/docker-prod.sh deploy
   ```

2. **Check health**:
   ```bash
   ./scripts/docker-prod.sh health
   ```

## What Happens During Deployment

### When you run `docker-compose up`:

1. **Build Phase**:
   - Docker builds the Slack bot image from the Dockerfile
   - Installs all Python dependencies from requirements.txt
   - Sets up the application structure

2. **Service Startup Order**:
   - Redis starts first (for caching and rate limiting)
   - ChromaDB starts (vector database for knowledge storage)
   - Slack bot waits for dependencies to be healthy before starting

3. **Volume Mounts**:
   - `./data` → Persistent storage for ChromaDB and cache
   - `./logs` → Application logs
   - `./config` → Configuration files
   - `./src` → Source code (read-write in dev, read-only in prod)

4. **Network Setup**:
   - All services communicate on internal network `slack-bot-network`
   - Exposed ports:
     - 8000: ChromaDB API
     - 6379: Redis (dev only)
     - 8081: Redis Commander (dev only, optional)

## Manual Docker Commands

If you prefer to run Docker commands directly:

### Development
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f slack-bot

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

### Production
```bash
# Use production compose files
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Scale the bot
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale slack-bot=2

# View production logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 slack-bot
```

## Troubleshooting

### Check container health:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Access container shell:
```bash
docker-compose exec slack-bot /bin/sh
```

### View Redis data:
```bash
docker-compose exec redis redis-cli
```

### Reset everything:
```bash
docker-compose down -v
rm -rf data/chroma/*
docker-compose up -d
```

## Required Environment Variables

The following must be set in your `.env` file:

- `SLACK_APP_TOKEN`: Your Slack app token (starts with xapp-)
- `SLACK_BOT_TOKEN`: Your Slack bot token (starts with xoxb-)
- `SLACK_SIGNING_SECRET`: Your Slack signing secret
- `CLAUDE_API_KEY`: Your Anthropic Claude API key

## Security Notes

1. Never commit `.env` file to version control
2. Use strong passwords for Redis in production
3. Enable ChromaDB authentication in production
4. Use HTTPS/SSL for external communications
5. Regularly update base images for security patches