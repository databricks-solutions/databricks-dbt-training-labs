{#
    Daily order aggregates, loaded incrementally with the insert_overwrite strategy.

    insert_overwrite replaces whole partitions. On each run dbt works out which order_month values
    the SELECT below produced, and swaps those partitions out wholesale; every other partition is
    left untouched. That makes reloads cheap, and it makes one mistake expensive -- see the warning
    on the incremental filter.

    On a SQL Warehouse dbt emits `INSERT INTO ... REPLACE ON (...)` rather than the older
    `INSERT OVERWRITE ... PARTITION (...)`, and may print a DBR 17.1+ warning. See the lab README.
#}

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'insert_overwrite',
    partition_by = ['order_month'],
    file_format = 'delta'
) }}

with

orders as (

    select
        order_id,
        customer_id,
        order_date,
        cast(date_trunc('month', order_date) as date) as order_month,
        subtotal,
        tax_paid,
        order_total

    from {{ source('silver', 'silver_orders') }}

    {#
        The `max_order_date` cutoff simulates time passing: it truncates the silver source to orders
        on or before a given date, so moving the cutoff forward behaves like new data arriving. It
        defaults to no cutoff (the full 61,948 orders). This is the one bit of logic the labs need
        that the static seed cannot express, so it lives here in the model that reads the source.
    #}
    {% if var('max_order_date', none) is not none %}
    where order_date <= date('{{ var('max_order_date') }}')
    {% endif %}

),

filtered as (

    select * from orders

    {% if is_incremental() %}

    {#
        Filter on the PARTITION COLUMN, never on a narrower column.

        insert_overwrite replaces every partition this SELECT touches. If the filter let through
        only some rows of a partition, the rest of that partition would be silently deleted --
        no error, no warning, just missing data. Filtering on order_month guarantees that any
        partition we touch is re-emitted in full.

        The `- interval 1 month` is a lookback window: it re-reads the most recent month so
        late-arriving orders for that month are corrected rather than lost. Lab step 4 walks
        through both halves of this.
    #}
    where order_month >= (select max(order_month) from {{ this }}) - interval 1 month

    {% endif %}

),

daily as (

    select

        ---------- grain
        order_date,
        order_month,

        ---------- measures
        count(*) as count_orders,
        count(distinct customer_id) as count_customers,
        sum(order_total) as order_total,
        sum(subtotal) as subtotal,
        sum(tax_paid) as tax_paid,
        avg(order_total) as avg_order_total

    from filtered

    group by 1, 2

)

select * from daily
