{#
    The same gold fact table using liquid clustering instead of partitioning.

    Delta forbids combining CLUSTER BY with PARTITIONED BY, so this has to be a separate model
    rather than another config on the partitioned one. That constraint is the point: partitioning
    and liquid clustering are alternatives, not layers.

    dbt issues OPTIMIZE against this table after the run completes, which is how the clustering is
    actually applied. Expect it in the run output.
#}

{{ config(
    materialized = 'table',
    liquid_clustered_by = ['order_date', 'customer_id']
) }}

select * from {{ ref('int_orders_enriched') }}
