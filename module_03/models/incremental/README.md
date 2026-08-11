# Lab 3.6: Incremental Models (insert-overwrite / MERGE)

You take a model that rebuilds itself from scratch every run and convert it to load only what
changed. Two strategies, side by side: `insert_overwrite`, which replaces whole partitions, and
`merge`, which upserts individual rows. Then you break one of them on purpose, watch it silently
delete 3,759 orders, and fix it.

**Before you start:** complete the setup in the [module README](../../README.md), which includes the
one-time `dbt seed` that loads the silver layer. This lab reads the shared
[silver layer](../silver/README.md) via `source()`.

## What you will learn

- How to configure `materialized='incremental'` with a Delta load strategy.
- The difference between **partition-scoped replacement** (`insert_overwrite`) and **row-level
  upsert** (`merge`), and when each is the right tool.
- Why `is_incremental()` exists and what it evaluates.
- How an incremental filter can silently destroy data, how to spot it, and how to write a test that
  catches it.
- What `--full-refresh` actually does, and when you have no choice but to use it.

## What's in this folder

| File | Purpose |
|------|---------|
| `fct_orders_daily_overwrite.sql` | Daily aggregates, `incremental_strategy='insert_overwrite'`, partitioned by `order_month`. |
| `fct_orders_upsert.sql` | Order-grain fact, `incremental_strategy='merge'`, keyed on `order_id`. |
| `_incremental_models.yml` | Descriptions and tests for both. |

The `incremental_strategy` configs sit in the model files rather than `dbt_project.yml` for the same
reason the layout configs do in Lab 3.5: the strategy is the subject of the lab, and the two models
deliberately differ on exactly that setting. `+materialized: incremental` stays in
`dbt_project.yml`.

## Simulating time passing

Incremental models are hard to demo on a static dataset: the second run has nothing new to find. So
both incremental models accept an optional cutoff var where they read the silver source:

```bash
dbt build --select path:models/incremental --vars '{"max_order_date": "2025-06-30"}'
```

That truncates the `silver_orders` source to orders on or before the given date as the model reads
it. Move the cutoff forward and it behaves exactly like new data arriving in your source system. With
no var, you get all 61,948 orders, which is why Lab 3.5 is unaffected.

The cutoff lives in the models rather than in the silver layer because the silver layer is a static
seed — a seed cannot take a var. Lab 3.5 always reads the full source, so only the incremental models
apply a cutoff. (The `assert_overwrite_model_covers_all_months` test applies the same cutoff to its
expected counts, so it stays correct under any cutoff.)

## Lab steps

Run everything from the project root (`module_03/`), with your environment exported:

```bash
set -a && source .env && set +a
```

### 1. First run: pretend it is the end of June

```bash
dbt build --select path:models/incremental \
  --vars '{"max_order_date": "2025-06-30"}' --full-refresh
```

(The silver layer is already loaded by `dbt seed`; the models read it via `source()`.) On the very
first run there is no table yet, so `is_incremental()` returns **false**, the `WHERE`
clause is skipped entirely, and both models load all history. Confirm what landed:

```sql
select count(*) as days, count(distinct order_month) as months, sum(count_orders) as orders
from   fct_orders_daily_overwrite;
```

| days | months | orders |
|---|---|---|
| 303 | 10 | 44,515 |

### 2. Second run: two more months arrive

Move the cutoff forward. **No `--full-refresh` this time** — that is the whole point:

```bash
dbt build --select path:models/incremental \
  --vars '{"max_order_date": "2025-08-31"}'
```

Now `is_incremental()` returns true, so the filter applies and only recent data is read. Look at the
SQL dbt actually sent:

```bash
grep -i "replace on" target/run/module_03/models/incremental/fct_orders_daily_overwrite.sql
```

```
replace on (t.order_month <=> s.order_month)
```

That is `INSERT INTO ... REPLACE ON`, Delta's partition-swap syntax. Every `order_month` the SELECT
produced is replaced wholesale; every other partition is left alone.

You will also see this warning, which is expected:

```
insert_overwrite is supported on SQL warehouses with DBR 17.1+. On older DBR versions, this
strategy would be equivalent to using the table materialization.
```

dbt cannot detect the DBR version behind a Serverless warehouse, so it warns unconditionally. On the
validated Serverless warehouse the `REPLACE ON` syntax works correctly — verify it yourself with the
per-month counts below rather than taking either the warning or this README on trust.

