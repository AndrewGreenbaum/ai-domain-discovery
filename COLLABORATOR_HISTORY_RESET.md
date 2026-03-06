# Collaborator History Reset Instructions

This repository history was rewritten to remove exposed secret material.

## If you have a local clone

Option A (recommended):
```bash
mv ai-domain-discovery ai-domain-discovery-old
git clone https://github.com/AndrewGreenbaum/ai-domain-discovery.git
```

Option B (hard reset existing clone):
```bash
git fetch origin --prune
git checkout main
git reset --hard origin/main
git clean -fd
```

## Important

- Do not merge old local branches without inspecting for leaked content.
- Re-run secret scanning before opening PRs from old branches.
