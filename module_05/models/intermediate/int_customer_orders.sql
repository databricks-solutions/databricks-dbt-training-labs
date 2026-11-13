{#
    Per-customer order rollup, materialized as EPHEMERAL.

    An ephemeral model is inlined as a CTE into whatever selects from it, so it never exists in Unity
    Catalog. dbt's docs site shows it as a node in the DAG; Unity Catalog lineage never will. That
    gap is on purpose: it is the clearest example, in Lab 5.1, of why dbt lineage (logical) and Unity
    Catalog lineage (physical) complement each other.

    lifetime_spend counts only orders that were not cancelled or returned.
#}

select

    customer_id,
    count(*) as count_orders,
    min(order_date) as first_order_date,
    max(order_date) as last_order_date,
    sum(
        case when order_status in ('cancelled', 'returned') then 0 else order_total end
    ) as lifetime_spend

from {{ ref('stg_orders') }}

group by 1
