#!/bin/bash
# Manual Server Deployment Script for AI Domain Discovery System
# Usage: ./deploy-manual.sh

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║   AI DOMAIN DISCOVERY - MANUAL DEPLOYMENT               ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo "❌ Please do not run as root"
  exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    postgresql \
    postgresql-contrib \
    nginx \
    supervisor \
    git \
    curl

echo "✅ System dependencies installed"

# Get database password
echo ""
echo "🔐 Database Configuration"
read -sp "Enter PostgreSQL password (min 12 characters): " DB_PASSWORD
echo ""

if [ ${#DB_PASSWORD} -lt 12 ]; then
    echo "❌ Password too short! Must be at least 12 characters."
    exit 1
fi

# Setup PostgreSQL
echo ""
echo "🗄️  Setting up PostgreSQL..."

sudo -u postgres psql << PSQL
CREATE DATABASE aidomains;
CREATE USER aidomains WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE aidomains TO aidomains;
PSQL

echo "✅ PostgreSQL configured"

# Create virtual environment
echo ""
echo "🐍 Creating Python virtual environment..."
cd backend
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Python dependencies installed"

# Create .env file
echo ""
echo "📝 Creating configuration..."

cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://aidomains:${DB_PASSWORD}@localhost:5432/aidomains
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
CT_LOG_API=https://crt.sh
DISCOVERY_SCHEDULE=0 9,14,20 * * *
MAX_CONCURRENT_VALIDATIONS=20
DOMAIN_TIMEOUT=3
TZ=UTC
EOF

echo "✅ Configuration created"

# Initialize database
echo ""
echo "🗄️  Initializing database..."
python -c "from services.database import init_db; import asyncio; asyncio.run(init_db())"

echo "✅ Database initialized"

# Create log directory
echo ""
echo "📁 Creating log directory..."
sudo mkdir -p /var/log/aidomains
sudo chown $USER:$USER /var/log/aidomains

# Create systemd services
echo ""
echo "⚙️  Creating systemd services..."

# API service
sudo tee /etc/systemd/system/aidomains-api.service > /dev/null << APISERVICE
[Unit]
Description=AI Domain Discovery API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

StandardOutput=append:/var/log/aidomains/api.log
StandardError=append:/var/log/aidomains/api-error.log

[Install]
WantedBy=multi-user.target
APISERVICE

# Scheduler service
sudo tee /etc/systemd/system/aidomains-scheduler.service > /dev/null << SCHEDULERSERVICE
[Unit]
Description=AI Domain Discovery Scheduler
After=network.target postgresql.service aidomains-api.service
Requires=postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/python daily_discovery.py --schedule
Restart=always
RestartSec=10

StandardOutput=append:/var/log/aidomains/scheduler.log
StandardError=append:/var/log/aidomains/scheduler-error.log

[Install]
WantedBy=multi-user.target
SCHEDULERSERVICE

echo "✅ Systemd services created"

# Enable and start services
echo ""
echo "🚀 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable aidomains-api aidomains-scheduler
sudo systemctl start aidomains-api aidomains-scheduler

sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
sudo systemctl status aidomains-api --no-pager -l
echo ""
sudo systemctl status aidomains-scheduler --no-pager -l

# Check health
echo ""
echo "🏥 Checking API health..."
if curl -f http://localhost:8000/api/health &> /dev/null; then
    echo "✅ API is healthy!"
else
    echo "⚠️  API not responding yet. Check logs with: sudo journalctl -u aidomains-api -f"
fi

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
echo "  View API logs:        sudo journalctl -u aidomains-api -f"
echo "  View scheduler logs:  sudo journalctl -u aidomains-scheduler -f"
echo "  Restart services:     sudo systemctl restart aidomains-api aidomains-scheduler"
echo "  Stop services:        sudo systemctl stop aidomains-api aidomains-scheduler"
echo "  Service status:       sudo systemctl status aidomains-api aidomains-scheduler"
echo ""
echo "📖 Next steps:"
echo "  1. Setup Nginx reverse proxy (see DEPLOYMENT_GUIDE.md)"
echo "  2. Configure SSL with certbot"
echo "  3. Setup automated backups"
echo "  4. Configure monitoring"
echo ""
echo "📖 Full deployment guide: ../DEPLOYMENT_GUIDE.md"
echo ""
