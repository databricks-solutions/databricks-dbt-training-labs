with

locations as (

    select * from {{ ref('stg_locations') }}

),

order_data as (

    select
        location_id,

        count(distinct order_id) as count_orders,
        sum(order_total) as total_revenue,
        min(ordered_at) as first_order_at,
        max(ordered_at) as last_order_at

    from {{ ref('orders') }}

    group by 1

),

joined as (

    select
        locations.*,

        coalesce(order_data.count_orders, 0) as count_orders,
        order_data.total_revenue,
        order_data.first_order_at,
        order_data.last_order_at

    from locations

    left join order_data
        on locations.location_id = order_data.location_id

)

select * from joined
