# Jaffle Shop (dbt on Databricks)

A Databricks-flavoured port of the canonical [Jaffle Shop](https://github.com/dbt-labs/jaffle-shop-classic) project, used as the first lab in this repo. It demonstrates a complete staging-to-marts dbt build against Unity Catalog using `dbt-databricks` and a SQL Warehouse.

## Project layout

```text
jaffle_shop/
├── dbt_project.yml         # project config: name, profile, paths, materializations
├── packages.yml            # dbt_utils, dbt_date
├── package-lock.yml
├── requirements.txt        # dbt-databricks>=1.8.0,<2.0.0
├── profiles.yml.example    # env-var driven profile template (copy to profiles.yml)
├── .env.template           # workspace credentials template (copy to .env)
├── macros/
│   ├── cents_to_dollars.sql      # adapter-dispatched currency macro
│   └── generate_schema_name.sql  # custom schema naming for seeds vs models
├── models/
│   ├── staging/            # views over raw seed sources (stg_*)
│   └── marts/              # business-facing tables (customers, orders, ...)
├── seeds/
│   └── jaffle-data/        # synthetic raw CSVs loaded with `dbt seed`
├── analyses/               # ad-hoc analyses (placeholder)
├── data-tests/             # singular tests (placeholder)
└── snapshots/              # SCD2 snapshots (placeholder)
```

## Prerequisites

- Databricks workspace with Unity Catalog
- A SQL Warehouse you can query
- A catalog and schema you have `CREATE` privilege on
- Python 3.10+
- A Databricks Personal Access Token (or use SSO via `databricks` CLI)

## Run locally

```bash
cp .env.template .env                 # then edit .env with your real values
cp profiles.yml.example profiles.yml  # uses env vars from .env

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

set -a && source .env && set +a       # export DATABRICKS_* vars

dbt deps
dbt seed --full-refresh --vars '{"load_source_data": true}'
dbt run
dbt test
```

`profiles.yml`, `.env`, and the generated `target/`, `logs/`, `dbt_packages/` are all gitignored. Never commit them.

## Models

### Staging (`models/staging/`)

Views over the raw seed tables defined in [`__sources.yml`](models/staging/__sources.yml) (source name `ecom`, schema `raw`):

| Source table | Staging model |
|--------------|---------------|
| `raw_customers` | `stg_customers` |
| `raw_orders` | `stg_orders` |
| `raw_items` | `stg_order_items` |
| `raw_stores` | `stg_locations` |
| `raw_products` | `stg_products` |
| `raw_supplies` | `stg_supplies` |

### Marts (`models/marts/`)

Tables that join staging models into business-facing entities: `customers`, `orders`, `order_items`, `products`, `locations`, `supplies`, plus a `metricflow_time_spine`.

## Schema strategy

`macros/generate_schema_name.sql` overrides dbt's default behaviour:

- Seeds (with `+schema: raw` in `dbt_project.yml`) land in a globally named `raw` schema.
- Non-prod targets keep all models in the profile's default schema (no per-folder suffixes).
- Prod targets prefix the default schema name to any custom schema (`{default}_{custom}`).

This keeps developer schemas isolated while production keeps clean per-domain schemas.

## Deploy as a Lakeflow Job

See the repo-root [README.md](../README.md) and [local_deployment/README.md](../local_deployment/README.md) for the DAB bundle pattern. The bundle file is workspace-specific and gitignored at the repo root.

## Credits

Based on the [Jaffle Shop Classic](https://github.com/dbt-labs/jaffle-shop-classic) project by dbt Labs (Apache 2.0). Synthetic Jaffle Shop seed data is reused under that license.
