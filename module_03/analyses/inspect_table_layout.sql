-- Inspect the physical layout of the two gold models.
--
-- Analyses are not run by `dbt run`. Compile this file and run the result in a Databricks SQL
-- editor:
--
--     dbt compile --select inspect_table_layout
--     cat target/compiled/module_03/analyses/inspect_table_layout.sql

-- 1. The partitioned model: expect partitionColumns = ["order_month"], clusteringColumns = [].
describe detail {{ ref('fct_orders_partitioned') }};

-- 2. The clustered model: expect the mirror image, clusteringColumns populated and
--    partitionColumns empty. The two are mutually exclusive.
describe detail {{ ref('fct_orders_clustered') }};

-- 3. The same partition metadata, from information_schema, in a form you can join and filter.
--    partition_index is non-null only for partition columns and gives their ordinal position.
select
    table_name,
    column_name,
    partition_index

from {{ target.catalog }}.information_schema.columns

where table_schema = '{{ target.schema }}'
  and table_name in ('fct_orders_partitioned', 'fct_orders_clustered')
  and partition_index is not null

order by table_name, partition_index;

-- 4. Partition-level detail for the partitioned model: 12 rows, one per month.
show partitions {{ ref('fct_orders_partitioned') }};
