#!/bin/bash
# Production Docker helper script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
    exit 1
fi

# Function to backup data
backup_data() {
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_dir="backups/${timestamp}"
    
    print_info "Creating backup in ${backup_dir}..."
    mkdir -p "${backup_dir}"
    
    # Backup volumes
    docker run --rm -v slack-bot_chroma-data:/data -v $(pwd)/${backup_dir}:/backup alpine tar czf /backup/chroma-data.tar.gz -C /data .
    docker run --rm -v slack-bot_redis-data:/data -v $(pwd)/${backup_dir}:/backup alpine tar czf /backup/redis-data.tar.gz -C /data .
    
    # Backup config
    cp -r config "${backup_dir}/"
    cp .env "${backup_dir}/"
    
    print_info "Backup completed in ${backup_dir}"
}

# Function to check service health
check_health() {
    print_info "Checking service health..."
    
    # Check Slack bot
    if docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T slack-bot python -c "import sys; sys.exit(0)" 2>/dev/null; then
        echo -e "Slack Bot: ${GREEN}Healthy${NC}"
    else
        echo -e "Slack Bot: ${RED}Unhealthy${NC}"
    fi
    
    # Check ChromaDB
    if curl -f http://localhost:8000/api/v1/heartbeat >/dev/null 2>&1; then
        echo -e "ChromaDB: ${GREEN}Healthy${NC}"
    else
        echo -e "ChromaDB: ${RED}Unhealthy${NC}"
    fi
    
    # Check Redis
    if docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T redis redis-cli ping >/dev/null 2>&1; then
        echo -e "Redis: ${GREEN}Healthy${NC}"
    else
        echo -e "Redis: ${RED}Unhealthy${NC}"
    fi
}

# Main command handler
case "$1" in
    deploy)
        print_info "Building production image..."
        docker build -t slack-knowledge-bot:latest .
        
        print_info "Starting production services..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        
        sleep 10
        check_health
        ;;
    
    update)
        print_info "Updating production deployment..."
        
        # Backup first
        backup_data
        
        # Build new image
        docker build -t slack-knowledge-bot:latest .
        
        # Rolling update
        print_info "Performing rolling update..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --scale slack-bot=2 slack-bot
        
        sleep 30
        check_health
        ;;
    
    stop)
        print_info "Stopping production services..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
        ;;
    
    logs)
        service=${2:-slack-bot}
        lines=${3:-100}
        print_info "Showing last $lines lines of logs for $service..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=$lines $service
        ;;
    
    backup)
        backup_data
        ;;
    
    restore)
        if [ -z "$2" ]; then
            print_error "Please specify backup directory"
            exit 1
        fi
        
        backup_dir=$2
        if [ ! -d "$backup_dir" ]; then
            print_error "Backup directory not found: $backup_dir"
            exit 1
        fi
        
        print_warning "This will restore from backup: $backup_dir"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Stop services
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
            
            # Restore volumes
            docker run --rm -v slack-bot_chroma-data:/data -v $(pwd)/${backup_dir}:/backup alpine tar xzf /backup/chroma-data.tar.gz -C /data
            docker run --rm -v slack-bot_redis-data:/data -v $(pwd)/${backup_dir}:/backup alpine tar xzf /backup/redis-data.tar.gz -C /data
            
            # Restore config
            cp -r ${backup_dir}/config/* config/
            cp ${backup_dir}/.env .env
            
            print_info "Restore completed"
        fi
        ;;
    
    health)
        check_health
        ;;
    
    monitor)
        print_info "Starting monitoring stack..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml --profile monitoring up -d
        print_info "Grafana available at http://localhost:3000"
        print_info "Prometheus available at http://localhost:9090"
        ;;
    
    scale)
        if [ -z "$2" ]; then
            print_error "Please specify number of replicas"
            exit 1
        fi
        
        replicas=$2
        print_info "Scaling slack-bot to $replicas replicas..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --scale slack-bot=$replicas slack-bot
        ;;
    
    *)
        echo "Usage: $0 {deploy|update|stop|logs|backup|restore|health|monitor|scale} [options]"
        echo ""
        echo "Commands:"
        echo "  deploy           - Deploy production services"
        echo "  update           - Update deployment (with backup)"
        echo "  stop             - Stop all services"
        echo "  logs [service]   - Show logs for service"
        echo "  backup           - Backup data and config"
        echo "  restore [dir]    - Restore from backup"
        echo "  health           - Check service health"
        echo "  monitor          - Start monitoring stack"
        echo "  scale [n]        - Scale slack-bot to n replicas"
        exit 1
        ;;
esac