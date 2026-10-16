with lagged as (
    select
        event_id,
        customer_id,
        event_date,
        login_count,
        api_calls,
        lag(event_date) over (partition by customer_id order by event_date) as prev_event_date
    from {{ ref('stg_usage_events') }}
)
select
    event_id,
    customer_id,
    event_date,
    login_count,
    api_calls,
    sum(case when prev_event_date is null or (event_date - prev_event_date) > 7 then 1 else 0 end) over (partition by customer_id order by event_date) as session_cycle_id
from lagged