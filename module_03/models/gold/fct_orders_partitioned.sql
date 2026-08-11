{#
    Gold fact table using Hive-style partitioning.

    `partition_by` lives here rather than in dbt_project.yml because the physical layout is the
    subject of this lab: it belongs next to the SQL it affects, and the two gold models in this
    folder deliberately differ on this one config. The `+materialized: table` default stays in
    dbt_project.yml.

    order_month (12 distinct values) is chosen over order_date (365) on purpose. Partitioning by
    day on a table this small produces 365 tiny partitions, which is the anti-pattern Databricks
    warns about. Lab step 4 has you prove that for yourself.
#}

{{ config(
    materialized = 'table',
    partition_by = ['order_month']
) }}

select * from {{ ref('int_orders_enriched') }}