Now check that the **early** partitions survived:

```sql
select order_month, count(*) as days, sum(count_orders) as orders
from   fct_orders_daily_overwrite
group by order_month order by order_month;
```

All 12 months, 365 days, 61,948 orders — and September through May hold exactly what they held after
run 1. Only July and August were rewritten.

### 3. Prove the merge is idempotent

Run the upsert model again with the **same** cutoff, changing nothing:

```sql
select count(*) as rows, max(dbt_loaded_at) as loaded from fct_orders_upsert;
```

```bash
dbt run --select fct_orders_upsert --vars '{"max_order_date": "2025-08-31"}'
```

Re-query. The row count is unchanged at 61,948, but `dbt_loaded_at` has moved. Rows were **updated
in place**, not duplicated — that is `MERGE ... WHEN MATCHED THEN UPDATE SET *` doing its job, and it
is what makes a merge model safe to re-run.

Two things to know about `unique_key`:

- **It must really be unique.** If two source rows share a key, Databricks aborts the whole MERGE
  with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE` rather than picking one arbitrarily.
  Deduplicate in the model with a `row_number()` window if your source can produce duplicates.
- **dbt uses null-safe equality (`<=>`)** in the ON clause, so a NULL key matches other NULL keys and
  will update them. Keep the key `not_null`; there is a test for it.

### 4. Break it: the silent data loss

This is the most important step in the lab.

Set up a baseline where the latest month is only **partially** loaded — this matters, and step 6
explains why:

```bash
dbt run --select fct_orders_daily_overwrite \
  --vars '{"max_order_date": "2025-07-15"}' --full-refresh
```

July now holds 15 days and 3,759 orders. Now change the filter in
`fct_orders_daily_overwrite.sql` to the one that looks obviously reasonable:

```sql
-- the anti-pattern: filtering on a column NARROWER than the partition key
where order_date > (select max(order_date) from {{ this }})
```

Run it incrementally:

```bash
dbt build --select fct_orders_daily_overwrite \
  --vars '{"max_order_date": "2025-08-31"}'
