# Security Remediation Matrix

Date: 2026-03-06
Scope: `AndrewGreenbaum` account scan (pattern-based)

| Repo | Finding | Severity | Action |
|---|---|---|---|
| ai-domain-discovery | Exposed Anthropic key in docs history (`DEPLOYMENT_GUIDE.md`, `SYSTEM_STATE.md`) | Critical | Key rotation required, content sanitized, history rewrite required |
| ai-domain-discovery | Operationally sensitive host/key-path references in docs (`<REDACTED_KEY_FILE>`, fixed host/IP instructions) | High | Removed from current docs; rewrite history to purge prior commits |
| carya-eagle-eye | `.env` files in repo with non-secret config values | Low | Retained with placeholder hygiene recommendation |
| bud-tracker/carya-eagle-eye | Pattern hits for `OPENAI_API_KEY` references in config/docs without direct key value | Low | No active key literal found in scanned hits |
| dotfiles | No high-confidence secret hit in scanned files | Info | No immediate action |

## Verification Commands

```bash
# post-rewrite checks
rg -n "SENSITIVE_PATTERN_SET"
git log --all -S "REDACTED_PATTERN" --oneline
git grep -n "REDACTED_PATTERN" $(git rev-list --all)
```
