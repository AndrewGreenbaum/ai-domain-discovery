# Engineering Decisions (AI Domain Discovery)

## 1) Stage-gated pipeline (discovery -> validation -> scoring)
I split the flow so each stage can fail independently and be debugged quickly.
Tradeoff: more orchestration code.

## 2) Rule-first quality filtering before expensive analysis
I use deterministic checks early to reduce junk domains and control runtime/cost.
Tradeoff: edge startups can be filtered out too aggressively.

## 3) API-first access to run outputs
I exposed results through API routes so tooling and dashboards stay decoupled from pipeline internals.
Tradeoff: schema evolution needs discipline.

## 4) Scheduler + manual run paths
Both are supported so production runs are automated but debugging remains fast.
Tradeoff: two invocation paths to maintain.

## 5) Security-safe operations docs
I removed machine-local paths and literal credentials from docs after incident response.
Tradeoff: onboarding requires secret-manager familiarity.
