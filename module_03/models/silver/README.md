# Silver layer (shared boilerplate)

The silver layer every Module 3 lab builds on, and the reusable base for new labs. It gives the gold
labs clean, typed tables to start from, so they can focus on modelling rather than on cleaning.

Module 3 is **self-contained**: it ships the silver data as seeds and loads it with its own
`dbt seed`.

## How silver is provided: seeds, and only seeds

The seeds **are** the silver layer. There are deliberately no silver *models*:

- `dbt seed` loads `seeds/silver_*.csv` into a **globally named `silver` schema** (see the `seeds:`
  config in [`dbt_project.yml`](../../dbt_project.yml) and
  [`macros/generate_schema_name.sql`](../../macros/generate_schema_name.sql)), so one seed load
  serves the whole workspace.
- The gold and incremental labs read them directly with `source('silver', ...)`.

The data arrives pre-cleaned in the seeds, so a passthrough silver model would only copy the same
rows into every learner's schema for no benefit. Keeping silver as the shared seed tables means the
only things a learner materializes are the gold/incremental models they are actually building.

```
seeds/silver_*.csv
     |
     v  dbt seed                         (once per workspace)
<catalog>.silver.silver_*                <- 5 shared silver tables
     |
     v  source('silver', ...)
<catalog>.<your-schema>.fct_orders_*      <- gold (Lab 3.5) / incremental (Lab 3.6), yours
```

Only the `silver` schema is shared. Gold and incremental build into the schema from your own profile,
so you get a private copy of just the layer you are building and can rebuild it freely.

> **Use a separate catalog per environment.** The `silver` schema name is intentionally *not*
> environment-prefixed (unlike models in prod, which get a `{default}_{custom}` prefix), so one seed
> load can serve everyone. That means dev and prod must point at **different catalogs** — if they
> share a catalog, a developer's `dbt seed` rewrites the same `<catalog>.silver.*` tables prod reads.

### The one piece of logic that is not in the seed

Lab 3.6 simulates time passing with a `max_order_date` var that truncates the orders to a cutoff
date. A static seed cannot take a var, so that cutoff lives in the **incremental models** where they
read the source (and in the `assert_overwrite_model_covers_all_months` test, so its expected counts
track the same cutoff). Lab 3.5 always reads the full source, so it never applies a cutoff.

## Where the seeds come from

The CSVs are generated deterministically from Lab 01's raw Jaffle Shop data by
[`scripts/generate_silver_seeds.py`](../../scripts/generate_silver_seeds.py), which applies the same
cleaning a bronze→silver step would: cents → decimal dollars, timestamps → dates, renames, and the
food/drink flags. Re-run it if the raw data ever changes:

```bash
python3 scripts/generate_silver_seeds.py
```

Column types are pinned in [`seeds/_seed_properties.yml`](../../seeds/_seed_properties.yml). That is
load-bearing: money columns load as `DECIMAL(16,2)` so `order_total = subtotal + tax_paid` holds
exactly, and date columns load as `DATE` so the gold layer can partition/cluster on them and the
cutoff var can compare against them.

## The tables

| Seed / source | Rows | Grain |
|---------------|------|-------|
| `silver_orders` | 61,948 | One row per order. `order_date` spans 2024-09-01 to 2025-08-31: 365 distinct days across 12 months. |
| `silver_order_items` | 90,900 | One row per item on an order. |
| `silver_customers` | 935 | One row per customer. |
| `silver_products` | 10 | One row per SKU, split into food and drink. |
| `silver_locations` | 6 | One row per store. |

That date span is deliberate: 12 months and 365 days give two partition-key candidates at very
different cardinalities, which is exactly what Lab 3.5 exercises.

## Using these tables in a lab

Read them with `source()`:

```sql
select * from {{ source('silver', 'silver_orders') }}
```

Tests on the silver data live in [`__sources.yml`](__sources.yml): uniqueness and not-null on every
key, referential integrity between the tables, an `accepted_values` check on `product_type`, and
`order_total = subtotal + tax_paid` on every order. Because they run against the seeds, a failure
points at the seed data rather than at a transformation.

## Reusing this as boilerplate for a new lab or module

This silver layer is the template other Module 3 labs (and future modules) build on:

- **New labs go in their own folder** under `models/`, alongside `gold/` and `incremental/`.
- **Read from silver with `source('silver', ...)`** — never hardcode a seed name or schema.
- **Keep lab-specific logic inside your folder**, so the module stays selectable one lab at a time
  with `dbt build --select path:models/<your-lab>`.
- **To start a new module from this pattern:** copy the `seeds/` + `_seed_properties.yml` +
  `models/silver/__sources.yml` trio, point the source at your seeds, and you have a self-contained
  silver base with no bronze pipeline to stand up.
