# Lab 3.5: Gold Layer with Partitioning

You build a gold-layer fact table as a partitioned Delta table, then build the same table again with
liquid clustering, and use `DESCRIBE DETAIL` to prove what Databricks actually did on disk. Along the
way you make the wrong choice on purpose, so you can measure what it costs.

**Before you start:** complete the setup in the [module README](../../README.md), which includes the
one-time `dbt seed` that loads the silver layer. This lab reads the shared
[silver layer](../silver/README.md) via `source()`, so make sure `dbt seed` has been run once first.

## What you will learn

- How to materialize a gold model as a Delta `table` with a physical layout you control.
- The difference between **Hive partitioning** (`partition_by`) and **liquid clustering**
  (`liquid_clustered_by`), and why Delta will not let you use both on one table.
- How to verify a table's layout in Databricks rather than trusting your dbt config.
- Why partitioning a small table by a high-cardinality column makes things worse, measured.
- Which layout to reach for by default, and the size thresholds behind that answer.

## What's in this folder

| File | Purpose |
|------|---------|
| `int_orders_enriched.sql` | Ephemeral model holding the shared gold logic: one row per order, enriched with item aggregates, carrying both partition key candidates. Reads the silver seeds with `source()`. |
| `fct_orders_partitioned.sql` | The gold fact, `partition_by = ['order_month']`. |
| `fct_orders_clustered.sql` | The same gold fact, `liquid_clustered_by = ['order_date', 'customer_id']`. |
| `*.yml` | Descriptions and tests for each model. |

The two fact models are byte-identical apart from their config block. That is the whole design: the
business logic lives once in the ephemeral model and gets inlined into both, so every difference you
measure comes from the physical layout and nothing else.

### Where the configs live, and why

`+materialized: table` is declared in `dbt_project.yml`, per this repo's convention. The
`partition_by` and `liquid_clustered_by` configs sit in `{{ config() }}` blocks inside the model
files instead. That is deliberate: the physical layout is the subject of this lab, the two gold
models differ on exactly that one setting, and you want to see it next to the SQL it affects.

## Lab steps

Run everything from the project root (`module_03/`), with your environment exported:

```bash
set -a && source .env && set +a
```

### 1. Build the partitioned gold table

```bash
dbt run --select fct_orders_partitioned
```

Now read the SQL dbt actually sent to Databricks:

```bash
grep -i "partitioned by" target/run/module_03/models/gold/fct_orders_partitioned.sql
```

```
      partitioned by (order_month)
```

Open the whole file too -- it is the exact `create or replace table ... using delta` statement, with
the ephemeral model inlined as a CTE. This is the habit worth forming: `target/run/` holds the real
DDL, so when a config does not behave the way you expect, look there first.

### 2. Verify the layout in Databricks

In a SQL editor, against your own catalog and schema:

```sql
describe detail fct_orders_partitioned;
```

| Field | Expected |
|-------|----------|
| `partitionColumns` | `["order_month"]` |
| `clusteringColumns` | `[]` |
| `numFiles` | 12 |
| `sizeInBytes` | ~1,763,000 (1.7 MB) |

Then look at the partitions themselves:

```sql
show partitions fct_orders_partitioned;    -- 12 rows, one per month
show create table fct_orders_partitioned;  -- contains PARTITIONED BY (order_month)
```

**A gotcha worth knowing:** `DESCRIBE DETAIL` is a command, not a relation, so you cannot wrap it in
a subquery. `select * from (describe detail my_table)` fails to parse on Databricks SQL. When you
need partition metadata inside a real query, read `information_schema.columns` instead, where
`partition_index` is non-null only for partition columns:

```sql
select table_name, column_name, partition_index
from   <your_catalog>.information_schema.columns
where  table_schema = '<your_schema>'
  and  partition_index is not null;
```

That is exactly how the singular tests in [`../../data-tests/`](../../data-tests/) assert the layout.

### 3. Make the wrong choice, and measure it

`order_date` looks like the natural partition key. Try it. In `fct_orders_partitioned.sql`, change
the config to:

