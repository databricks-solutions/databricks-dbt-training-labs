# Local Deployment (Gitignored)

**Everything in this folder except this README is gitignored.** This is intentional.

This folder holds workspace-specific deployment configuration -- workspace URLs, CLI profiles,
catalog/schema names, warehouse IDs, email notifications, and the DAB job definitions that are unique
to your environment. None of it belongs in a public repository.

## Why This Folder Exists

The dbt projects, models, seeds, macros, and tests in this repo are designed to be portable across
any Databricks workspace. To actually deploy and run them as Lakeflow Jobs, you need
environment-specific config (which workspace, which warehouse, which catalog, which email gets
failure notifications). That config lives here, locally, and never leaves your machine.

## Layout

The bundle is split so each deployable unit is its own file, pulled together by `include:` in a thin
root `databricks.yml`:

| File | Location | Tracked? | Purpose |
|------|----------|----------|---------|
| `databricks.yml` | **Repo root** | Gitignored | Thin bundle: name, `include:`, variables, target config |
| `resources/jaffle_shop_dbt_job.yml` | `local_deployment/resources/` | Gitignored | Lab 01 job: seed + run + test |
| `resources/module_03_seed_job.yml` | `local_deployment/resources/` | Gitignored | Module 3 **shared** seed job (run once per workspace) |
| `resources/module_03_gold_job.yml` | `local_deployment/resources/` | Gitignored | Module 3 Lab 3.5 (gold) build job |
| `resources/module_03_incremental_job.yml` | `local_deployment/resources/` | Gitignored | Module 3 Lab 3.6 (incremental) build job |

### Why jobs are split this way

- **One file per deployable unit**, so the bundle stays reviewable and you can deploy/run one lab at
  a time.
- **Lab 01 (`jaffle_shop`) stays a single job** because it is self-contained — it seeds and builds
  into the same `jaffle_shop` schema with no shared/per-dev split.
- **Module 3 separates seed from build.** `dbt seed` writes the *shared*, globally named `silver`
  schema — one load serves the whole workspace. The gold/incremental builds are *per-developer* and
  write to your own schema. Mixing them in one job would re-seed the shared schema on every personal
  build, so `module_03_seed_job` is deliberately its own job you run once (or when the seed data
  changes), while the per-lab build jobs read that silver via `source()`.

## Deploying to your own workspace

