# AGENTS.md

## Context
Before substantive work, read `PROJECT_CONTEXT.md`.

For code, data processing, analytical logic, schemas, dependencies,
architecture or reproducible outputs, also read `.agents/rules.md`.

Read `PIPELINE.md` only when changing pipeline logic, stages,
inputs, outputs or DAG dependencies.

Inspect only files relevant to the task; do not recursively read the repo.

## Critical invariants
- Never link Urgencias and Egresos at patient level.
- Preserve their different granularities; relationships are ecological/territorial only.
- No real-time bed/capacity management.
- Do not reduce the product to a descriptive dashboard.
- Do not invent, silently correct or impute data without reproducible evidence.

## Completion
Run task-relevant tests and report:
- changes;
- validation;
- failures/blockers;
- Git status.

Do not create planning artifacts unless requested.