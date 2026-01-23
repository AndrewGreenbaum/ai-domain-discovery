# AI DOMAIN DISCOVERY SYSTEM - ARCHITECTURE & REFERENCE

## SYSTEM_METADATA
```yaml
last_updated: 2025-12-16
version: 4.7
status: PRODUCTION
database: PostgreSQL (docker_db_1)
api_port: 8000
frontend_port: 3000
llm_model: claude-3-5-sonnet-20241022
```

## LLM UPGRADE (Dec 16, 2025) - Anthropic Sonnet 3.5 with Vision & Web Search

### Model Upgrade: Haiku → Sonnet 3.5
| Setting | Old Value | New Value |
|---------|-----------|-----------|
| Model | `claude-3-haiku-20240307` | `claude-3-5-sonnet-20241022` |
| Input Cost | $0.25 / 1M tokens | $3.00 / 1M tokens |
| Output Cost | $1.25 / 1M tokens | $15.00 / 1M tokens |
| Vision | ❌ Not available | ✅ Full vision capabilities |
| Reasoning | Basic | Advanced reasoning |

### New LLM Capabilities

#### 1. Vision/Screenshot Analysis (`analyze_screenshot`)
The LLM can now analyze website screenshots to detect:
- **Visual quality**: Professional vs template designs
- **Parking page detection**: Visually identifies parking pages
- **Product UI visibility**: Can see if there's a real product
- **Brand presence**: Logo, colors, unique identity
- **Red flags**: Stock photos, broken images, generic templates
- **Score modifier**: -20 to +20 based on visual analysis

**Usage in llm_evaluator.py:**
```python
from services.llm_evaluator import llm_evaluator

# Capture screenshot first
screenshot_bytes = await screenshot_service.capture_screenshot(domain)

# Analyze with vision
vision_result = await llm_evaluator.analyze_screenshot(
    domain="example.ai",
    screenshot_bytes=screenshot_bytes,
    validation=validation_result
)
# Returns: visual_quality, is_parking_visual, has_real_product, design_maturity, etc.
```

#### 2. Web Search Research (`research_with_web_search`)
Uses Brave Search API to research domains, then LLM analyzes results:
- **Company existence**: Searches for company mentions across web
- **Funding history**: Detects established companies by funding rounds
- **Founding date**: Extracts company founding year
- **News mentions**: Finds recent news about the startup
- **Score modifier**: -30 to +20 based on research findings

**Usage:**
```python
research_result = await llm_evaluator.research_with_web_search(
    domain="example.ai",
    company_name="Example AI",  # Optional
    validation=validation_result
)
# Returns: company_found, is_established_company, founding_year, funding_info, etc.
```

#### 3. Enhanced Evaluation Prompts
The main `evaluate_domain` method now includes:
- Domain age information with warnings for old domains
- Parent company detection
- Redirect detection
- Stricter scoring guidelines:
  - Domain > 3 years old → MAX 15
  - Parent company detected → MAX 20
  - Redirect to established site → MAX 15
  - Established company's new product → MAX 25

### Files Modified for LLM Upgrade:
| File | Change |
|------|--------|
| `backend/llm_config.py` | Default model updated |
| `backend/config/settings.py` | `llm_model` default updated |
| `backend/services/llm_evaluator.py` | Model + Vision + Web Search added |
| `backend/services/llm_service.py` | Model default + `self.model` usage fixed |
| `backend/api/routes.py` | Fixed hardcoded model name |

### Environment Variable:
```bash
# Optional - to override model in docker/.env on EC2:
LLM_MODEL=claude-3-5-sonnet-20241022
```

## RECENT_IMPROVEMENTS (Dec 16, 2025)

### Critical Fixes Applied:
| Component | Issue Fixed | Details |
|-----------|-------------|---------|
| **API Routes** | Timezone datetime mismatch | PostgreSQL stores naive datetimes; changed `datetime.now(timezone.utc)` → `datetime.utcnow()` in all DB queries |
| **Frontend** | Missing ARIA labels | Added accessibility attributes to collapsible panels |
| **Frontend** | useCallback warnings | Wrapped fetchStatus in useCallback for SchedulerStatus and LLMStatus |
| **API Timeout** | Vercel 10s limit | Reduced axios timeout from 30s to 10s |
| Validation | Blocking DNS call | Wrapped `dns.resolver.resolve()` in `asyncio.to_thread()` with retry logic |
| Implementer | Missing LLM fields | Now saves `llm_reasoning` and `llm_cost_usd` to database |
| Discovery | Missing HN method | Synced `dns_discovery.py` with `discover_via_hacker_news()` method |
| LLM Services | Duplicate implementations | Consolidated `llm_service.py` and `llm_evaluator.py` into unified service |

### PostgreSQL Datetime Fix (CRITICAL):
**Problem**: `/api/domains` returned "Internal Server Error" with:
```
can't subtract offset-naive and offset-aware datetimes
```

