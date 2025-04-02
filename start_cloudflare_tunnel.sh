#!/bin/bash

# Define usage function
usage() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  -c, --config     Use the configuration file (cloudflared-config.yml)"
  echo "  -q, --quick      Quick mode (no config file, just expose API)"
  echo "  -h, --help       Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 --quick       Start a quick tunnel to localhost:8000"
  echo "  $0 --config      Start tunnel using the configuration file"
  exit 1
}

# Default to quick mode if no args provided
if [ $# -eq 0 ]; then
  MODE="quick"
else
  case "$1" in
    -c|--config)
      MODE="config"
      ;;
    -q|--quick)
      MODE="quick"
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: Unknown option $1"
      usage
      ;;
  esac
fi

# Start Cloudflare Tunnel
if [ "$MODE" = "quick" ]; then
  echo "Starting Cloudflare Tunnel in quick mode to expose the API at http://localhost:8000..."
  cloudflared tunnel --url http://localhost:8000
elif [ "$MODE" = "config" ]; then
  echo "Starting Cloudflare Tunnel using configuration file..."
  
  if [ ! -f "cloudflared-config.yml" ]; then
    echo "Error: Configuration file 'cloudflared-config.yml' not found!"
    exit 1
  fi
  
  cloudflared tunnel --config cloudflared-config.yml run
fi