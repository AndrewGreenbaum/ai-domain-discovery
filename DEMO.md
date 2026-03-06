# Demo Script (AI Domain Discovery)

## Goal
Show the full value chain in ~8 minutes: noisy domain source -> filtered actionable output.

## Demo Flow

1. Problem + constraint (1 minute)
- Explain CT log noise and why precision matters.

2. Architecture walk-through (2 minutes)
- Discovery, validation, scoring, API serving.
- Point to exact backend folders/services.

3. Run path (2 minutes)
```bash
cd backend
python3 main.py
# in another shell
curl http://localhost:8000/api/health
```

4. Quality controls (2 minutes)
- Show parked/for-sale filtering logic.
- Explain why these checks run before deep analysis.

5. Tests + limits (1 minute)
Prerequisites: Python 3.11+ and backend dependencies installed.
```bash
cd backend
python3 -m pytest tests -q
```
- Close with known limitations and planned improvements.

## Interview Talking Points

- Biggest tradeoff: strict filtering vs potential missed startups.
- Hardest bug class: upstream source instability / timeout handling.
- What I’d improve with more time: better source weighting + outcome feedback loop.