**Root Cause**: PostgreSQL asyncpg driver cannot compare timezone-aware Python datetimes with naive database timestamps.

**Fix Applied** in `backend/api/routes.py`:
```python
# WRONG (causes error with PostgreSQL):
cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

# CORRECT (works with PostgreSQL):
cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
```

Fixed in these endpoints:
- `/api/domains` (line 120)
- `/api/domains/today` (line 67)
- `/api/stats/today` (line 202)
- `/api/metrics/discovery` (line 273)
- `/api/metrics/quality/today` (line 291)
- `/api/metrics/quality/range` (line 314)
- `/api/metrics/dashboard` (line 395)
- `/api/llm/status` (line 500)

### LLM Consolidation:
- **Before**: Two separate LLM services (`llm_evaluator.py` and `llm_service.py`) with different APIs
- **After**: Single unified `llm_evaluator.py` with backward-compatible aliases
- **Benefits**:
  - No more blocking calls (native async via httpx)
  - Retry logic for rate limiting on ALL LLM calls
  - Consistent response format across all consumers
  - Single source of truth for LLM configuration

### Database Changes:
- Added `llm_reasoning TEXT` column to domains table
- Added `llm_cost_usd FLOAT` column to domains table

## QUICK_COMMANDS (Copy-Paste Ready)
```bash
# === HEALTH CHECKS ===
curl -s "https://api.carya-domain-overlord.win/api/health"
curl -s "https://api.carya-domain-overlord.win/api/domains?limit=3"
curl -s "https://api.carya-domain-overlord.win/api/llm/status"

# === SSH TO EC2 ===
ssh ubuntu@3.236.14.219

# === RESTART BACKEND (on EC2) ===
cd ~/ai-domain-discovery/docker && sudo docker-compose restart backend

# === VIEW LOGS (on EC2) ===
cd ~/ai-domain-discovery/docker && sudo docker-compose logs --tail=50 backend

# === SYNC FILE TO EC2 (from local) ===
rsync -avz backend/api/routes.py ubuntu@3.236.14.219:~/ai-domain-discovery/backend/api/

# === DEPLOY FRONTEND (from local) ===
cd frontend && npm run build && vercel --prod --force --yes
```

---

## DEPLOYMENT_URLS
```yaml
# Frontend (Vercel) - PERMANENT URL
frontend_url: https://carya-ai-domain-discovery.vercel.app
# Vercel project: carya-ai-domain-discovery (linked via .vercel/project.json)

# Backend (AWS EC2)
ec2_instance_id: i-09b1d31591c588f5b
ec2_public_ip: 3.236.14.219
backend_direct_url: http://3.236.14.219:8000

# Cloudflare Tunnel (HTTPS access to backend) - PERMANENT URL
# Tunnel name: ai-domain-api
# Tunnel ID: 9bc834d6-d2bf-4c2b-804a-9372ac3d6ad4
# Auto-starts on EC2 boot via systemd service
cloudflare_tunnel_url: https://api.carya-domain-overlord.win

# To check tunnel status:
#   ssh ubuntu@3.236.14.219
#   sudo systemctl status cloudflared
```

## INDEPENDENT_OPERATION
**This system runs 24/7 WITHOUT your local computer being on.**

### How It Works:
```
┌─────────────────────────────────────────────────────────────────┐
│                    RUNS 24/7 IN THE CLOUD                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AWS EC2 Server (3.236.14.219) - DOCKER DEPLOYMENT              │
│  ├── docker_backend_1: FastAPI (port 8000)                      │
│  ├── docker_db_1: PostgreSQL (port 5432)                        │
│  ├── docker_frontend_1: React (port 3000)                       │
│  ├── Scheduler (inside backend container)                       │
│  ├── LLM Evaluator (Claude Haiku)                               │
│  └── Cloudflare Tunnel (auto-starts on boot)                    │
│                                                                 │
│  ⚠️  ENV FILE: ~/ai-domain-discovery/docker/.env                │
│                                                                 │
│  Vercel (Frontend Hosting) - PUBLIC URL                         │
│  └── React Dashboard (always available)                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Your local computer is ONLY for development/debugging.
Production runs Docker containers on EC2 + Vercel frontend.
```

### Automated Schedule:
- **9 AM UTC**: Morning discovery run
- **2 PM UTC**: Afternoon discovery run
- **8 PM UTC**: Evening discovery run

### LLM Evaluation:
- **AGGRESSIVE MODE (DEFAULT)**: LLM evaluates ALL live domains (scores 0-100)
- Mode is set via `LLM_SCORING_MODE=aggressive` in backend .env
- LLM uses Claude Haiku model (cost-effective, ~$3-5/month)

### To Verify System is Running:
```bash
# Check backend health
curl https://api.carya-domain-overlord.win/api/health

# Check scheduler
curl https://api.carya-domain-overlord.win/api/scheduler/next-run

# Check LLM status
curl https://api.carya-domain-overlord.win/api/llm/status

# Check recent discovery runs
curl https://api.carya-domain-overlord.win/api/runs/recent?limit=3
```

