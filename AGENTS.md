# AGENTS.md

## Project

Capstone APT: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana.

The repository implements a reproducible analytical platform for:

1. 4–8 week mental-health emergency demand forecasting;
2. territorial accessibility analysis;
3. F00–F99 hospitalization length-of-stay analysis;
4. integration through a web/API product.

Do not implement real-time bed/capacity management.
Do not reduce the product to a descriptive-only dashboard.

## Context

Before substantive work, inspect `PROJECT_CONTEXT.md`.

For tasks that modify code, data processing, analytical logic, architecture, schemas, dependencies or reproducible outputs, read `.agents/rules.md`.

Read `PIPELINE.md` only when the task creates/modifies executable pipeline logic, stages, inputs, outputs or DAG dependencies.

Do not recursively read the repository by default. Inspect only files relevant to the task.

## Critical domain rules

- Never link Urgencias and Egresos at patient level.
- Any relationship between both sources must be ecological/territorial.
- Preserve their different granularities.
- Do not infer hospital location from patient residence fields.
- Never invent, silently correct or impute data without reproducible justification.

## Engineering rules

- No hardcoded personal paths, mutable years, secrets or machine-specific state.
- Code must work after another team member clones/pulls the repository.
- Use relative or dynamically derived paths.
- Permanent dependencies must be declared.
- Permanent data-processing logic must belong to the official reproducible pipeline when applicable.
- Do not place indispensable logic in `scratch/`.
- Prefer extending existing modules over duplicating logic.

## Validation

For code changes, run the relevant tests.

Before considering a substantive code task complete, unless the task clearly does not require it:

```text
python scripts/run_pipeline.py --help
pytest tests/
git status --short
```

Report concisely:
- files changed;
- validation performed;
- failures or limitations;
- relevant Git status.

Do not create planning artifacts such as `task.md`, `implementation_plan.md` or `walkthrough.md` unless explicitly requested.