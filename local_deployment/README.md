# Local Deployment (Gitignored)

**Everything in this folder except this README is gitignored.** This is intentional.

This folder holds workspace-specific deployment configuration -- workspace URLs, CLI profiles, catalog/schema names, warehouse IDs, email notifications, and DAB bundle settings that are unique to your environment. None of it belongs in a public repository.

## Why This Folder Exists

The dbt project, models, seeds, macros, and tests in this repo are designed to be portable across any Databricks workspace. To actually deploy and run them as a Lakeflow Job, you need environment-specific config (which workspace, which warehouse, which catalog, which email gets failure notifications). That config lives here, locally, and never leaves your machine.

## What Goes Here

| File / Folder | Location | Purpose |
|---------------|----------|---------|
| `databricks.yml` | **Repo root** (gitignored) | DAB bundle: workspace host, variables, target config |
| `resources/jaffle_shop_dbt_job.yml` | `local_deployment/resources/` | Optional split-out Lakeflow Job resource definition |
| `instructions_to_use/` | `local_deployment/` | Filled-in instruction copies with your real values |
| Any other `.yml`, `.json`, `.env` | `local_deployment/` | Environment-specific overrides |

## For Other Users of This Repo

If you clone this repo and want to deploy to your own workspace:

1. Create `databricks.yml` at the **repo root** (it's gitignored there).
2. Optionally split job resources into `local_deployment/resources/*.yml` and reference them via `include:`.
3. From the repo root: `databricks bundle validate && databricks bundle deploy && databricks bundle run jaffle_shop_dbt_job`.

### Example `databricks.yml` (placeholders only)

Place this at the **repo root** with your real values substituted in. It is gitignored.

```yaml
bundle:
  name: databricks-dbt-training-labs

variables:
  warehouse_id:
    description: SQL Warehouse ID for dbt execution
    default: "<your-warehouse-id>"
  catalog_name:
    description: Unity Catalog for dbt outputs
    default: "<your-catalog>"

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://<your-workspace>.cloud.databricks.com
      root_path: /Workspace/Users/${workspace.current_user.userName}/.bundle/${bundle.name}/${bundle.target}

resources:
  jobs:
    jaffle_shop_dbt_job:
      name: "[${bundle.target}] Jaffle Shop - dbt Build"
      description: >
        Lakeflow Job to run the Jaffle Shop dbt project.
        Executes dbt deps, seed, run, and test sequentially using the SQL Warehouse.

      environments:
        - environment_key: dbt_env
          spec:
            environment_version: "5"
            dependencies:
              - dbt-databricks>=1.8.0,<2.0.0

      tasks:
        - task_key: dbt_build
          environment_key: dbt_env
          dbt_task:
            source: WORKSPACE
            project_directory: jaffle_shop
            commands:
              - "dbt deps"
              - "dbt seed --full-refresh --vars '{\"load_source_data\": true}'"
              - "dbt run"
              - "dbt test"
            warehouse_id: ${var.warehouse_id}
            catalog: ${var.catalog_name}
            schema: jaffle_shop

      email_notifications:
        on_failure:
          - "<your-email>"
```

### Optional: split the job resource into its own file

If you'd rather keep the bundle config slim, move the `resources:` block into `local_deployment/resources/jaffle_shop_dbt_job.yml` and add this to the root `databricks.yml`:

```yaml
include:
  - local_deployment/resources/*.yml
```

Both files are gitignored.
