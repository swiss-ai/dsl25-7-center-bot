#!/bin/bash
# Development Docker helper script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Creating .env from .env.example..."
    cp .env.example .env
    print_warning "Please update .env with your actual configuration values"
    exit 1
fi

# Main command handler
case "$1" in
    up)
        print_info "Starting development environment..."
        docker-compose up -d
        print_info "Services started. Checking health..."
        sleep 5
        docker-compose ps
        ;;
    
    down)
        print_info "Stopping development environment..."
        docker-compose down
        ;;
    
    restart)
        print_info "Restarting development environment..."
        docker-compose restart
        ;;
    
    logs)
        service=${2:-slack-bot}
        print_info "Showing logs for $service..."
        docker-compose logs -f $service
        ;;
    
    build)
        print_info "Building development images..."
        docker-compose build --no-cache
        ;;
    
    shell)
        service=${2:-slack-bot}
        print_info "Opening shell in $service container..."
        docker-compose exec $service /bin/sh
        ;;
    
    test)
        print_info "Running tests in container..."
        docker-compose exec slack-bot pytest tests/
        ;;
    
    clean)
        print_warning "This will remove all containers, volumes, and images!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down -v --rmi all
            print_info "Cleanup complete"
        fi
        ;;
    
    status)
        print_info "Service status:"
        docker-compose ps
        echo
        print_info "Container health:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    
    sync)
        print_info "Triggering knowledge sync..."
        docker-compose exec slack-bot python -m scripts.index_sources
        ;;
    
    redis-cli)
        print_info "Connecting to Redis..."
        docker-compose exec redis redis-cli
        ;;
    
    *)
        echo "Usage: $0 {up|down|restart|logs|build|shell|test|clean|status|sync|redis-cli} [service]"
        echo ""
        echo "Commands:"
        echo "  up        - Start all services"
        echo "  down      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  logs      - Show logs (optionally specify service)"
        echo "  build     - Build/rebuild images"
        echo "  shell     - Open shell in container (optionally specify service)"
        echo "  test      - Run tests"
        echo "  clean     - Remove all containers, volumes, and images"
        echo "  status    - Show service status"
        echo "  sync      - Trigger knowledge source sync"
        echo "  redis-cli - Connect to Redis CLI"
        exit 1
        ;;
esac