---

## ⚠️ CRITICAL: EC2 RUNS DOCKER (NOT DIRECT PYTHON)

### The Problem That Keeps Happening:
EC2 has **TWO different .env files** and LLMs keep editing the WRONG one!

```
EC2 Server File Structure:
├── /home/ubuntu/ai-domain-discovery/
│   ├── backend/.env          ← LOCAL DEV ONLY (NOT USED IN PRODUCTION!)
│   └── docker/.env           ← PRODUCTION (Docker uses THIS one!)
```

### WHY This Happens:
1. Documentation mentions `backend/.env` for local development
2. LLMs assume EC2 uses direct Python (`python3 main.py`)
3. **WRONG!** EC2 runs Docker: `docker-compose up`
4. Docker containers read from `docker/.env`, NOT `backend/.env`

### HOW TO CHECK (Always Verify First!):
```bash
# SSH to EC2
ssh -i "/path/to/<REDACTED_KEY_FILE>" ubuntu@3.236.14.219

# Check if Docker is running the backend
docker ps | grep backend
# If you see "docker_backend_1" → IT'S DOCKER!

# Check which .env Docker is using
cat ~/ai-domain-discovery/docker/.env
```

### CORRECT WAY TO ADD/UPDATE ENVIRONMENT VARIABLES ON EC2:

```bash
# 1. SSH to EC2
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219

# 2. Edit the DOCKER .env file (NOT backend/.env!)
nano ~/ai-domain-discovery/docker/.env
# OR append directly:
echo 'NEW_VAR=value' >> ~/ai-domain-discovery/docker/.env

# 3. Restart Docker to load new env vars
cd ~/ai-domain-discovery/docker
docker-compose restart backend

# 4. Verify the variable is loaded
docker exec docker_backend_1 python3 -c "import os; print(os.getenv('NEW_VAR'))"
```

### SYNCING LOCAL → EC2:
When you add a key to LOCAL `backend/.env`, you MUST ALSO add it to EC2's `docker/.env`:

```bash
# Example: Syncing BRAVE_SEARCH_API_KEY
LOCAL_KEY=$(grep BRAVE_SEARCH_API_KEY backend/.env | cut -d'=' -f2)
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219 \
  "echo 'BRAVE_SEARCH_API_KEY=$LOCAL_KEY' >> ~/ai-domain-discovery/docker/.env"
```

### DEPLOYING CODE CHANGES TO EC2:
```bash
# 1. Copy updated file to EC2
scp -i "<REDACTED_KEY_PATH>" \
  backend/agents/discovery.py \
  ubuntu@3.236.14.219:~/ai-domain-discovery/backend/agents/

# 2. Restart Docker (code is mounted via volume)
ssh -i "<REDACTED_KEY_PATH>" ubuntu@3.236.14.219 \
  "cd ~/ai-domain-discovery/docker && docker-compose restart backend"
```

### QUICK REFERENCE:
| Action | Local Dev | EC2 Production |
|--------|-----------|----------------|
| .env location | `backend/.env` | `docker/.env` |
| Start backend | `python3 main.py` | `docker-compose up` |
| Restart backend | `Ctrl+C` + restart | `docker-compose restart backend` |
| View logs | Terminal output | `docker logs docker_backend_1` |
| Check env var | `echo $VAR` | `docker exec docker_backend_1 env \| grep VAR` |

---

## CORE_PURPOSE
Discover NEW .ai domains registered daily to identify emerging AI startups at launch. Filter established companies, parking pages, and for-sale domains.

---

## ARCHITECTURE

### AGENT_PIPELINE
```
PLANNER -> DISCOVERY -> VALIDATION -> INVESTIGATOR -> ENRICHMENT -> HYBRID_SCORER -> IMPLEMENTER
```

### AGENT_DEFINITIONS
| Agent | File | Purpose |
|-------|------|---------|
| Planner | `agents/planner.py` | Schedule 3x daily runs (9AM, 2PM, 8PM UTC) |
| Discovery | `agents/discovery.py` | Multi-source domain finding |
| Validation | `agents/validation.py` | HTTP/DNS/SSL + parking detection |
| Investigator | `agents/investigator.py` | WHOIS, tech stack, company research |
| Enrichment | `agents/enrichment.py` | Screenshots, SEO, LLM content analysis |
| HybridScorer | `agents/hybrid_scorer.py` | Rule-based + LLM scoring |
| ScoringAgent | `agents/scoring.py` | Component scoring (used by HybridScorer) |
| Implementer | `agents/implementer.py` | Pipeline orchestration |