```sql
partition_by = ['order_date']
```

Then rebuild and re-inspect:

```bash
dbt run --select fct_orders_partitioned
```

```sql
describe detail fct_orders_partitioned;
```

If the output still shows the old layout, qualify the table fully
(`describe detail <catalog>.<schema>.fct_orders_partitioned`) -- an unqualified `DESCRIBE DETAIL` can
return cached metadata straight after a rebuild.

| | `order_month` | `order_date` |
|---|---|---|
| Partitions | 12 | 365 |
| `numFiles` | 12 | 365 |
| `sizeInBytes` | 1,762,643 | 4,786,370 |
| Avg partition size | ~145 KB | ~13 KB |

Same 61,948 rows, same columns. Thirty times the files and **2.7x more storage** -- the data got
bigger by being split up, because Parquet compresses and encodes worse across many tiny files, and
each file carries its own footer and statistics. Every query now also pays to open 365 files
instead of 12.

Note that neither figure is anywhere near the >= 1 GB per partition Databricks asks for. At this
table's size the honest answer is that it should not be partitioned at all, which is what the
guidance section below is about.

Also notice what did *not* happen: you did not need `--full-refresh`. A `table` materialization
drops and recreates on every run, so a layout change takes effect immediately. An `incremental`
model behaves differently -- see Gotchas.

Now revert to `order_month` and rebuild:

```bash
dbt run --select fct_orders_partitioned
```

### 4. Build the liquid-clustered twin

```bash
dbt run --select fct_orders_clustered
```

Check the generated DDL again, and you get `CLUSTER BY` where the partitioned model had
`PARTITIONED BY`:

```bash
grep -i "cluster by" target/run/module_03/models/gold/fct_orders_clustered.sql
```

Watch the log for an `optimize` statement after the create. dbt issues it automatically when
`liquid_clustered_by` is set; that is what actually applies the clustering.

```sql
describe detail fct_orders_clustered;
```

| Field | Expected |
|-------|----------|
| `partitionColumns` | `[]` |
| `clusteringColumns` | `["order_date","customer_id"]` |
| `numFiles` | 1 |
| `sizeInBytes` | ~1,664,000 (1.6 MB) |

The mirror image of step 2, and the most compact of the three layouts: one file rather than 12 or
365. Note that `order_date` is a perfectly good *clustering* key at day grain even though it was a
poor *partition* key -- clustering does not create a directory per value.

Now try to list its partitions:

```sql
show partitions fct_orders_clustered;
```

```
[DELTA_SHOW_PARTITION_IN_NON_PARTITIONED_TABLE] SHOW PARTITIONS is not allowed on a table that is
not partitioned
```

That error is the lesson. A liquid-clustered table has no partition directories at all: clustering
organizes data *within* files rather than splitting it across folders. This is also why you cannot
combine the two -- `partition_by` and `liquid_clustered_by` on one model would mean asking Delta for
`PARTITIONED BY` and `CLUSTER BY` in the same `CREATE TABLE`, which it rejects.

### 5. Run the whole lab with its tests

```bash
dbt build --select path:models/gold
```

24 nodes: the ephemeral model, both gold tables, and 21 tests. `dbt build` interleaves models and
tests in dependency order, so a broken model fails before anything downstream of it runs. The gold
models read the silver seeds via `source()`, so make sure `dbt seed` has been run once first.

The tests cover uniqueness and referential integrity on both gold models, plus two singular tests
that read `information_schema` to confirm the partitioned model really is partitioned by
`order_month` and the clustered model is not partitioned at all.

Worth knowing: those two singular tests carry a `-- depends_on: {{ ref(...) }}` comment. Because
they query `information_schema` rather than using `ref()` in the `from` clause, dbt cannot otherwise
tell that they depend on the models, and `dbt build` would test a stale table before rebuilding it.

Try breaking one: set `partition_by` back to `['order_date']`, re-run the build, and watch
`assert_gold_partition_columns` fail. Then revert.

## Partitioning vs liquid clustering: how to choose

Databricks' current guidance, from
[Partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions):

