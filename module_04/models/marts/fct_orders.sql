{#
    Order-grain fact table, materialized as a Delta table.

    This is the physical table the later "Databricks constraints vs dbt tests" lab attaches Delta
    constraints to, so it is a real table rather than a view. It deliberately does NOT join
    customers: the duplicated customer (D02) would fan out and duplicate orders here.

    Item-less orders (subtotal 0) get count_order_items = 0, not NULL: an order with no items has
    zero items, not an unknown number of them (the same fix as the Module 3 gold layer).
#}

with

orders as (

    select * from {{ ref('stg_orders') }}

),

locations as (

    select * from {{ ref('stg_locations') }}

),

item_counts as (

    select
        order_id,
        count(*) as count_order_items

    from {{ ref('stg_order_items') }}

    group by 1

)

select

    orders.order_id,
    orders.customer_id,
    orders.location_id,
    locations.location_name,
    orders.order_date,
    orders.order_status,
    orders.subtotal,
    orders.tax_paid,
    orders.order_total,
    coalesce(item_counts.count_order_items, 0) as count_order_items

from orders

left join locations
    on orders.location_id = locations.location_id

left join item_counts
    on orders.order_id = item_counts.order_id