### DISCOVERY_SOURCES
```python
# EXPANDED Dec 2025: 7 discovery sources with 496 CT patterns, 23 startup sources
SOURCES = {
    "ct_logs": {
        "file": "services/multi_ct_logs.py",
        "patterns": 496,  # AI-related domain patterns (expanded from 272)
        "contribution": "60-70%"
    },
    "dns_enumeration": {
        "file": "services/dns_discovery.py",
        "patterns": 209,  # Common AI naming patterns
        "contribution": "5-10%"
    },
    "github_api": {
        "file": "services/github_discovery.py",
        "contribution": "10-20%"
    },
    "startup_directories": {
        "file": "services/startup_scraper.py",
        "sources": 23,  # Expanded: YC, Product Hunt, BetaList, Reddit, HN, TechCrunch, etc.
        "contribution": "10-15%"
    },
    "brave_search": {
        "file": "services/mcp_services.py",
        "requires": "BRAVE_SEARCH_API_KEY",
        "queries": 23,  # AI tool category searches
        "contribution": "bonus"
    },
    "registrar_feeds": {
        "file": "services/registrar_feeds.py",  # NEW Dec 2025
        "sources": ["RDAP", "domain auctions", "RSS feeds"],
        "contribution": "5-10%"
    },
    "hacker_news": {
        "file": "services/dns_discovery.py",
        "contribution": "5%"
    }
}
```

---

## SCORING_SYSTEM

### HYBRID_SCORER_MODES
```python
MODES = {
    "conservative": {"llm_range": [40, 70], "cost": "$0.30/month"},
    "moderate": {"llm_range": [35, 75], "cost": "$1.50/month"},
    "aggressive": {"llm_range": [0, 100], "cost": "$3-5/month"}  # DEFAULT
}
```

### SCORING_USAGE
```python
# CORRECT - Use HybridScorer
from agents.hybrid_scorer import HybridScorer
scorer = HybridScorer()
result = await scorer.score_domain(domain, validation)
# Returns: final_score, evaluation_method, cost_usd, llm_result

# DEPRECATED - Do not use ScoringAgent directly for final scores
# ScoringAgent is used internally by HybridScorer
```

### PENALTY_PHASES
```python
PENALTIES = {
    "phase_0": {"check": "not_live", "cap": 0},
    "phase_0.5": {"check": "parking OR for_sale", "cap": 35},
    "phase_1": {"check": "redirect to different domain", "cap": 20},
    "phase_1.5": {"check": "domain_age > 90 days (WHOIS)", "cap": 15},
    "phase_2": {"check": "parent_company OR company_age > 3 years", "cap": 20}
}
```

### SCORE_COMPONENTS
```python
COMPONENTS = {
    "domain_quality": 0.20,      # Name length, words, brandability
    "launch_readiness": 0.25,    # Content, functionality
    "content_originality": 0.20, # Not template/generic
    "professional_setup": 0.20,  # SSL, DNS, WHOIS
    "early_signals": 0.15        # Social links, waitlist
}
```

### CATEGORIES
```python
CATEGORIES = [
    "LAUNCHING_NOW",      # Live site, real startup
    "COMING_SOON",        # Pre-launch with waitlist
    "JUST_REGISTERED",    # Domain only, no site
    "STEALTH_MODE",       # Minimal but professional
    "INSTANT_REJECT",     # Parking/for-sale
    "REDIRECT_ESTABLISHED", # Redirects to established company
    "ESTABLISHED_COMPANY",  # Parent company > 3 years
    "PRE_EXISTING_DOMAIN"   # Domain age > 90 days
]
```

---

## LLM_INTEGRATION

### UNIFIED LLM SERVICE (Dec 2025 Consolidation)
**IMPORTANT**: There is now ONE unified LLM service. Do NOT use `llm_service.py` directly.

```python
# File: services/llm_evaluator.py (UNIFIED - use this!)
# Features:
# - Native async via httpx (no blocking)
# - Retry logic for rate limiting (3 retries, exponential backoff)
# - Scoring mode support (conservative/moderate/aggressive)
# - Cost tracking
# - Singleton instance available

from services.llm_evaluator import LLMEvaluator, llm_evaluator, llm_service

# Usage options:
evaluator = LLMEvaluator()  # New instance
evaluator = llm_evaluator   # Singleton
evaluator = llm_service     # Alias for backward compatibility

CONFIG = {
    "model": "claude-3-haiku-20240307",
    "temperature": 0.3,
    "max_tokens": 500,
    "cost_per_call": ~$0.0003
}

# Returns (extended format with compatibility fields)
{
    "verdict": "REAL_STARTUP|PARKING|FOR_SALE|COMING_SOON|ESTABLISHED|REDIRECT",
    "confidence": 0.0-1.0,
    "reasoning": "string",
    "suggested_score": 0-100,
    "key_indicators": ["list"],
    "cost_usd": 0.0003,
    # Compatibility fields (from old llm_service)
    "is_legitimate_startup": True/False,
    "category": "AI/ML",
    "red_flags": [],
    "positive_signals": []
}

# Key methods:
await evaluator.evaluate_domain(domain, validation, agent_score)
await evaluator.analyze_content_for_enrichment(domain, title, desc, content)
evaluator.should_use_llm(score, is_parking, is_for_sale)
evaluator.get_status()  # For API endpoints
evaluator.is_available()  # Check if API key set
```

