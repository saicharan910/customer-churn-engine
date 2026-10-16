with rfm as (
    select * from {{ ref('int_customer_rfm_metrics') }}
),
customers as (
    select * from {{ ref('dim_customers') }}
),
recent_activity as (
    select
        customer_id,
        sum(case when event_date >= current_date - 30 then login_count else 0 end) as logins_last_30d,
        sum(case when event_date < current_date - 30 and event_date >= current_date - 60 then login_count else 0 end) as logins_prev_30d
    from {{ ref('stg_usage_events') }}
    group by customer_id
),
growth as (
    select
        customer_id,
        case
            when logins_prev_30d = 0 and logins_last_30d > 0 then 100.0
            when logins_prev_30d = 0 and logins_last_30d = 0 then 0.0
            else round(((logins_last_30d - logins_prev_30d)::numeric / logins_prev_30d::numeric) * 100, 2)
        end as usage_growth_rate
    from recent_activity
)
select
    c.customer_id,
    c.company_name,
    c.tier,
    c.arr,
    c.upcoming_renewal_date,
    r.recency_days,
    r.frequency_score,
    r.monetary_value,
    coalesce(g.usage_growth_rate, 0.0) as usage_growth_rate,
    r.r_score,
    r.f_score,
    r.m_score,
    (c.upcoming_renewal_date - current_date) as days_until_renewal,
    case
        when (r.r_score <= 2 or r.f_score <= 2) and (c.upcoming_renewal_date - current_date) <= 60 then 'Critical'
        when (r.r_score <= 2 or r.f_score <= 3) and (c.upcoming_renewal_date - current_date) <= 90 then 'High'
        when r.r_score <= 3 then 'Medium'
        else 'Low'
    end as risk_tier
from customers c
join rfm r on c.customer_id = r.customer_id
left join growth g on c.customer_id = g.customer_id
where c.subscription_status = 'Active'