# Deployment Guide

Last updated: 2026-03-06

This guide documents a secure deployment pattern without embedding credentials, private key paths, or fixed infrastructure identifiers.

## Principles

- Never commit secrets, tokens, private keys, or machine-local paths.
- Keep runtime credentials in secret managers or environment configuration only.
- Treat docs as public unless the repository is guaranteed private and access-controlled.

## Required Runtime Variables

Set these in your deployment environment (not in git):

```bash
DATABASE_URL=<SET_IN_ENV>
ANTHROPIC_API_KEY=<SET_IN_ENV>
OPENAI_API_KEY=<SET_IN_ENV>
ALLOWED_ORIGINS=<SET_IN_ENV>
```

Optional variables:

```bash
BRAVE_SEARCH_API_KEY=<SET_IN_ENV>
AWS_ACCESS_KEY_ID=<SET_IN_ENV>
AWS_SECRET_ACCESS_KEY=<SET_IN_ENV>
AWS_S3_BUCKET=<SET_IN_ENV>
```

## Deployment Steps

1. Build and deploy backend using your platform pipeline.
2. Build and deploy frontend with environment-specific API base URL.
3. Validate health endpoint and one read endpoint.
4. Confirm logs show no startup secret errors.

## Rotation Procedure

When a secret is exposed:

1. Revoke old credential immediately.
2. Generate replacement credential.
3. Update secret stores.
4. Redeploy services.
5. Verify old key fails and new key succeeds.

## Verification Checklist

- No secrets in repo files (`rg -n "sk-|ghp_|AKIA|PRIVATE KEY"`).
- `.env.example` contains placeholders only.
- CI secret scan passes.
- Branch protections require secret-scan status checks.
