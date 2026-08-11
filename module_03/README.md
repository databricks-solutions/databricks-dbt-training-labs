# Module 3: Modeling with dbt on Databricks

The dbt project behind the Module 3 labs: medallion layering, materializations, physical layout, and
slowly changing dimensions.

One project serves the whole module. You configure a profile once and load the silver layer once,
then run each lab on its own with a `--select`. That keeps the labs independent without making you
set up three separate projects against the same data.

| Path | What it is |
|------|-----------|
| [`models/silver/`](models/silver/) | The shared silver layer: seeds + `source()` definitions (no silver models). See its [README](models/silver/README.md). |
| [`models/gold/`](models/gold/) | **Lab 3.5 — Gold Layer with Partitioning.** See its [README](models/gold/README.md) for the lab guide. |
| [`models/incremental/`](models/incremental/) | **Lab 3.6 — Incremental Models (insert-overwrite / MERGE).** See its [README](models/incremental/README.md) for the lab guide. |
| [`data-tests/`](data-tests/) | Singular tests asserting physical layout and incremental correctness. |
| [`analyses/`](analyses/) | Layout inspection queries you run in a SQL editor. |

This project ships its silver data as **seeds** (`dbt seed`), so it is self-contained. See [`models/silver/README.md`](models/silver/README.md) for how the seed
boilerplate works and how to reuse it for a new lab.

Further labs land as sibling folders under `models/`, each reusing the same seeded silver layer.

## Prerequisites

- A Databricks workspace with Unity Catalog enabled
- A SQL Warehouse (Serverless or Classic) you can query
- A catalog and schema you have `CREATE` privilege on
- Python 3.10+
- A Databricks Personal Access Token (or use SSO via the `databricks` CLI)

Module 3 is **self-contained**: it ships its own silver data as seeds, so there is no Lab 01 raw-load
prerequisite and no bronze pipeline to stand up. See [`models/silver/README.md`](models/silver/README.md)
for how the seed boilerplate works.

## Setup (once for the whole module)

```bash
cp .env.template .env                 # then edit .env with your real values
cp profiles.yml.example profiles.yml  # reads the env vars from .env

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

set -a && source .env && set +a       # export DATABRICKS_* vars

dbt deps
dbt debug                             # confirm the connection before you build anything
```

`profiles.yml`, `.env`, and the generated `target/`, `logs/`, `dbt_packages/` are all gitignored.
Never commit them.

### Load the silver seeds (once per workspace)

```bash
dbt seed                              # loads the pre-cleaned silver tables
```

That writes five tables to a **globally named** `silver` schema, so it is a one-time step for
the whole workspace, not something each learner repeats. Confirm it worked:

```sql
show tables in <your-catalog>.silver;   -- expect 5 silver_* tables
```

## Running a lab

Each lab is a folder under `models/`, selectable on its own:

```bash
dbt build --select path:models/gold          # Lab 3.5 — partitioning
dbt build --select path:models/incremental   # Lab 3.6 — incremental
```

`dbt build` runs models and their tests together in dependency order. The labs read the silver layer
from seeds via `source()`, so make sure you have run `dbt seed` once (above) before building a lab.
To build the whole module at once, run `dbt build` with no selector: 67 nodes.

Lab 3.6 also uses an optional `max_order_date` var to simulate new data arriving between runs:

```bash
dbt build --select path:models/incremental --vars '{"max_order_date": "2025-06-30"}'
```

With no var, the labs see all 61,948 orders, which is what Lab 3.5 expects.

## Schema strategy

Only the seeded `silver` schema is shared across the workspace — one `dbt seed` serves everyone. The
gold and incremental models build into the schema from your profile, so each learner gets a private
copy of just the layer they are building and can drop and rebuild it without coordinating with
anyone. See [`macros/generate_schema_name.sql`](macros/generate_schema_name.sql).