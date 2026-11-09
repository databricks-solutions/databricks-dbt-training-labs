{# Staging orders: one row per order, straight from the seed. #}

select

    order_id,
    customer_id,
    location_id,
    order_date,
    order_status,
    subtotal,
    tax_paid,
    order_total

from {{ ref('orders') }}
