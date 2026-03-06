# Security Policy

## Reporting a Vulnerability

Do not open a public issue for active secret exposure.

Report privately with:
- affected file/path
- exposure type
- whether the secret appears active

## Secret Handling Rules

- Never commit API keys, tokens, private keys, or local machine key paths.
- Keep `.env` files local and out of git.
- Use `.env.example` placeholders only.

## Incident Response (Secrets)

1. Revoke exposed secret immediately.
2. Rotate and redeploy.
3. Remove from current branch.
4. Rewrite git history if secret was committed.
5. Validate with automated secret scanning.
