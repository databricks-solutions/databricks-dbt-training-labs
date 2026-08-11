{#
    The shared gold SELECT, materialized as ephemeral so it is inlined into both gold models.
    Keeping the business logic here means fct_orders_partitioned and fct_orders_clustered differ
    by exactly one thing: their physical layout config. That is what makes the comparison in this
    lab a fair test.
#}

with

orders as (

    select * from {{ source('silver', 'silver_orders') }}

),

order_items as (

    select * from {{ source('silver', 'silver_order_items') }}

),

products as (

    select * from {{ source('silver', 'silver_products') }}

),

locations as (

    select * from {{ source('silver', 'silver_locations') }}

),

order_items_joined as (

    select
        order_items.order_id,

        products.product_price,
        products.is_food_item,
        products.is_drink_item

    from order_items

    left join products on order_items.product_id = products.product_id

),

order_items_summary as (

    select
        order_id,

        count(*) as count_order_items,
        sum(case when is_food_item then 1 else 0 end) as count_food_items,
        sum(case when is_drink_item then 1 else 0 end) as count_drink_items,
        sum(product_price) as order_items_subtotal

    from order_items_joined

    group by 1

),

joined as (

    select

        ---------- ids
        orders.order_id,
        orders.customer_id,
        orders.location_id,

        ---------- partition and cluster key candidates
        orders.order_date,
        cast(date_trunc('month', orders.order_date) as date) as order_month,

        ---------- dimensions
        locations.location_name,

        ---------- numerics
        orders.subtotal,
        orders.tax_paid,
        orders.order_total,
        coalesce(order_items_summary.order_items_subtotal, 0) as order_items_subtotal,
        coalesce(order_items_summary.count_order_items, 0) as count_order_items,
        coalesce(order_items_summary.count_food_items, 0) as count_food_items,
        coalesce(order_items_summary.count_drink_items, 0) as count_drink_items,

        ---------- booleans
        coalesce(order_items_summary.count_food_items, 0) > 0 as is_food_order,
        coalesce(order_items_summary.count_drink_items, 0) > 0 as is_drink_order

    from orders

    left join order_items_summary
        on orders.order_id = order_items_summary.order_id

    left join locations
        on orders.location_id = locations.location_id

)

select * from joined
