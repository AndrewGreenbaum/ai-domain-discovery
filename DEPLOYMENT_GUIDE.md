# AI Domain Discovery - Complete Deployment Guide

**Last Updated**: November 23, 2025
**Status**: ✅ FULLY DEPLOYED AND OPERATIONAL

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCTION SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Frontend (Vercel)                                          │
│  └─ URL: https://carya-ai-domain-discovery-a9ni9k5ww.vercel.app
│  └─ Auto-deploys on git push                                │
│  └─ TypeScript + React + Vite                               │
│                                                             │
│  Backend (EC2: 3.236.14.219)                               │
│  └─ Ubuntu 24.04 LTS                                        │
│  └─ Python 3.12 + FastAPI                                   │
│  └─ PostgreSQL Database                                     │
│  └─ LLM System (Claude API)                                 │
│  └─ Auto-retrain Process (PID varies)                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Current Deployment Status

### Backend (EC2)
- **IP**: 3.236.14.219
- **User**: ubuntu
- **OS**: Ubuntu 24.04.3 LTS
- **Location**: `/home/ubuntu/ai-domain-discovery/`
- **Status**: ✅ Running

### Frontend (Vercel)
- **URL**: https://carya-ai-domain-discovery-a9ni9k5ww.vercel.app
- **Project**: carya-ai-domain-discovery
- **Status**: ✅ Deployed

### Database (PostgreSQL on EC2)
- **Host**: localhost (on EC2)
- **Port**: 5432
- **Database**: aidomains
- **Status**: ✅ Running

---

## Access Information

### SSH to EC2 Backend

**Method 1 - Easy Script** (from local machine):
```bash
~/ec2_connect.sh
```

**Method 2 - Direct Command** (from local machine):
```bash
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219
```

**Method 3 - SSH Config Alias** (if configured):
```bash
ssh ec2-backend
```

### Key File Location
- **Local**: `<REDACTED_KEY_PATH>`
- **Permissions**: 400 (already set correctly)

---

## Environment Configuration

### Backend .env File (on EC2)

Location: `/home/ubuntu/ai-domain-discovery/backend/.env`

**Required Variables**:
```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aidomains

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Claude AI (LLM System)
ANTHROPIC_API_KEY=<REDACTED_ANTHROPIC_KEY>

# Discovery Settings
DISCOVERY_SCHEDULE=0 9,14,20 * * *
MAX_CONCURRENT_VALIDATIONS=10
DOMAIN_TIMEOUT=2

# Smart Pipeline Thresholds
INVESTIGATION_SCORE_THRESHOLD=60
ENRICHMENT_SCORE_THRESHOLD=70

# Concurrency Limits
MAX_CONCURRENT_INVESTIGATIONS=3
MAX_CONCURRENT_ENRICHMENTS=2

# Screenshot/Enrichment
SCREENSHOT_ENABLED=true
SCREENSHOT_TIMEOUT=30
SCREENSHOT_STORAGE=s3

# AWS S3 (if using screenshots)
AWS_S3_BUCKET=
AWS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Security
ALLOWED_ORIGINS=https://carya-ai-domain-discovery-a9ni9k5ww.vercel.app
API_KEY_ENABLED=false

# MCP Services
BRAVE_SEARCH_API_KEY=
```

### Frontend .env File (Vercel)

Location: Vercel Dashboard → Environment Variables

**Required Variables**:
```bash
VITE_API_URL=http://3.236.14.219:8000
```

---

## Critical System Components

### 1. Backend Services Running on EC2

Check what's running:
```bash
# SSH to EC2
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219

# Check backend process
ps aux | grep "python3 main.py"

# Check auto-retrain process
ps aux | grep auto_retrain

# Check database
sudo systemctl status postgresql
```

### 2. Auto-Retrain Process

**Current Status**: Running (check PID with `ps aux | grep auto_retrain`)

**Location**: `/home/ubuntu/ai-domain-discovery/backend/auto_retrain.py`

