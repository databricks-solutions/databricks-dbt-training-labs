{#
    Customer dimension, a Delta table: one row per customer with their order history.

    Carries personal data (customer_name, customer_email), so it is the table Lab 5.1 protects with
    Unity Catalog tags and a column mask. Customers with no orders get count_orders = 0, not NULL.
#}

with

customers as (

    select * from {{ ref('stg_customers') }}

),

customer_orders as (

    select * from {{ ref('int_customer_orders') }}

)

select

    customers.customer_id,
    customers.customer_name,
    customers.customer_email,
    coalesce(customer_orders.count_orders, 0) as count_orders,
    customer_orders.first_order_date,
    customer_orders.last_order_date,
    coalesce(customer_orders.lifetime_spend, 0) as lifetime_spend

from customers

left join customer_orders
    on customers.customer_id = customer_orders.customer_id