### DEPRECATED: llm_service.py
**DO NOT USE** `services/llm_service.py` directly. It has been superseded by the unified `llm_evaluator.py`.
The `llm_service` alias in `llm_evaluator.py` provides backward compatibility.

### AUTO_RETRAIN
```python
# File: auto_retrain.py
TRIGGERS = {
    "min_examples": 5,      # Retrain after 5 LLM evaluations
    "max_days": 7,          # Force retrain after 7 days
    "min_confidence": 0.7   # Only save high-confidence as training
}
# Run: nohup python3 auto_retrain.py --monitor --interval 3600 &
```

### FEEDBACK_SYSTEM
```python
# File: feedback_system.py
# LLM evaluations auto-saved as training data
feedback_system.add_llm_feedback(domain, llm_result, agent_score, auto_validate=True)
stats = feedback_system.get_llm_statistics(days=30)
```

---

## MCP_INTEGRATIONS

### BRAVE_SEARCH
```python
# File: services/mcp_services.py
# Requires: BRAVE_SEARCH_API_KEY in .env
# Free tier: 2000 requests/month
# Used by: Discovery Agent, Investigator Agent
```

### PLAYWRIGHT
```python
# File: services/mcp_services.py
# Used by: Enrichment Agent for page structure extraction
# No API key required (local)
```

---

## FILE_STRUCTURE

### KEY_FILES
```
backend/
  agents/
    planner.py           # Scheduling
    discovery.py         # Multi-source discovery
    validation.py        # HTTP/DNS/SSL validation
    investigator.py      # Deep investigation
    enrichment.py        # Screenshots, SEO
    scoring.py           # Component scoring
    hybrid_scorer.py     # Rule-based + LLM routing
    implementer.py       # Orchestration
  services/
    llm_evaluator.py     # Claude API integration
    mcp_services.py      # Brave Search, Playwright
    whois_service.py     # Domain age lookup
    multi_ct_logs.py     # CT log discovery
    dns_discovery.py     # DNS pattern discovery
    domain_check.py      # HTTP validation
    screenshot_service.py # Playwright screenshots
    s3_service.py        # Screenshot storage
  config/
    settings.py          # Pydantic settings
    indicators.py        # Parking/for-sale patterns
  models/
    domain.py            # SQLAlchemy models
    schemas.py           # Pydantic schemas
  feedback_system.py     # Training data collection
  auto_retrain.py        # Continuous improvement
  llm_config.py          # LLM configuration
  training_data.json     # Base training dataset
  aidomains.db           # SQLite database
```

### CONFIG_FILES
```
.env                     # Environment variables
  DATABASE_URL           # SQLite connection
  ANTHROPIC_API_KEY      # Claude API
  BRAVE_SEARCH_API_KEY   # Brave Search API
  LLM_SCORING_MODE       # aggressive|moderate|conservative
  SCREENSHOT_ENABLED     # true|false
  AWS_ACCESS_KEY_ID      # S3 screenshots
  AWS_SECRET_ACCESS_KEY  # S3 screenshots
```

---

## DATABASE_SCHEMA

### DOMAINS_TABLE
```sql
-- Key columns
domain VARCHAR(255) UNIQUE NOT NULL
discovered_at TIMESTAMP
status VARCHAR(50)  -- pending, live, parking, for_sale, coming_soon
category VARCHAR(100)
quality_score INTEGER
is_live BOOLEAN
is_parking BOOLEAN
is_for_sale BOOLEAN

-- Penalty detection
is_redirect BOOLEAN
final_url TEXT
redirect_target TEXT
domain_age_days INTEGER
domain_created_date DATE
parent_company VARCHAR(255)
company_founded_year INTEGER
is_established_company BOOLEAN

-- LLM evaluation
llm_category VARCHAR(100)
llm_confidence FLOAT
llm_is_legitimate BOOLEAN
llm_reasoning TEXT
llm_cost_usd FLOAT

-- Investigation
tech_stack JSONB
social_media JSONB
company_info JSONB

-- Enrichment
screenshot_url VARCHAR(500)
visual_analysis JSONB
```

---

## API_ENDPOINTS

### CORE_ROUTES
```
POST /api/discover/daily     # Trigger discovery run
GET  /api/domains/today      # Today's discoveries
GET  /api/domains/{id}       # Domain details
GET  /api/stats/today        # Today's statistics
POST /api/validate/{domain}  # Validate specific domain
GET  /api/reports/today      # Daily report
```

---

## EXECUTION

