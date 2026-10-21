# Module 4: Testing and Data Quality with dbt on Databricks

The dbt project behind the Module 4 testing labs: generic tests, singular tests, Delta constraints
versus dbt tests, `dbt build`, and warning versus failure severity.

It is a **repeatable lab boilerplate**: small seeded fixtures plus a catalog of **known defects**, so
every lab starts from the same state and has deterministic pass and fail cases. It is fully
self-contained. It does not need Lab 01, Module 3, or any earlier output.

| Path | What it is |
|------|-----------|
| [`seeds/`](seeds/) | The fixtures (`customers`, `products`, `locations`, `orders`, `order_items`) and the `defect_catalog` answer key. |
| [`models/staging/`](models/staging/) | Five staging views. Starter YAML with descriptions and **no tests**. |
| [`models/marts/`](models/marts/) | `fct_orders`, a Delta table (the later "constraints vs tests" lab attaches to it). |
| [`data-tests/`](data-tests/) | Where singular tests live. Holds the Lab 4.3 starter placeholder. |
| [`labs/`](labs/) | Lab guides and reference solutions. See [Lab 4.3](labs/lab_4_3_singular_test/README.md). |
| [`scripts/`](scripts/) | `generate_module4_seeds.py`, which regenerates the seeds deterministically. |

## Prerequisites

- A Databricks workspace with Unity Catalog enabled
- A SQL Warehouse (Serverless or Classic) you can query
- A catalog and schema you have `CREATE` privilege on
- Python 3.10+
- A Databricks Personal Access Token (or SSO via the `databricks` CLI)

## Setup

```bash
cd module_04
cp .env.template .env                 # then edit .env with your real values
cp profiles.yml.example profiles.yml  # reads the env vars from .env

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

set -a && source .env && set +a       # export DATABRICKS_* vars

dbt deps
dbt debug                             # confirm the connection before you build anything
```

`profiles.yml`, `.env`, and the generated `target/`, `logs/`, `dbt_packages/` are gitignored. Never
commit them.

## Build the starter

```bash
dbt build
```

`dbt build` loads the seeds, builds the models, and runs any tests, all in dependency order. The
**starter is green**: no generic tests are declared yet, and the one singular test is a placeholder
that returns no rows. The known defects are in the data waiting for the tests *you* add.

Everything lands in **your own schema** (`DATABRICKS_SCHEMA` in `.env`). The seeds are tiny, so
reseeding is cheap and nothing is shared between learners.

> **Why `ref()` and not `source()` for the seeds?** `dbt build` orders nodes by their `ref()`
> dependencies. A `source()` has no link to the seed that fills it, so a model or test could run
> before the seed finished loading. Reading seeds with `ref()` makes one `dbt build` work from scratch.

## Known defects

The fixtures are a clean sample of the Jaffle Shop data with seven defects injected on purpose. The
[`defect_catalog`](seeds/defect_catalog.csv) seed is the answer key (one row per defective row), and
the generator re-derives every count below from the data it writes, so they cannot drift.

| ID | Table | What is wrong | Rows | Caught by |
|----|-------|---------------|-----:|-----------|
| D01 | `customers` | `customer_name` is `NULL` | 1 | generic test: `not_null` |
| D02 | `customers` | `customer_id` appears twice (a duplicated key) | 1 key | generic test: `unique` |
| D03 | `orders` | `customer_id` has no matching customer | 1 | generic test: `relationships` |
| D04 | `orders` | `order_status` is `delivred`, a typo | 1 | generic test: `accepted_values` |
| D05 | `orders` | `tax_paid` is negative | 1 | `dbt_utils.expression_is_true` (a Delta `CHECK` constraint is the platform-side option, covered in the constraints lab) |
| **D06** | `orders` | `subtotal` differs from the sum of its item prices | **4** | **singular SQL test ([Lab 4.3](labs/lab_4_3_singular_test/README.md))** |
| D07 | `order_items` | `product_id` is an unknown SKU | 2 | `relationships` (try `severity: warn`) |

Two orders are *legitimately* item-less (subtotal 0). That is an edge case for your SQL to handle, not
a defect.

## Labs

| Lab | Topic | Defects it uses |
|-----|-------|-----------------|
| Generic tests | `not_null`, `unique`, `relationships`, `accepted_values` in YAML | D01 to D04, D07 |
| [**4.3 Singular SQL test**](labs/lab_4_3_singular_test/README.md) | A custom SQL test for a business rule | **D06** |
| Constraints vs tests | Delta `CHECK` / `NOT NULL` versus dbt tests | D05 |
| Severity | `warn` versus `error` | D07 |

All labs plug into the same fixtures and defect catalog. This repository currently ships the
boilerplate and Lab 4.3.

## Regenerating the seeds

The seeds are produced by a deterministic script, so the output is byte-for-byte identical every run:

```bash
python3 scripts/generate_module4_seeds.py
```

It samples a few customers and their orders from Lab 01's raw Jaffle Shop data (`jaffle_shop/seeds/`),
converts cents to dollars, adds a synthetic `order_status`, injects the defects, and checks that the
counts above match the data. Money loads as `DECIMAL(16,2)` and dates as `DATE` (see
[`seeds/_seed_properties.yml`](seeds/_seed_properties.yml)) so numeric comparisons and constraints
behave exactly.

## Validated configuration

Run end to end on a Serverless SQL Warehouse (`dbsql_version 2026.39`) with dbt-core 1.11.8 and
dbt-databricks 1.11.7, into an empty schema:

| Check | Result |
|---|---|
| `dbt build` (starter) | **13/13**: 6 seeds, 6 models (5 views + the Delta `fct_orders`), 1 placeholder test |
| Seed row counts | `customers` 31 · `orders` 80 · `order_items` 104 · `products` 10 · `locations` 6 · `defect_catalog` 11 |
| One test per defect (throwaway copy) | D01 **1** · D02 **1** · D03 **1** · D04 **1** · D05 **1** · D06 **4** · D07 **2** failing rows |
| Lab 4.3 solution, `dbt test` | **fails with 4 rows**, the same 4 `order_id`s as D06 in `defect_catalog` |
| Lab 4.3 with `quarantine_subtotal_defects`: `dbt run --select stg_orders --vars ...`, then `dbt test --select assert_order_subtotal_matches_items` | **passes with 0 rows**; restoring with `dbt run --select stg_orders` makes it fail with 4 rows again |
| The same quarantine as a single `dbt build --select stg_orders assert_order_subtotal_matches_items`, with generic tests for D03, D04 and D05 added | **exits with an error**: Lab 4.3's test passes, but the 3 generic tests on `stg_orders` fail |

`customers` holds 31 rows because D02 duplicates one of the 30 customers. The row counts, node counts
and failing-row counts above are for the supplied seed. Verify against your own run rather than
hard-coding them.

## Credits

The underlying data is the [Jaffle Shop Classic](https://github.com/dbt-labs/jaffle-shop-classic)
dataset by dbt Labs (Apache 2.0), sampled from the raw data seeded by Lab 01.
