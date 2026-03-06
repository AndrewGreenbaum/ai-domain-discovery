# AI Domain Discovery

Automated pipeline that discovers newly registered `.ai` domains, validates whether they are real products vs parked domains, scores launch quality, and serves results through an API/dashboard.

## What I Built

- Multi-stage backend pipeline: discovery -> validation -> scoring -> persistence.
- FastAPI layer for query/reporting workflows.
- Scheduler-driven runs with retry-aware behavior.
- Security-hardened docs/config flow (no secrets in repo).

## Why This Exists

Certificate logs are noisy. Most domains are not actionable startups. The project focuses on reducing false positives quickly so investigation time goes to likely launches.

## Architecture

- Discovery: pulls candidate domains from CT and related sources.
- Validation: checks DNS/HTTP/SSL + basic content and parked/for-sale heuristics.
- Scoring: weighted quality signal model with guardrails.
- Orchestration: scheduled and manual runs.
- Serving: REST endpoints + lightweight dashboard assets.

## Key Tradeoffs

1. Precision over recall in first-pass scoring:
High early precision prevents analyst fatigue; tradeoff is missing some weak-signal startups.

2. Explicit pipeline stages over one monolith:
Improves debugging and replacement of components; tradeoff is more wiring/config surface.

3. Deterministic rule scaffolding before heavy LLM usage:
Controls cost and makes decisions auditable; tradeoff is slower adaptation to edge patterns.

## Run

### Docker
```bash
cd docker
docker-compose up -d
```

### Local backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python3 main.py
```

## Test

Prerequisites: Python 3.11+, backend dependencies installed from `backend/requirements.txt`.

```bash
cd backend
python3 -m pytest tests -q
```

## Troubleshoot

- API won’t start: verify required env vars in `.env` and dependency install completed.
- No discoveries: run manual discovery and inspect logs from scheduler/discovery services.
- Low-quality output: inspect validation and scoring thresholds before broadening rules.

## Interview Talking Points

- How I balanced false-positive reduction vs missing early startups.
- Why I kept scoring explainable instead of opaque.
- One failure mode (source noise/timeouts) and how I mitigated it.
- What I would change next (better source weighting + richer observability).

## Related Docs

- `DECISIONS.md`
- `BUILD_LOG.md`
- `KNOWN_LIMITATIONS.md`
- `DEMO.md`
- `SECURITY.md`
