# Coding Standards

## General Rules

- Do not put emojis in SQL, Python, YAML, or general code files.
- Do not hallucinate. If you are unsure about an API, SDK method, or behavior, say so.
- **Always ask before committing.** Never `git commit` or `git push` without explicit user approval.
- Never make architecture changes without asking the user first.
- Always try programmatic approaches (Databricks SDK, REST API, CLI, DAB resources) before suggesting manual UI steps.

## dbt on Databricks

- Always reference upstream models with `ref()` and raw inputs with `source()`. Never hardcode catalog or schema names inside model SQL.
- Declare materializations in `dbt_project.yml`, not as ad-hoc `{{ config(...) }}` blocks unless a per-model override is genuinely needed.
- Schema, freshness, and data tests live in `*.yml` files alongside the models or sources they describe.
- Use `dbt-databricks>=1.8.0,<2.0.0` and target Unity Catalog (catalog + schema in the profile or DAB variables).
- Prefer SQL Warehouses for production runs; reserve interactive clusters for ad-hoc dev.
- For deployment, prefer Databricks Asset Bundles (`databricks.yml` + `resources/*.yml`) over hand-crafted Jobs UI configuration.

## Secrets and Local Config

- Never commit `profiles.yml`, `.env`, `databricks.yml`, or any file under `local_deployment/` other than the README.
- Use env-var-driven `profiles.yml` (jinja `env_var(...)`) sourced from a local `.env`.
- For DAB deployments, keep workspace host, warehouse id, catalog, and email notifications in the **gitignored** root `databricks.yml`. Use the placeholder example in [local_deployment/README.md](../../local_deployment/README.md).

## Documentation

- Keep documentation concise. Consolidate rather than scatter across many files.
- The root `README.md` is the primary user-facing document. Keep it comprehensive but scannable.
- Each lab project gets its own `README.md` for project-specific guidance.

## Code Quality

- Read existing code before editing.
- Fix linter errors you introduce.
- Do not add comments that just narrate what the code does.