### START_BACKEND
```bash
cd /home/umichleg/ai-domain-discovery/backend
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### RUN_DISCOVERY
```bash
python3 daily_discovery.py
# Or via API:
curl -X POST http://localhost:8000/api/discover/daily
```

### CHECK_AUTO_RETRAIN
```bash
ps aux | grep auto_retrain
tail -f logs/auto_retrain.log
```

---

## VALIDATION_INDICATORS

### LOCATION
```
backend/config/indicators.py
```

### PARKING_INDICATORS
```python
# ~40 patterns including:
"domain registered on", "domain for sale", "coming soon",
"under construction", "parked domain", "buy this domain",
"welcome to nginx", "apache default page", "lorem ipsum"
```

### FOR_SALE_INDICATORS
```python
# ~50 patterns including:
"buy this domain", "make an offer", "domain for sale",
"porkbun marketplace", "sedo.com", "godaddy auctions",
"parked by", "price upon request"
```

---

## TECH_STACK

```yaml
backend:
  language: Python 3.11+
  framework: FastAPI
  async: asyncio + httpx
  database: SQLite (SQLAlchemy 2.0 async)
  llm: Anthropic Claude API
  screenshots: Playwright

frontend:
  framework: React 18 + TypeScript
  build: Vite
  styling: TailwindCSS
  http: axios

deployment:
  containers: Docker + Docker Compose
  server: Uvicorn
```

---

## COMMON_TASKS

### ADD_NEW_PARKING_PATTERN
```python
# Edit: config/indicators.py
# Add to PARKING_INDICATORS or FOR_SALE_INDICATORS list
```

### CHANGE_LLM_MODE
```bash
# Edit .env
LLM_SCORING_MODE=aggressive  # or conservative, moderate
```

### CHECK_LLM_COSTS
```python
from feedback_system import FeedbackSystem
fs = FeedbackSystem()
stats = fs.get_llm_statistics(days=30)
print(f"Total cost: ${stats['total_cost_usd']:.4f}")
```

### FORCE_RETRAIN
```bash
python3 auto_retrain.py --force
```

### FORCE_LLM_EVAL (Dec 2025)
Evaluates existing live domains with LLM (for domains that were scored before LLM was configured):
```bash
# SSH to EC2 and run:
ssh ubuntu@3.236.14.219
cd ~/ai-domain-discovery/docker

# Run LLM evaluation on 5 live domains at a time
sudo docker-compose exec -T backend python3 /app/force_llm_eval.py

