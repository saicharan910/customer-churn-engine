with aggregated_subs as (
    select
        customer_id,
        max(status) as subscription_status,
        sum(mrr_amount) as total_mrr,
        min(start_date) as original_start_date,
        max(renewal_date) as upcoming_renewal_date
    from {{ ref('stg_subscriptions') }}
    group by customer_id
)
select
    c.customer_id,
    c.company_name,
    c.industry,
    c.tier,
    c.signup_date,
    coalesce(s.subscription_status, 'None') as subscription_status,
    coalesce(s.total_mrr, 0) as mrr,
    coalesce(s.total_mrr * 12, 0) as arr,
    s.upcoming_renewal_date
from {{ ref('stg_customers') }} c
left join aggregated_subs s on c.customer_id = s.customer_id