-- Asserts that the gold fact table really is partitioned by order_month in Databricks, rather
-- than merely being configured that way in dbt. Returns a row (and therefore fails) if the
-- physical partition columns are anything other than exactly [order_month].
--
-- This reads information_schema rather than DESCRIBE DETAIL because DESCRIBE is a command, not a
-- relation: `select ... from (describe detail t)` does not parse on Databricks SQL. The
-- partition_index column is non-null only for partition columns, and gives their ordinal position.
--
-- Because the query reads information_schema instead of using ref(), dbt cannot infer that this
-- test depends on the model. The depends_on hint below supplies that edge, so `dbt build` tests
-- the table only after rebuilding it rather than checking a stale one.

-- depends_on: {{ ref('fct_orders_partitioned') }}

with partition_columns as (

    select
        column_name,
        partition_index

    from {{ target.catalog }}.information_schema.columns

    where table_schema = '{{ target.schema }}'
      and table_name = 'fct_orders_partitioned'
      and partition_index is not null

)

select

    count(*) as partition_column_count,
    max(case when column_name = 'order_month' and partition_index = 0 then 1 else 0 end) as has_order_month

from partition_columns

having count(*) != 1
    or max(case when column_name = 'order_month' and partition_index = 0 then 1 else 0 end) != 1