| Table size | Guidance |
|------------|----------|
| Under 1 TB | **Do not partition.** |
| 1 TB to 100 TB | Use liquid clustering. Partitioning likely hurts more often than it helps. |
| Over 100 TB | Partitioning *might* help. Benchmark against liquid clustering first. |

And from [Use liquid clustering for Delta tables](https://docs.databricks.com/aws/en/delta/clustering):

> Databricks recommends liquid clustering for all new tables, including streaming tables and
> materialized views.
>
> Liquid clustering is a data layout optimization technique that replaces table partitioning and
> `ZORDER`.

The practical rules:

- **Liquid clustering is the default.** Reach for `liquid_clustered_by` unless you have a specific
  reason not to. It handles high-cardinality columns, and you can change the keys later without
  rewriting the table's directory structure.
- **If you do partition, each partition should hold at least 1 GB.** Fewer, larger partitions beat
  many small ones.
- **Never partition on a high-cardinality column** -- timestamps, IDs, anything per-user. Use low or
  known cardinality: dates at a coarse grain, regions, physical locations.
- **They are alternatives, not layers.** Delta rejects `CLUSTER BY` together with `PARTITIONED BY`.
- **You will still meet partitioned tables.** Migrations from Hive, Glue and older Spark estates are
  full of them, which is why this lab teaches the mechanics rather than only the recommendation.

So why does this lab partition at all? Because knowing how `partition_by` behaves -- and being able
to show with `DESCRIBE DETAIL` why it is the wrong tool for a 1.7 MB table -- is more useful than
never having seen it. A 61,948-row gold table in production would be liquid-clustered, or left alone.

### The dbt configs

| Config | What it does | Notes |
|--------|--------------|-------|
| `partition_by` | Hive-style partition directories | String or list of columns |
| `liquid_clustered_by` | Delta liquid clustering | Up to 4 columns; dbt runs `OPTIMIZE` after the build |
| `auto_liquid_cluster` | `CLUSTER BY AUTO`, Databricks picks the keys | dbt-databricks 1.10+; UC managed tables, DBR 15.4 LTS+; mutually exclusive with `liquid_clustered_by` |
| `clustered_by` + `buckets` | Legacy Hive bucketing | Not liquid clustering; prefer `liquid_clustered_by` for new tables |
| `tblproperties` | Arbitrary Delta table properties | Changing these on an incremental model needs `--full-refresh` |

## Gotchas

- **`table` recreates, `incremental` does not.** Changing `partition_by` on a `table` model applies
  on the next `dbt run`. On an `incremental` model dbt will *not* detect the change and will *not*
  issue `ALTER TABLE` -- the table keeps its old layout while new rows append under it. You need
  `dbt run --full-refresh --select <model>`. Same for changing `liquid_clustered_by`.
- **`on_schema_change` does not cover layout.** It governs added and dropped *columns* only. It will
  not restructure partitions or clustering keys.
- **`DESCRIBE DETAIL` is not composable.** Covered in step 2; use `information_schema.columns` when
  you need the metadata inside a query.
- **`SHOW PARTITIONS` only works on partitioned tables.** On a clustered table it raises
  `DELTA_SHOW_PARTITION_IN_NON_PARTITIONED_TABLE`.
- **`OPTIMIZE` is what applies clustering.** dbt runs it for you after the build. Below certain
  write sizes, newly written data stays unordered until it runs.

## Validated configuration

Run end to end on a Serverless SQL Warehouse with dbt-core 1.11.8 and dbt-databricks 1.11.7,
building into an empty schema: `dbt seed` 5/5, full `dbt build` 67/67,
`dbt build --select path:models/gold` 24/24. The `DESCRIBE DETAIL` figures above are from that run;
yours will be close but not identical, since file sizes vary a little between writes.

## What's next

- **[Lab 3.6](../incremental/README.md)** -- incremental models with `insert_overwrite` and `MERGE`,
  where the `partition_by` you configured here becomes the unit of incremental replacement and
  `--full-refresh` becomes load-bearing.
- **Lab 3.7** -- an SCD Type 2 gold dimension using dbt snapshots.
