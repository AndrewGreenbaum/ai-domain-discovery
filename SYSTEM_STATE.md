# System State

Last updated: 2026-03-06
Status: Operational

This document intentionally excludes sensitive infrastructure identifiers and credentials.

## Current Capabilities

- Scheduled discovery pipeline
- Validation and scoring pipeline
- API + frontend deployment
- Optional LLM-assisted evaluation

## Operational Notes

- Runtime configuration is provided via environment variables.
- All credentials are expected to be managed outside git.
- Incident response requires immediate credential rotation and history cleanup if leakage occurs.

## Security Posture

- Secret scanning enforced in CI
- Pre-commit secret scan available locally
- Security disclosure instructions in `SECURITY.md`
