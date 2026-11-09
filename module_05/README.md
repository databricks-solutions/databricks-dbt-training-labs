# Module 5: Documentation and Governance with dbt and Unity Catalog

The dbt project behind the Module 5 labs: generating dbt docs, enriching model metadata, controlling
access with Unity Catalog, combining dbt lineage with Unity Catalog lineage, and delivering all of it
reproducibly and auditably.

It is a **repeatable lab boilerplate**: a small, clean Jaffle Shop dataset with one column of personal
data worth protecting, and starter models that carry a one-line description and nothing else. It is
fully self-contained. It does not need Lab 01, Module 3, Module 4, or any earlier output.

| Path | What it is |
|------|-----------|
| [`seeds/`](seeds/) | The fixtures: `customers` (with a synthetic `customer_email`), `products`, `locations`, `orders`, `order_items`. All clean. |
| [`models/staging/`](models/staging/) | Five staging views. Starter YAML: one-line descriptions only. |
| [`models/intermediate/`](models/intermediate/) | `int_customer_orders`, an **ephemeral** model: in the dbt graph, never in Unity Catalog. |
| [`models/marts/`](models/marts/) | `dim_customers` (holds personal data) and `fct_orders` (holds none), both Delta tables. |
| [`models/exposures.yml`](models/exposures.yml) | A dashboard exposure, so the docs graph ends at a consumer. |
| [`macros/`](macros/) | `create_pii_mask_function()`, the Unity Catalog mask function Lab 5.1 wires in. |
| [`analyses/`](analyses/) | SQL that checks each stage in Unity Catalog. Run `dbt compile`, then paste the file from `target/compiled/module_05/analyses/` into the SQL editor. |
| [`scripts/`](scripts/) | `generate_module5_seeds.py`, `doc_coverage.py` and `compare_lineage.py`. |
| [`labs/`](labs/) | The lab guide and its reference solution. See [Lab 5.1](labs/lab_5_1_document_and_govern/README.md). |

## Prerequisites

- A Databricks workspace with Unity Catalog enabled
- A SQL Warehouse (Serverless or Classic) you can query
- A catalog and schema you have `CREATE` privilege on, plus `CREATE FUNCTION` (the mask function) and
  `APPLY TAG` on your tables (Unity Catalog tags)
- Python 3.10+
- A Databricks Personal Access Token (or SSO via the `databricks` CLI)
- Optional, for the lineage and audit steps: `USE CATALOG` on `system`, `USE SCHEMA` on `system.access`,
  and `SELECT` on `system.access.table_lineage`, `system.access.column_lineage` and
  `system.query.history` (metastore admins have them)

## Setup

```bash
cd module_05
cp .env.template .env                 # then edit .env with your real values
cp profiles.yml.example profiles.yml  # reads the env vars from .env

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

set -a && source .env && set +a       # export DATABRICKS_* vars

dbt debug                             # confirm the connection before you build anything
```

`profiles.yml`, `.env`, and the generated `target/`, `logs/`, `dbt_packages/` are gitignored. Never
commit them.

## Build the starter

```bash
dbt build
```

`dbt build` loads the seeds and builds the models in dependency order. There are no tests in this
module, so the build is purely about producing the objects the lab documents and governs.

Everything lands in **your own schema** (`DATABRICKS_SCHEMA` in `.env`). The seeds are tiny, so
reseeding is cheap and nothing is shared between learners.

## What the starter is missing (on purpose)

Run `dbt docs generate` and then `python3 scripts/doc_coverage.py`. The starter documents **0 of 39
columns**, has no tags, no access controls and no audit trail. Lab 5.1 closes every gap:

