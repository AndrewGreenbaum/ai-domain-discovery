# Architecture

## Overview

The system discovers candidate domains, validates them, scores them, and exposes results through an API and frontend.

## Pipeline

1. Discovery
2. Validation
3. Enrichment
4. Scoring
5. Persistence
6. API serving

## Design Constraints

- Discovery throughput is bounded by external source limits.
- Validation must degrade safely when third-party lookups fail.
- Scoring decisions must be explainable and auditable.

## Security Requirements

- No hardcoded secrets in source or docs.
- Environment-driven credentials only.
- Automated secret scanning in CI and pre-commit.
- Credential rotation runbook maintained in `DEPLOYMENT_GUIDE.md`.

## Reliability

- Scheduler retries transient failures.
- Long-running tasks are bounded with timeouts.
- Logging captures structured execution and error context.
