#!/bin/bash
# Quick Docker Deployment Script for AI Domain Discovery System
# Usage: ./deploy-docker.sh

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║   AI DOMAIN DISCOVERY - DOCKER DEPLOYMENT               ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo "❌ Please do not run as root"
  exit 1
fi

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed. Please log out and log back in, then run this script again."
    exit 0
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Installing..."
    sudo apt update
    sudo apt install docker-compose -y
fi

echo "✅ Prerequisites met"
echo ""

# Get database password
echo "🔐 Database Configuration"
read -sp "Enter PostgreSQL password (min 12 characters): " DB_PASSWORD
echo ""

if [ ${#DB_PASSWORD} -lt 12 ]; then
    echo "❌ Password too short! Must be at least 12 characters."
    exit 1
fi

# Get domain name (optional)
echo ""
echo "🌐 Domain Configuration (optional)"
read -p "Enter your domain name (leave empty for localhost): " DOMAIN_NAME

# Create .env file
echo ""
echo "📝 Creating configuration..."

cat > backend/.env << EOF
# Database
DATABASE_URL=postgresql+asyncpg://aidomains:${DB_PASSWORD}@db:5432/aidomains

# API
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# CT Logs
CT_LOG_API=https://crt.sh

# Schedule (3x daily: 9 AM, 2 PM, 8 PM UTC)
DISCOVERY_SCHEDULE=0 9,14,20 * * *

# Performance
MAX_CONCURRENT_VALIDATIONS=20
DOMAIN_TIMEOUT=3

# Timezone
TZ=UTC
EOF

echo "✅ Configuration created"

# Create docker-compose.yml
echo ""
echo "🐳 Creating Docker Compose configuration..."

cat > docker-compose.yml << 'DOCKERCOMPOSE'
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: aidomains-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: aidomains
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: aidomains
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - aidomains-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aidomains"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: aidomains-backend
    restart: unless-stopped
    env_file:
      - backend/.env
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
    networks:
      - aidomains-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  scheduler:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: aidomains-scheduler
    restart: unless-stopped
    env_file:
      - backend/.env
    command: python daily_discovery.py --schedule
    volumes:
      - ./logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
    networks:
      - aidomains-network

networks:
  aidomains-network:
    driver: bridge

volumes:
  postgres_data:
    driver: local
DOCKERCOMPOSE

# Replace ${DB_PASSWORD} in docker-compose.yml
sed -i "s/\${DB_PASSWORD}/$DB_PASSWORD/g" docker-compose.yml

echo "✅ Docker Compose configuration created"

# Create Dockerfile if it doesn't exist
if [ ! -f "docker/Dockerfile" ]; then
    echo ""
    echo "🐳 Creating Dockerfile..."
    mkdir -p docker

    cat > docker/Dockerfile << 'DOCKERFILE'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p /app/logs

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "main.py"]
DOCKERFILE

    echo "✅ Dockerfile created"
fi

# Build and start services
echo ""
echo "🏗️  Building Docker images..."
docker-compose build

echo ""
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo ""
echo "🏥 Checking service health..."
if curl -f http://localhost:8000/api/health &> /dev/null; then
    echo "✅ API is healthy!"
else
    echo "⚠️  API not responding yet. Check logs with: docker-compose logs -f"
fi

# Display status
echo ""
echo "📊 Service Status:"
docker-compose ps

# Create logs directory
mkdir -p logs

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║   🎉 DEPLOYMENT SUCCESSFUL!                             ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "📡 API: http://localhost:8000"
echo "📚 Documentation: http://localhost:8000/docs"
echo "🏥 Health Check: http://localhost:8000/api/health"
echo ""
echo "🔧 Useful Commands:"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart:          docker-compose restart"
echo "  Run discovery:    docker-compose exec backend python daily_discovery.py --once"
echo "  Check metrics:    curl http://localhost:8000/api/metrics/dashboard | jq"
echo ""

if [ -n "$DOMAIN_NAME" ]; then
    echo "🌐 Next steps for domain setup:"
    echo "  1. Point $DOMAIN_NAME to this server's IP"
    echo "  2. Install Nginx: sudo apt install nginx"
    echo "  3. Setup SSL: sudo certbot --nginx -d $DOMAIN_NAME"
    echo ""
fi

echo "📖 Full deployment guide: DEPLOYMENT_GUIDE.md"
echo ""