1. Create `databricks.yml` at the **repo root** (gitignored there) — see the example below.
2. Create `local_deployment/resources/*.yml` for the jobs you want — see the examples below.
3. Authenticate the CLI (see the top-level [README](../README.md#optional-deploy-as-a-lakeflow-job-via-dab)).
4. From the repo root:
   ```bash
   databricks bundle validate --profile <your-profile>
   databricks bundle deploy   --profile <your-profile>

   # Lab 01
   databricks bundle run jaffle_shop_dbt_job        --profile <your-profile>

   # Module 3: seed once, then build a lab
   databricks bundle run module_03_seed_job         --profile <your-profile>
   databricks bundle run module_03_gold_job         --profile <your-profile>
   databricks bundle run module_03_incremental_job  --profile <your-profile>
   ```

### Example root `databricks.yml` (placeholders only)

```yaml
bundle:
  name: databricks-dbt-training-labs

include:
  - local_deployment/resources/*.yml

variables:
  warehouse_id:
    description: SQL Warehouse ID for dbt execution
    default: "<your-warehouse-id>"
  catalog_name:
    description: Unity Catalog for dbt outputs
    default: "<your-catalog>"
  dev_schema:
    description: Per-developer schema for Module 3 gold/incremental builds
    default: "module_03"
  notification_email:
    description: Address that receives job failure notifications
    default: "<your-email>"

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://<your-workspace>.cloud.databricks.com
      root_path: /Workspace/Users/${workspace.current_user.userName}/.bundle/${bundle.name}/${bundle.target}
```

> `dev_schema` is only used by the Module 3 build jobs. Lab 01 hardcodes `schema: jaffle_shop` in its
> job file.

### Example `local_deployment/resources/jaffle_shop_dbt_job.yml` (Lab 01)

```yaml
# jaffle_shop is self-contained: one job seeds, runs, and tests it into the jaffle_shop schema.
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
            project_directory: ../../jaffle_shop
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
          - "${var.notification_email}"
```

### Example `local_deployment/resources/module_03_seed_job.yml`

Run once per workspace to load the shared silver layer:

```yaml
# Loads the silver layer into the globally named `silver` schema. Run once per workspace,
# or when seed data changes — not on every build.
resources:
  jobs:
    module_03_seed_job:
      name: "[${bundle.target}] Module 3 - Seed silver (shared, run once)"
      description: >
        Loads the Module 3 silver layer as seeds into the shared `silver` schema. One run serves the
        whole workspace; the per-lab build jobs read this via source('silver', ...). Re-run only when
        the seed data changes.

      environments:
        - environment_key: dbt_env
          spec:
            environment_version: "5"
            dependencies:
              - dbt-databricks>=1.11.7,<2.0.0

      tasks:
        - task_key: dbt_seed
          environment_key: dbt_env
          dbt_task:
            source: WORKSPACE
            project_directory: ../../module_03
            commands:
              - "dbt deps"
              - "dbt seed --full-refresh"
            warehouse_id: ${var.warehouse_id}
            catalog: ${var.catalog_name}
            # No schema override: seeds are pinned to the global `silver` schema in dbt_project.yml.

      email_notifications:
        on_failure:
          - "${var.notification_email}"
```

### Example `local_deployment/resources/module_03_gold_job.yml` (Lab 3.5)

Requires `module_03_seed_job` to have run once first. Builds into `${var.dev_schema}` (per-developer).

```yaml
# Requires module_03_seed_job to have run once. Builds into var.dev_schema (per-developer).
resources:
  jobs:
    module_03_gold_job:
      name: "[${bundle.target}] Module 3 - Lab 3.5 Gold (partitioning)"
      description: >
        Builds the gold-layer partitioning lab (models + tests) with
        `dbt build --select path:models/gold`. Requires the shared silver seeds (module_03_seed_job).

      environments:
        - environment_key: dbt_env
          spec:
            environment_version: "5"
            dependencies:
              - dbt-databricks>=1.11.7,<2.0.0

      tasks:
        - task_key: dbt_build_gold
          environment_key: dbt_env
          dbt_task:
            source: WORKSPACE
            project_directory: ../../module_03
            commands:
              - "dbt deps"
              - "dbt build --select path:models/gold"
            warehouse_id: ${var.warehouse_id}
            catalog: ${var.catalog_name}
            schema: ${var.dev_schema}

      email_notifications:
        on_failure:
          - "${var.notification_email}"
```

### Example `local_deployment/resources/module_03_incremental_job.yml` (Lab 3.6)

Requires `module_03_seed_job` to have run once first. Runs the lab at full-data state (`--full-refresh`, no `max_order_date` var). The time-simulation and silent-data-loss walkthrough in the lab README are meant to be run interactively from the CLI with `--vars`, not as a scheduled job.

```yaml
# Requires module_03_seed_job to have run once. Full-data build (--full-refresh, no max_order_date).
# Time-simulation steps in the lab README are CLI-only (--vars), not for scheduled runs.
resources:
  jobs:
    module_03_incremental_job:
      name: "[${bundle.target}] Module 3 - Lab 3.6 Incremental (insert_overwrite / MERGE)"
      description: >
        Builds the incremental-models lab (models + tests) with
        `dbt build --select path:models/incremental`. Requires the shared silver seeds
        (module_03_seed_job).

      environments:
        - environment_key: dbt_env
          spec:
            environment_version: "5"
            dependencies:
              - dbt-databricks>=1.11.7,<2.0.0

      tasks:
        - task_key: dbt_build_incremental
          environment_key: dbt_env
          dbt_task:
            source: WORKSPACE
            project_directory: ../../module_03
            commands:
              - "dbt deps"
              - "dbt build --select path:models/incremental --full-refresh"
            warehouse_id: ${var.warehouse_id}
            catalog: ${var.catalog_name}
            schema: ${var.dev_schema}

      email_notifications:
        on_failure:
          - "${var.notification_email}"
```

> **Version pins:** Module 3 jobs require `dbt-databricks>=1.11.7` because the `insert_overwrite`
> labs depend on `REPLACE ON` behaviour. Lab 01's job keeps `>=1.8.0`.