| Gap in the starter | Lab 5.1 step | What closes it |
|---|---|---|
| No column descriptions | 1 and 2 | descriptions and doc blocks → `dbt docs generate` |
| Docs only on the dbt site | 3 | `persist_docs` → comments in Unity Catalog |
| No ownership or classification | 4 | `meta`, `tags` and `databricks_tags` |
| Anyone can read the email column | 5 | `grants` and a Unity Catalog column mask |
| Two lineage views, never compared | 6 | `compare_lineage.py` and the Lineage tab |
| No record of what ran or why | 7 | pinned dbt versions, run artifacts, `query_tags` |

## Labs

| Lab | Topic | What it covers |
|-----|-------|----------------|
| [**5.1 Document and govern**](labs/lab_5_1_document_and_govern/README.md) | dbt docs, Unity Catalog metadata, access control, lineage, auditable delivery | `dbt docs`, `persist_docs`, doc blocks, `meta`/`tags`/`databricks_tags`, `grants`, a column mask, dbt versus Unity Catalog lineage, query tags |

The lab plugs into the fixtures and starter models above. This repository ships the boilerplate and Lab 5.1.

## Run it as Lakeflow Jobs (optional)

To run the same project as deployed jobs, see [`local_deployment/`](../local_deployment/README.md). Run
`module_05_seed_job` first and then `module_05_build_job`; both write to your own schema.

## Regenerating the seeds

The seeds are produced by a deterministic script, so the output is byte-for-byte identical every run:

```bash
python3 scripts/generate_module5_seeds.py
```

It samples a few customers and their orders from Lab 01's raw Jaffle Shop data (`jaffle_shop/seeds/`),
converts cents to dollars, adds a synthetic `order_status` and a synthetic `customer_email` (always on
the reserved `example.com` domain), and checks that the data is clean. Money loads as `DECIMAL(16,2)`
and dates as `DATE` (see [`seeds/_seed_properties.yml`](seeds/_seed_properties.yml)).

## Validated configuration

Run end to end on a Serverless SQL Warehouse (`dbsql_version 2026.39`) with dbt-core 1.11.8 and
dbt-databricks 1.11.7, into an empty schema:

| Check | Result |
|---|---|
| `dbt build` (starter) | **PASS=12, NO-OP=1** (TOTAL 13): 5 seeds, 5 views, 2 Delta tables, and the exposure, which dbt reports as NO-OP because it builds nothing |
| Seed row counts | `customers` 30 · `orders` 80 · `order_items` 111 · `products` 10 · `locations` 6 |
| `python3 scripts/doc_coverage.py`, starter | **0/39 = 0%** (exits 1 with `--min 100`) |
| Lab 5.1 solution, `dbt build` | **PASS=13, NO-OP=1** (TOTAL 14): the extra pass is the `on-run-start` hook that creates the mask function |
| `python3 scripts/doc_coverage.py`, solution | **39/39 = 100%** |
| Comments in Unity Catalog | every table and view has a comment; every column of every model has one |
| Tags in Unity Catalog | 2 table tags on each mart, `data_classification = pii` on 2 columns of `dim_customers` |
| Column mask | `customer_email` returns `***@example.com`; with `pii_reader_group` set to a group you belong to, it returns the real address, and restoring the var masks it again. The mask survives rebuilds. |
| Grants | with `reader_principal` set, `SELECT` is granted on both marts; rebuilding without it **revokes** it |
| Lakeflow Jobs (DABs) | `module_05_seed_job` then `module_05_build_job` both **succeed** on Serverless; the schema ends with 12 objects (5 seeds and 2 tables, 5 views) |
| Lineage | all 10 table-level edges Unity Catalog recorded match a dbt path once the ephemeral model is bridged; the 4 dbt-only edges all touch the ephemeral model or the exposure |

Row counts, node counts and coverage numbers are for the supplied seed. Verify against your own run
rather than hard-coding them.

## Credits

The underlying data is the [Jaffle Shop Classic](https://github.com/dbt-labs/jaffle-shop-classic)
dataset by dbt Labs (Apache 2.0), sampled from the raw data seeded by Lab 01.
