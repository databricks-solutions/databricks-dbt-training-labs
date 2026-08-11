-- Guards against the insert_overwrite failure mode this lab is built around: a partition replaced
-- with FEWER rows than it should hold, because the incremental filter was too narrow. The run
-- reports success and no error is raised, so only a test like this catches it.
--
-- Comparing which months exist is not enough. A clobbered month usually still exists, just with
-- some of its days missing -- for example, July can remain with only 16 of its 31 days while
-- thousands of orders vanish. So this compares the order COUNT per month against silver_orders, which
-- is the only source of truth about how many orders each month really had.
--
-- Lab step 4 has you break this deliberately, watch it fail, and then fix it.

with expected as (

    select
        cast(date_trunc('month', order_date) as date) as order_month,
        count(distinct order_date) as expected_days,
        count(*) as expected_orders

    from {{ source('silver', 'silver_orders') }}

    {#
        Apply the same max_order_date cutoff the overwrite model reads its source with, so the
        expected counts match the amount of source data that existed on the run being checked.
        Without this, a cutoff run (Lab 3.6) would compare a truncated table against full silver.
    #}
    {% if var('max_order_date', none) is not none %}
    where order_date <= date('{{ var('max_order_date') }}')
    {% endif %}

    group by 1

),

actual as (

    select
        order_month,
        count(*) as actual_days,
        sum(count_orders) as actual_orders

    from {{ ref('fct_orders_daily_overwrite') }}

    group by 1

)

select

    expected.order_month,
    expected.expected_days,
    coalesce(actual.actual_days, 0) as actual_days,
    expected.expected_orders,
    coalesce(actual.actual_orders, 0) as actual_orders

from expected

left join actual
    on expected.order_month = actual.order_month

{# A partition is wrong if it is missing entirely, or short on days, or short on orders. #}
where actual.order_month is null
   or actual.actual_days != expected.expected_days
   or actual.actual_orders != expected.expected_orders
