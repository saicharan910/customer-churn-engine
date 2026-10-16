WITH source AS (
    SELECT * FROM "analytics_warehouse"."public"."raw_subscriptions"
)
SELECT
    TRIM(subscription_id) AS subscription_id,
    TRIM(customer_id) AS customer_id,
    ROUND(CAST(mrr_amount AS NUMERIC), 2) AS mrr_amount,
    status,
    CAST(start_date AS DATE) AS start_date,
    CAST(renewal_date AS DATE) AS renewal_date,
    CAST(churn_date AS DATE) AS churn_date
FROM source