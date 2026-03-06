# Quick Start

## 1. Clone and bootstrap

```bash
git clone <REPO_URL>
cd ai-domain-discovery
cp .env.example .env
```

## 2. Configure environment

Set real values in `.env` (local only, never commit):

```bash
DATABASE_URL=<SET_IN_ENV>
ANTHROPIC_API_KEY=<SET_IN_ENV>
```

## 3. Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## 4. Validate

- Confirm health endpoint responds.
- Confirm one data endpoint returns expected shape.

## 5. Security baseline

- Run secret scan before push.
- Do not include host-specific private key references in docs.