# Requires psycopg2-binary (install if missing):
sudo docker-compose exec -T backend pip install psycopg2-binary
```

**Note:** The `force_llm_eval.py` script uses PostgreSQL directly (not SQLite). It was fixed Dec 2025 to use the correct database URL.

---

## TROUBLESHOOTING

### LLM_NOT_AVAILABLE
```bash
grep ANTHROPIC_API_KEY .env
python3 -c "from services.llm_evaluator import LLMEvaluator; print(LLMEvaluator().is_available())"
```

### LLM_ZERO_EVALUATIONS_FIX
If LLM shows 0 evaluations and Anthropic console shows $0:

#### Critical Checklist (CHECK IN ORDER):
1. **Is `anthropic` package installed?** (MOST COMMON ISSUE!)
   ```bash
   docker exec docker_backend_1 pip list | grep anthropic
   # Must show: anthropic  X.X.X
   # If MISSING, add to requirements.txt and rebuild Docker!
   ```

2. **Is ANTHROPIC_API_KEY set?**
   ```bash
   docker exec docker_backend_1 python3 -c "import os; print(bool(os.getenv('ANTHROPIC_API_KEY')))"
   # Must return: True
   ```

3. **Test API directly:**
   ```bash
   docker exec docker_backend_1 python3 -c "
   import os, anthropic
   client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
   msg = client.messages.create(model='claude-3-haiku-20240307', max_tokens=10, messages=[{'role':'user','content':'Hi'}])
   print('SUCCESS:', msg.content[0].text)
   "
   ```

4. **Are discovery runs happening?**
   ```bash
   # Check recent runs
   docker exec docker_backend_1 python3 -c "
   from sqlalchemy import create_engine, text
   e = create_engine('sqlite:///aidomains.db')
   with e.connect() as c:
       for r in c.execute(text('SELECT run_at, status, domains_new FROM discovery_runs ORDER BY run_at DESC LIMIT 5')):
           print(r)
   "
   ```

5. **LLM only evaluates NEW domains!**
   - If `domains_new = 0` in all runs, no LLM calls happen
   - LLM is NOT called for duplicate/existing domains
   - This is why Anthropic console shows $0 - no NEW domains found

6. **Is LLM scoring mode set correctly?** (CRITICAL!)
   ```bash
   # Check LLM status - must show min:0, max:100 for aggressive
   curl -s https://api.carya-domain-overlord.win/api/llm/status | python3 -m json.tool
   # If showing min:40, max:70 - llm_service.py wasn't updated!
   ```

7. **Are LLM columns in database?** (CRITICAL!)
   ```bash
   # Check if LLM columns exist
   docker exec docker_backend_1 python3 -c "
   from sqlalchemy import create_engine, text
   e = create_engine('sqlite:///aidomains.db')
   with e.connect() as c:
       result = c.execute(text('PRAGMA table_info(domains)'))
       cols = [r[1] for r in result if 'llm' in r[1].lower()]
       print(f'LLM columns: {len(cols)}')
       if len(cols) < 10:
           print('ERROR: Missing LLM columns! Run migration below.')
   "
   ```

#### Root Causes (Common Pitfalls):
| Issue | Symptom | Fix |
|-------|---------|-----|
| `anthropic` not in requirements.txt | Import error, no LLM calls | Add `anthropic>=0.18.0` to requirements.txt, rebuild Docker |
| API key not set | `ANTHROPIC_API_KEY` undefined | Add to backend/.env |
| No NEW domains | `domains_new=0` in all runs | Normal - wait for genuinely new .ai registrations |
| Cron not running | No runs since container restart | Check `crontab -l` and container name matches |
| **llm_service.py hardcoded range** | API shows 40-70, setting ignored | Fixed Dec 2025 - llm_service.py now reads `settings.llm_scoring_mode` |
| Score 15 domains skip LLM | Only 40-70 get LLM in conservative | Set `LLM_SCORING_MODE=aggressive` in .env, restart backend |
| Wrong container name | Cron fails silently | Ensure cron uses `docker_backend_1` |
| **DATABASE MISSING LLM COLUMNS** | LLM runs but nothing saved, `llm_evaluated_at` error | Run migration script below |

#### Database Migration for LLM Columns:
If LLM columns are missing, run this to add them:
```bash
docker exec docker_backend_1 python3 -c "
from sqlalchemy import create_engine, text
columns = [
    ('llm_evaluated_at', 'DATETIME'),
    ('llm_category', 'VARCHAR(100)'),
    ('llm_subcategory', 'VARCHAR(100)'),
    ('llm_business_model', 'VARCHAR(100)'),
    ('llm_target_audience', 'VARCHAR(255)'),
    ('llm_product_description', 'TEXT'),
    ('llm_quality_assessment', 'VARCHAR(50)'),
    ('llm_is_legitimate', 'BOOLEAN'),
    ('llm_confidence', 'FLOAT'),
    ('llm_suggested_score', 'INTEGER'),
    ('llm_red_flags', 'JSON'),
    ('llm_positive_signals', 'JSON'),
    ('llm_reasoning', 'TEXT'),
    ('llm_cost_usd', 'FLOAT'),
    ('domain_age_days', 'INTEGER'),
]
e = create_engine('sqlite:///aidomains.db')
with e.connect() as c:
    for col, typ in columns:
        try:
            c.execute(text(f'ALTER TABLE domains ADD COLUMN {col} {typ}'))
            c.commit()
            print(f'Added: {col}')
        except: pass
print('Migration complete!')
"
```

#### LLM Scoring Modes:
```python
# In config/settings.py:
llm_scoring_mode: str = "aggressive"  # DEFAULT - ALL live domains (0-100)
# Alternative modes:
# "moderate" - scores 35-75 only
# "conservative" - scores 40-70 only
```

### SCHEDULER_NOT_RUNNING
If scheduled discovery runs stopped:

1. **After Docker restart, container names can change**
   ```bash
   # Check actual container name
   docker ps --format '{{.Names}}' | grep backend
   # Must output: docker_backend_1
   ```

2. **Verify cron job uses correct container name**
   ```bash
   crontab -l
   # Must reference: docker_backend_1
   ```

3. **Test manual run**
   ```bash
   docker exec docker_backend_1 python3 /app/daily_discovery.py
   ```

4. **Check cron log**
   ```bash
   cat /tmp/discovery_cron.log
   ```

### WHOIS_FAILURES
WHOIS is async-wrapped with `asyncio.to_thread()`. If failures occur, domain proceeds without age check (conservative approach).

### HIGH_PARKING_RATE
Check CT log patterns and for-sale indicators in `config/indicators.py`.

### API_INTERNAL_SERVER_ERROR (500)
If API endpoints return "Internal Server Error":

#### Check 1: Datetime Timezone Mismatch (MOST COMMON!)
```bash
# Check backend logs for this error:
ssh ubuntu@3.236.14.219 "cd ~/ai-domain-discovery/docker && sudo docker-compose logs --tail=50 backend 2>&1 | grep -i 'offset-naive\|offset-aware'"
```

If you see `can't subtract offset-naive and offset-aware datetimes`:
- **Problem**: Code uses `datetime.now(timezone.utc)` but PostgreSQL stores naive timestamps
- **Fix**: Change all database query datetimes to `datetime.utcnow()`
- **File**: `backend/api/routes.py`
- **After fix**: Sync to EC2 and restart backend:
  ```bash
  rsync -avz backend/api/routes.py ubuntu@3.236.14.219:~/ai-domain-discovery/backend/api/
  ssh ubuntu@3.236.14.219 "cd ~/ai-domain-discovery/docker && sudo docker-compose restart backend"
  ```

