with

products as (

    select * from {{ ref('stg_products') }}

),

order_items as (

    select * from {{ ref('order_items') }}

),

product_orders as (

    select
        product_id,

        count(order_item_id) as count_orders,
        sum(product_price) as total_revenue,
        sum(supply_cost) as total_cost

    from order_items

    group by 1

),

joined as (

    select
        products.*,

        coalesce(product_orders.count_orders, 0) as count_orders,
        product_orders.total_revenue,
        product_orders.total_cost,
        product_orders.total_revenue - product_orders.total_cost as gross_profit

    from products

    left join product_orders
        on products.product_id = product_orders.product_id

)

select * from joined
