with sub as (
    select
        c.customer_id,
        current_date - max(e.event_date) as recency_days,
        count(distinct e.event_date) as frequency_score,
        coalesce(max(c.mrr_amount), 0) as monetary_value
    from {{ ref('stg_subscriptions') }} c
    left join {{ ref('stg_usage_events') }} e on c.customer_id = e.customer_id
    group by c.customer_id
)
select
    customer_id,
    recency_days,
    frequency_score,
    monetary_value,
    ntile(5) over (order by recency_days desc) as r_score,
    ntile(5) over (order by frequency_score asc) as f_score,
    ntile(5) over (order by monetary_value asc) as m_score
from sub