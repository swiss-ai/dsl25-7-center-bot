# Firecrawl Integration

This document explains how to use the Firecrawl integration to crawl and vectorize websites efficiently.

## Overview

Firecrawl is an advanced web crawling solution that allows for more efficient and comprehensive crawling of websites compared to simple URL fetching. The integration enables:

- Crawling entire websites including subdomains
- Respecting robots.txt rules
- Configurable crawl depth and concurrency
- Scheduled periodic crawling
- Exclusion patterns to skip certain pages
- Vectorizing content for Claude's knowledge base

## Setup

1. Install required dependencies:
   ```bash
   pip install firecrawl==0.1.11 schedule==1.2.1
   ```

2. Enable Firecrawl in your `.env` file:
   ```
   FIRECRAWL_ENABLED=true
   FIRECRAWL_CONFIG_PATH=/path/to/crawl_config.yaml
   ```

3. Create a configuration file (default: `crawl_config.yaml`):
   ```yaml
   # Global configuration - applied to all sites unless overridden
   global:
     crawl_interval: 24  # Daily
     max_pages: 100
     include_subdomains: true
     max_depth: 3
     respect_robots_txt: true
     delay: 1.0
     concurrency: 5
     timeout: 30

   # Sites to crawl
   sites:
     - url: https://example.com/
       max_depth: 2

   # URLs to exclude
   exclude_patterns:
     - "*login*"
     - "*checkout*"
   ```

## Managing Crawl Configuration

Use the `edit_crawl_config.py` script to manage your crawl configuration:

```bash
# List all configured sites
python edit_crawl_config.py list

# Add a new site
python edit_crawl_config.py add --url https://example.com --depth 2

# Remove a site
python edit_crawl_config.py remove --url https://example.com

# Update global settings
python edit_crawl_config.py global --setting max_pages=200

# Add exclusion pattern
python edit_crawl_config.py exclude-add --pattern "*admin*"

# Remove exclusion pattern
python edit_crawl_config.py exclude-remove --pattern "*admin*"
```

## Manual Crawling

You can manually trigger crawls using the `manual_crawl.py` script:

```bash
# Crawl all sites in configuration
python manual_crawl.py --all

# Crawl a specific URL
python manual_crawl.py --url https://example.com/

# Check crawl service status
python manual_crawl.py --status
```

## API Endpoints

The integration adds these API endpoints:

- `POST /api/knowledge/firecrawl/crawl?url={url}`: Trigger a crawl (if URL is provided, crawl only that URL; otherwise crawl all configured sites)
- `GET /api/knowledge/firecrawl/status`: Get the status of the Firecrawl service

## Configuration Options

### Global Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `crawl_interval` | Time between crawls (hours) | 24 |
| `max_pages` | Maximum number of pages to crawl per site | 100 |
| `include_subdomains` | Whether to follow links to subdomains | true |
| `max_depth` | Maximum crawl depth | 3 |
| `respect_robots_txt` | Whether to respect robots.txt rules | true |
| `delay` | Delay between requests (seconds) | 1.0 |
| `concurrency` | Maximum concurrent requests | 5 |
| `timeout` | Request timeout (seconds) | 30 |

### Site-Specific Overrides

Any global setting can be overridden for specific sites. Additionally:

| Setting | Description |
|---------|-------------|
| `params` | Query parameters to add to the URL |

### Exclusion Patterns

Exclusion patterns support wildcards (`*`) and will prevent crawling any matching URLs. Some recommended patterns:

- `*login*`, `*signin*` - Skip login pages
- `*download*` - Skip download pages
- `*.pdf`, `*.zip` - Skip specific file types
- `*private*`, `*account*` - Skip private/account pages

## How It Works

1. The Firecrawl service initializes on application startup if enabled
2. It reads the configuration file and schedules crawls based on intervals
3. During a crawl, it fetches pages and follows links according to your settings
4. Content is converted from HTML to clean text
5. The text is chunked and stored in the vector database
6. Claude can search and use this content when answering questions

## Troubleshooting

- Logs will indicate any issues with Firecrawl initialization
- Check the application logs for crawl results and any errors
- Use the status endpoint or script to verify the service is running
- Make sure the configured URLs are accessible and allow crawling