#### Check 2: Database Connection Issues
```bash
# Check if PostgreSQL is running
ssh ubuntu@3.236.14.219 "docker ps | grep db"
# Check database logs
ssh ubuntu@3.236.14.219 "cd ~/ai-domain-discovery/docker && sudo docker-compose logs --tail=20 db"
```

#### Check 3: Missing Dependencies
```bash
# Check for import errors
ssh ubuntu@3.236.14.219 "cd ~/ai-domain-discovery/docker && sudo docker-compose logs --tail=100 backend 2>&1 | grep -i 'import\|module'"
```

### FRONTEND_DEMO_MODE_FIX
If the frontend shows "DEMO MODE" or "Displaying sample data. Backend API not responding or returned empty data":

#### Step 0: Check if API Returns Data (CHECK THIS FIRST!)
```bash
# 1. Check health endpoint
curl -s "https://api.carya-domain-overlord.win/api/health"
# Should return: {"status":"healthy",...}

# 2. Check domains endpoint (THIS IS THE KEY TEST!)
curl -s "https://api.carya-domain-overlord.win/api/domains?limit=3"
# Should return: JSON array of domains
# If returns "Internal Server Error" → See API_INTERNAL_SERVER_ERROR section above!
```

**Root Causes for Demo Mode**:
| Symptom | Cause | Fix |
|---------|-------|-----|
| Health OK but `/api/domains` returns 500 | Datetime timezone mismatch | See API_INTERNAL_SERVER_ERROR above |
| Both endpoints fail | Backend down or tunnel broken | Restart backend container |
| API works in curl but not in browser | CORS issue | Check ALLOWED_ORIGINS in .env |
| API works, frontend still shows demo | Stale JS bundle | Rebuild and redeploy frontend |

#### Step 1: Check local `.env` file (`frontend/.env`):
```bash
cat frontend/.env
# Must contain:
VITE_API_URL=https://api.carya-domain-overlord.win
```

#### Step 2: Link to CORRECT Vercel Project
```bash
cd frontend

# Check current project
cat .vercel/project.json
# Must show: "projectName":"carya-ai-domain-discovery"

# If wrong project, relink:
rm -rf .vercel
vercel link --project carya-ai-domain-discovery --yes
```

**CRITICAL**: There are multiple Vercel projects. The correct one is `carya-ai-domain-discovery`, NOT `frontend`.

#### Step 3: Rebuild and Redeploy
```bash
cd frontend
rm -rf dist && npm run build
vercel --prod --force --yes
```

#### Step 4: Verify Deployment
```bash
# Check the deployed JS bundle has correct API URL
curl -s "https://carya-ai-domain-discovery.vercel.app/" | grep -o 'index-[^"]*\.js'
# Get the JS filename, then:
curl -s "https://carya-ai-domain-discovery.vercel.app/assets/<JS_FILENAME>" | grep -o 'api.carya-domain-overlord.win'
# Should output: api.carya-domain-overlord.win
```

#### Root Causes (Common Issues):
1. **Vite Build-Time Baking**: `VITE_API_URL` is baked into JS at build time. Changing Vercel env var ALONE doesn't work - must rebuild!
2. **Wrong Vercel Project**: Deploying to `frontend` instead of `carya-ai-domain-discovery` - site won't update
3. **EC2 IP Changed**: If EC2 was stopped/started, IP changes (unless using Elastic IP). Cloudflare tunnel handles this automatically.
4. **Stale Cache**: Use `--force` flag to skip Vercel build cache

### EC2_IP_CHANGE_FIX
If EC2 IP has changed (check AWS Console):

1. **Cloudflare Tunnel** should still work - it routes to EC2 automatically
2. **If tunnel not working**, SSH to EC2 and restart cloudflared:
   ```bash
   ssh -i "<REDACTED_KEY_PATH>" ubuntu@<NEW_EC2_IP>
   # On EC2:
   sudo systemctl restart cloudflared
   ```
3. **Update local documentation** with new IP:
   - `DEPLOYMENT_GUIDE.md`
   - `SYSTEM_STATE.md`
   - `backend/.env` (ALLOWED_ORIGINS)

**Recommendation**: Allocate an Elastic IP in AWS to prevent IP changes:
- EC2 → Elastic IPs → Allocate → Associate with your instance

---

## PROJECT_FILES
Essential documentation files:
- `ARCHITECTURE.md` - System architecture and troubleshooting (THIS FILE)
- `DEPLOYMENT_GUIDE.md` - Deployment and operations guide
- `SYSTEM_STATE.md` - Current system state
- `README.md` - Project overview
- `frontend/README.md` - Frontend setup
- `QUICK_START.md` - Quick reference guide
