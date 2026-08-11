-- The companion assertion to assert_gold_partition_columns: the liquid-clustered model must have
-- no Hive partition columns at all. Delta forbids combining CLUSTER BY with PARTITIONED BY, so if
-- this ever returns a row, the two layout strategies have been mixed up.
--
-- See the depends_on note in assert_gold_partition_columns.sql: reading information_schema means
-- dbt needs the hint below to order this test after the model it checks.

-- depends_on: {{ ref('fct_orders_clustered') }}

select
    column_name,
    partition_index

from {{ target.catalog }}.information_schema.columns

where table_schema = '{{ target.schema }}'
  and table_name = 'fct_orders_clustered'
  and partition_index is not null
