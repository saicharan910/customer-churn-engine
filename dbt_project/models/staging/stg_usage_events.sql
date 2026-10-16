WITH source AS (
    SELECT * FROM "analytics_warehouse"."public"."raw_usage_events"
)
SELECT
    TRIM(event_id) AS event_id,
    TRIM(customer_id) AS customer_id,
    CAST(event_date AS DATE) AS event_date,
    COALESCE(active_users, 0) AS active_users,
    COALESCE(login_count, 0) AS login_count,
    COALESCE(export_count, 0) AS export_count,
    COALESCE(api_calls, 0) AS api_calls
FROM source