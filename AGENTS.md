# AGENTS.md

## Context
Before substantive work, read `PROJECT_CONTEXT.md`.

For code, data processing, analytical logic, schemas, dependencies,
architecture or reproducible outputs, also read `.agents/rules.md`.

Read `PIPELINE.md` only when the task affects pipeline logic, stages,
dependencies, execution, transformations, data contracts or related
architecture; read the relevant sections, not the whole file, unless
the task requires it. Not needed for changes unrelated to the pipeline.

Inspect only files relevant to the task; do not recursively read the repo.

## Critical invariants
- Never link Urgencias and Egresos at patient level.
- Preserve their different granularities; relationships are ecological/territorial only.
- No real-time bed/capacity management.
- Do not reduce the product to a descriptive dashboard.
- Do not invent, silently correct or impute data without reproducible evidence.

## Completion
Run tests proportional to scope and risk (policy in `.agents/rules.md`):
directly related tests; broader or full suite for shared components,
contracts, dependencies or wide impact. Do not claim full validation
after partial runs; report any necessary test that could not run.
Report:
- changes;
- validation;
- failures/blockers;
- Git status.

Do not create planning artifacts unless requested.