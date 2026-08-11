{#
    Order-grain fact loaded incrementally with the merge strategy.

    Where insert_overwrite thinks in partitions, merge thinks in rows. dbt emits a Delta
    MERGE INTO keyed on unique_key: rows that already exist are updated in place, rows that do not
    are inserted. Re-running over the same window is therefore idempotent -- you get corrections,
    not duplicates.

    Two things worth knowing before you rely on this:

    1. unique_key must actually be unique in the SELECT below. If two source rows map to the same
       key, Databricks aborts the whole MERGE with
       DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE, because it cannot tell which row
       should win. That is a feature: it fails loudly instead of picking arbitrarily.

    2. dbt builds the ON clause with <=> (null-safe equality), so a NULL key matches a NULL key.
       Keep the key not-null -- there is a test for that in _incremental_models.yml.
#}

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'merge',
    unique_key = 'order_id',
    file_format = 'delta',
    on_schema_change = 'append_new_columns'
) }}

with

source as (

    select * from {{ source('silver', 'silver_orders') }}

    {#
        The `max_order_date` cutoff simulates time passing: it truncates the silver source to orders
        on or before a given date, so moving the cutoff forward behaves like new data arriving. It
        defaults to no cutoff (the full 61,948 orders).
    #}
    {% if var('max_order_date', none) is not none %}
    where order_date <= date('{{ var('max_order_date') }}')
    {% endif %}

),

orders as (

    select * from source

    {% if is_incremental() %}

    {#
        merge does not replace partitions, so this filter only decides how much work to do -- it
        cannot silently drop rows the way the insert_overwrite filter can. A one-month lookback is
        enough to catch late-arriving orders and restatements of recent ones.
    #}
    where order_date >= (select max(order_date) from {{ this }}) - interval 1 month

    {% endif %}

),

locations as (

    select * from {{ source('silver', 'silver_locations') }}

),

joined as (

    select

        ---------- ids
        orders.order_id,
        orders.customer_id,
        orders.location_id,

        ---------- dates
        orders.order_date,

        ---------- dimensions
        locations.location_name,

        ---------- numerics
        orders.subtotal,
        orders.tax_paid,
        orders.order_total,

        ---------- audit
        {# Proves an upsert happened: on a re-run this timestamp moves, the row count does not. #}
        current_timestamp() as dbt_loaded_at

    from orders

    left join locations
        on orders.location_id = locations.location_id

)

select * from joined