```

**The run succeeds.** No error, no warning. Now count:

| | Expected | Actual |
|---|---|---|
| days | 365 | 350 |
| orders | 61,948 | 58,189 |
| July partition | 31 days / 8,044 orders | 16 days / 4,285 orders |

**15 days and 3,759 orders are gone.** The filter returned only orders after 15 July. Those rows all
belong to the July partition, so `REPLACE ON` swapped the entire July partition out and replaced it
with just those 16 days. The first 15 days were not in the incoming batch, so they ceased to exist.

This is the defining hazard of partition-scoped replacement, and the dbt docs are blunt about it:

> **Important!** Be sure to re-select *all* of the relevant data for a partition or cluster when
> using this incremental strategy.

Now fix it by filtering on the **partition column** instead:

```sql
where order_month >= (select max(order_month) from {{ this }}) - interval 1 month
```

Re-run from the same July-15 baseline and all 365 days come back. The rule is one line long:
**with `insert_overwrite`, your filter must never be narrower than your partition key.** The
`- interval 1 month` lookback additionally re-reads the most recent month, so late-arriving orders
correct the partition instead of being lost.

`merge` does not have this failure mode. Its filter only decides how much work to do; rows outside
the window are simply not touched.

### 5. Write a test that catches it

Silent failures need tests, because by definition you will not notice them.
[`assert_overwrite_model_covers_all_months`](../../data-tests/assert_overwrite_model_covers_all_months.sql)
compares the order count per month against `silver_orders` and fails if any month is missing or
short.

It compares **counts** rather than just which months exist because a clobbered month usually still
shows up in the table — July can remain with only 16 of its 31 days while thousands of orders are
gone. A presence-only check would pass on that broken table. Re-break the filter from step 4 and
watch this test fail.

### 6. Understand `--full-refresh`

```bash
dbt run --select fct_orders_daily_overwrite --vars '{"max_order_date": "2025-08-31"}' --full-refresh
```

```bash
grep -i "create or replace" target/run/module_03/models/incremental/fct_orders_daily_overwrite.sql
```

On a full refresh dbt discards the incremental logic entirely and issues
`CREATE OR REPLACE TABLE`. For Delta this is atomic — the table is never missing while it rebuilds.
Non-Delta formats get a `DROP` followed by a `CREATE`, with a window where the table does not exist.

When you need it:

- **Changing `partition_by`.** dbt will not detect this on an incremental model and will not issue
  `ALTER TABLE`; new rows keep appending under the old layout until you full-refresh.
- **Changing `tblproperties`.**
- **Recovering from the step 4 mistake.** Once a partition has been clobbered, the data is gone from
  that table. Fixing the filter stops the bleeding but does not restore what was lost — only a
  rebuild from source does.
- **Backfilling** after upstream logic changes.

Protect an expensive model from an accidental rebuild with `full_refresh: false` in its config; that
config wins over the CLI flag.

## Choosing a strategy

| | `insert_overwrite` | `merge` | `replace_where` | `append` |
|---|---|---|---|---|
| Unit of work | Partition | Row | Predicate scope | Row |
| Needs `unique_key` | No | Yes, in practice | No | No |
| Needs `partition_by` | Effectively yes | No | No | No |
| Idempotent re-run | Yes, per partition | Yes | Yes, per predicate | **No** — duplicates |
| Silent-loss risk | **Yes** | No | **Yes** | No |
| Best for | Batch reload of recent periods | CDC, upserts, restatements | Explicit custom scope | Immutable event logs |

Rules of thumb:

- **Reloading yesterday's or last month's data wholesale?** `insert_overwrite`, partitioned on the
  period, filtered on the partition column.
- **Upserting by a business key, or handling restatements?** `merge` with a genuinely unique
  `unique_key`.
- **Need a scope that is not a partition?** `replace_where` with explicit `incremental_predicates` —
  it emits `INSERT INTO ... REPLACE WHERE <predicate>`. This is the most explicitly
  SQL-Warehouse-native option, since the scope is declared rather than inferred, and it produces no
  DBR warning. Worth knowing about even though this lab does not build a model with it.
- **Appending immutable events?** `append`. Just remember it is the one strategy that will happily
  duplicate rows if you re-run an overlapping window.

## Gotchas

- **`insert_overwrite` filters must not be narrower than the partition key.** Step 4. The single most
  expensive mistake in this lab.
- **`is_incremental()` is false on the first run** and whenever `--full-refresh` is passed, so the
  full history loads. It returns true only when the model is incremental, the relation already exists
  as a table, and no full refresh was requested.
- **Late-arriving data needs a lookback window.** `>= max(...) - interval 1 month` rather than
  `> max(...)`, or corrections for recent periods never land.
- **`merge` aborts on duplicate `unique_key` values** rather than guessing. Deduplicate upstream.
- **`on_schema_change` handles columns, not layout.** It cannot restructure partitions. The overwrite
  model here uses `append_new_columns`.
- **The DBR 17.1+ warning on Serverless is expected.** dbt cannot see the DBR version behind a
  Serverless warehouse. Verify behaviour with row counts, not with the absence of warnings.
- **An unqualified `DESCRIBE DETAIL` can return cached metadata** right after a rebuild. Fully
  qualify the table name.

## Validated configuration

Run end to end on a Serverless SQL Warehouse (`dbsql_version 2026.20`) with dbt-core 1.11.8 and
dbt-databricks 1.11.7:

| Command | Result |
|---|---|
| `dbt build` (whole module) | **67/67** |
| `dbt build --select path:models/incremental` | **17/17** |
| Run 1 (June cutoff) | 303 days / 10 months / 44,515 orders |
| Run 2 (August cutoff, incremental) | 365 days / 12 months / 61,948 orders, early partitions intact |
| Merge re-run | 61,948 rows unchanged, `dbt_loaded_at` advanced |
| Anti-pattern run | 350 days / 58,189 orders — **3,759 orders lost**, run reported success |

All four Delta syntaxes (`REPLACE ON`, `REPLACE WHERE`, `INSERT OVERWRITE ... PARTITION`, `MERGE`)
were confirmed working on that warehouse. Note that `SET spark.sql.sources.partitionOverwriteMode`
is **not** available on Serverless — which is why dbt uses `REPLACE ON` there instead of the older
dynamic-partition-overwrite mechanism.

## What's next

- **Lab 3.7** — an SCD Type 2 gold dimension using dbt snapshots, where tracking history becomes the
  model's whole job rather than something you avoid.
