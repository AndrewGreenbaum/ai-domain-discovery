# Quick Start Guide for AI Agents

**Purpose**: Help AI agents quickly understand and work with this system

---

## System Overview

**What**: AI Domain Discovery System - Finds new .ai domains daily, filters out old/established companies

**Where**:
- Backend: EC2 (44.221.89.157)
- Frontend: Vercel (https://carya-ai-domain-discovery-a9ni9k5ww.vercel.app)
- Database: PostgreSQL on EC2

**Status**: ✅ Fully operational (as of Nov 23, 2025)

---

## Critical Information

### SSH Access
```bash
# Easy method (use this)
~/ec2_connect.sh

# Manual method
ssh -i "<REDACTED_KEY_PATH>" ubuntu@44.221.89.157
```

### Key Locations

**Backend**: `/home/ubuntu/ai-domain-discovery/backend/` (on EC2)  
**Frontend**: `/home/umichleg/ai-domain-discovery/frontend/` (local)  
**Docs**: `/home/umichleg/ai-domain-discovery/*.md` (local)

### Environment Config

**Backend** `.env` location: `/home/ubuntu/ai-domain-discovery/backend/.env`  
Contains: `ANTHROPIC_API_KEY`, `DATABASE_URL`, etc.

---

## Common Tasks

### Check System Status
```bash
ssh -i "<REDACTED_KEY_PATH>" ubuntu@44.221.89.157
cd ~/ai-domain-discovery/backend
python3 check_llm_system.py
python3 training_status.py
```

### View Logs
```bash
# On EC2
tail -f ~/ai-domain-discovery/backend/logs/backend.log
tail -f ~/ai-domain-discovery/backend/logs/auto_retrain.log
```

### Restart Services
```bash
# On EC2
cd ~/ai-domain-discovery/backend
pkill -f "python3 main.py"
pkill -f "auto_retrain.py"
nohup python3 main.py > logs/backend.log 2>&1 &
nohup python3 auto_retrain.py --monitor --interval 3600 > logs/auto_retrain.log 2>&1 &
```

### Deploy Updates

**Backend**:
```bash
# Upload changes
scp -i "<REDACTED_KEY_PATH>" -r ~/ai-domain-discovery/backend/* ubuntu@44.221.89.157:~/ai-domain-discovery/backend/

# Restart (see above)
```

**Frontend**:
```bash
cd ~/ai-domain-discovery/frontend
vercel --prod
```

---

## Key Features Implemented

### Phase 1: Redirect Detection ✅
- Detects domains that redirect elsewhere
- Penalty: Cap at 20/100

### Phase 1.5: Domain Age Filtering ✅ (Nov 23, 2025)
- Uses WHOIS to check registration date
- Penalty: Domains >90 days old → Cap at 15/100
- Prevents old domains from scoring as "new discoveries"

### Phase 2: Parent Company Detection ✅
- Detects established companies
- Penalty: Cap at 20/100

### LLM Training System ✅
- Hybrid scorer (agents + Claude AI)
- Auto-retrain when 5+ examples collected
- Self-improving over time

---

## Important Files

**Must Read**:
- `DEPLOYMENT_GUIDE.md` - Complete deployment documentation
- `SYSTEM_STATE.md` - Current system state
- `PHASE_3_DOMAIN_AGE_FIX.md` - Domain age filtering details

**LLM System**:
- `LLM_OVERVIEW.md` - LLM system overview
- `LLM_AGENT_GUIDE.md` - Detailed guide for agents
- `LLM_QUICK_REF.md` - Quick reference

**Backend Code**:
- `agents/scoring.py` - Scoring logic with penalties
- `agents/validation.py` - Validation + WHOIS
- `services/whois_service.py` - Domain age lookup
- `auto_retrain.py` - Training system

---

## Testing

```bash
# Test domain age filter
cd ~/ai-domain-discovery/backend
python3 test_domain_age_filter.py

# Test LLM system
python3 test_llm_system.py

# Test Claude API
python3 test_claude_direct.py
```

---

## Troubleshooting

**Backend not responding**:
```bash
ps aux | grep "python3 main.py"
tail -100 ~/ai-domain-discovery/backend/logs/backend.log
```

**LLM not working**:
```bash
python3 check_llm_system.py
grep ANTHROPIC_API_KEY .env
```

**Database issues**:
```bash
sudo systemctl status postgresql
sudo -u postgres psql aidomains
```

---

## Quick Reference

| Task | Command |
|------|---------|
| SSH to EC2 | `~/ec2_connect.sh` |
| Check status | `python3 check_llm_system.py` |
| View logs | `tail -f logs/backend.log` |
| Restart backend | `pkill -f "python3 main.py" && nohup python3 main.py > logs/backend.log 2>&1 &` |
| Deploy frontend | `cd frontend && vercel --prod` |
| Check database | `sudo -u postgres psql aidomains` |

---

**Read DEPLOYMENT_GUIDE.md for complete details**