**Start Command**:
```bash
cd ~/ai-domain-discovery/backend
nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &
```

**Log File**: `logs/auto_retrain.log`

### 3. LLM Training System

**Status**: ✅ Configured and operational

**Components**:
- `services/llm_evaluator.py` - Claude API integration
- `agents/hybrid_scorer.py` - Routing logic
- `feedback_system.py` - Training data collection
- `auto_retrain.py` - Continuous improvement

**Check Status**:
```bash
cd ~/ai-domain-discovery/backend
python3 check_llm_system.py
python3 training_status.py
```

### 4. Domain Age Filtering (Phase 3)

**Status**: ✅ Deployed November 23, 2025

**Components**:
- `services/whois_service.py` - WHOIS lookups
- `agents/validation.py` - Captures domain age
- `agents/scoring.py` - Applies age penalty (>90 days → 15/100)

**Test**:
```bash
cd ~/ai-domain-discovery/backend
python3 test_domain_age_filter.py
```

---

## Common Operations

### Deploy Backend Updates

**From Local Machine**:
```bash
# 1. Upload changes to EC2
scp -i "<REDACTED_KEY_PATH>" -r ~/ai-domain-discovery/backend/* ubuntu@3.236.14.219:~/ai-domain-discovery/backend/

# 2. SSH to EC2
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219

# 3. On EC2, restart services
cd ~/ai-domain-discovery/backend
pkill -f "python3 main.py"
pkill -f "auto_retrain.py"

# 4. Restart backend
nohup python3 main.py > logs/backend.log 2>&1 &

# 5. Restart auto-retrain
nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &

# 6. Verify
ps aux | grep python3
tail -f logs/backend.log
```

### Deploy Frontend Updates

**From Local Machine**:
```bash
cd ~/ai-domain-discovery/frontend
vercel --prod
```

Vercel auto-deploys on git push if repository is connected.

### Check System Health

**SSH to EC2 and run**:
```bash
cd ~/ai-domain-discovery/backend

# System status
python3 check_llm_system.py

# Training progress
python3 training_status.py

# View logs
tail -f logs/backend.log
tail -f logs/auto_retrain.log

# Check database
psql -U postgres -d aidomains -c "SELECT COUNT(*) FROM domains;"
```

### View Recent Discoveries

```bash
cd ~/ai-domain-discovery/backend
python3 -c "
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://postgres:postgres@localhost:5432/aidomains')
with engine.connect() as conn:
    result = conn.execute(text('SELECT domain, quality_score, category, discovered_at FROM domains ORDER BY discovered_at DESC LIMIT 10'))
    for row in result:
        print(f'{row[0]:20} {row[1]:3}/100 {row[2]:20} {row[3]}')
"
```

### Restart Everything

```bash
# SSH to EC2
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219

# Stop all
pkill -f "python3 main.py"
pkill -f "auto_retrain.py"
sudo systemctl restart postgresql

# Start all
cd ~/ai-domain-discovery/backend
nohup python3 main.py > logs/backend.log 2>&1 &
nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &

# Verify
ps aux | grep python3
```

---

## Monitoring & Logs

### Log Locations (on EC2)

```bash
# Backend API logs
~/ai-domain-discovery/backend/logs/backend.log

# Auto-retrain logs
~/ai-domain-discovery/backend/logs/auto_retrain.log

# Discovery logs
~/ai-domain-discovery/backend/logs/discovery.log

# System logs
/var/log/syslog
```

### View Live Logs

```bash
# Backend
tail -f ~/ai-domain-discovery/backend/logs/backend.log

# Auto-retrain
tail -f ~/ai-domain-discovery/backend/logs/auto_retrain.log

# All logs
tail -f ~/ai-domain-discovery/backend/logs/*.log
```

### Monitor System Resources

```bash
# CPU and memory
htop

# Disk usage
df -h

# Database size
sudo du -sh /var/lib/postgresql/

# Check running processes
ps aux | grep python3
```

