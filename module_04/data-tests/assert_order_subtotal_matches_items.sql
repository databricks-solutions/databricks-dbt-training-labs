-- LAB 4.3 STARTER: singular SQL test.
--
-- THE BUSINESS RULE
--   An order's `subtotal` must equal the sum of the list prices of the items on that order.
--
-- HOW A SINGULAR TEST WORKS
--   dbt runs this query. If it returns ZERO rows the test PASSES. Every row it returns is a
--   violation, so write a query that returns exactly the orders that break the rule.
--
-- WHY A GENERIC TEST CAN'T DO THIS
--   not_null / unique / relationships / accepted_values look at one column of one table. This rule
--   needs a join (orders -> order_items -> products) and an aggregate (sum of prices).
--
-- YOUR TASK
--   1. Total each order's item prices (join stg_order_items to stg_products, group by order_id).
--   2. Compare that total to stg_orders.subtotal.
--   3. Return the orders where they differ. Think about orders that have NO items at all.
--
-- Use ref(), not table names:  {{ ref('stg_orders') }}, {{ ref('stg_order_items') }},
-- {{ ref('stg_products') }}. Do not end the query with a semicolon.
--
-- Until you write it, this placeholder returns no rows, so `dbt build` stays green.
-- When you are stuck, the reference answer is in labs/lab_4_3_singular_test/solution/.

select
    cast(null as string) as order_id

where false