---

## Troubleshooting

### Backend Not Responding

```bash
# Check if running
ps aux | grep "python3 main.py"

# Check logs for errors
tail -100 ~/ai-domain-discovery/backend/logs/backend.log

# Restart
cd ~/ai-domain-discovery/backend
pkill -f "python3 main.py"
nohup python3 main.py > logs/backend.log 2>&1 &
```

### Auto-Retrain Not Running

```bash
# Check if running
ps aux | grep auto_retrain

# Check logs
tail -100 ~/ai-domain-discovery/backend/logs/auto_retrain.log

# Restart
cd ~/ai-domain-discovery/backend
pkill -f auto_retrain
nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &
```

### Database Issues

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql

# Connect to database
sudo -u postgres psql aidomains

# Check table sizes
sudo -u postgres psql aidomains -c "\dt+"
```

### LLM System Not Working

```bash
cd ~/ai-domain-discovery/backend

# Check configuration
python3 check_llm_system.py

# Test Claude API directly
python3 test_claude_direct.py

# View LLM usage
python3 training_status.py
```

---

## Security Notes

### Firewall Rules (EC2 Security Group)

**Required Ports**:
- **22** (SSH): Your IP only
- **8000** (API): 0.0.0.0/0 (or restrict to Vercel IPs)
- **5432** (PostgreSQL): localhost only (NOT exposed)

### API Key Management

**NEVER** commit these to git:
- `ANTHROPIC_API_KEY`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- Database passwords

**Stored in**:
- EC2: `/home/ubuntu/ai-domain-discovery/backend/.env`
- Local: `/home/umichleg/ai-domain-discovery/backend/.env`
- Vercel: Dashboard → Environment Variables

---

## Backup & Recovery

### Database Backup

```bash
# Backup database
sudo -u postgres pg_dump aidomains > backup_$(date +%Y%m%d).sql

# Restore database
sudo -u postgres psql aidomains < backup_20251123.sql
```

### Code Backup

```bash
# From EC2 to local
scp -i "<REDACTED_KEY_PATH>" -r ubuntu@3.236.14.219:~/ai-domain-discovery ~/backup_$(date +%Y%m%d)

# From local to EC2
scp -i "<REDACTED_KEY_PATH>" -r ~/ai-domain-discovery ubuntu@3.236.14.219:~/ai-domain-discovery_backup
```

---

## Quick Reference Commands

```bash
# SSH to EC2
~/ec2_connect.sh

# Check system status
cd ~/ai-domain-discovery/backend && python3 check_llm_system.py

# Check training progress
cd ~/ai-domain-discovery/backend && python3 training_status.py

# View backend logs
tail -f ~/ai-domain-discovery/backend/logs/backend.log

# Restart backend
cd ~/ai-domain-discovery/backend && pkill -f "python3 main.py" && nohup python3 main.py > logs/backend.log 2>&1 &

# Restart auto-retrain
cd ~/ai-domain-discovery/backend && pkill -f auto_retrain && nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &

# Deploy frontend
cd ~/ai-domain-discovery/frontend && vercel --prod

# Check database
sudo -u postgres psql aidomains -c "SELECT COUNT(*) FROM domains;"
```

---

## Contact & Support

**System Owner**: umichleg
**EC2 Instance**: 3.236.14.219
**Frontend**: https://carya-ai-domain-discovery-a9ni9k5ww.vercel.app

**Documentation**:
- `DEPLOYMENT_GUIDE.md` (this file)
- `PHASE_3_DOMAIN_AGE_FIX.md` - Domain age filtering
- `LLM_OVERVIEW.md` - LLM system documentation
- `LLM_AGENT_GUIDE.md` - For AI agents
- `LLM_QUICK_REF.md` - Quick reference

---

**Last Verified**: November 23, 2025
**Status**: ✅ All systems operational
