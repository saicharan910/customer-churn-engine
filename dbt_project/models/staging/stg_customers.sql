WITH source AS (
    SELECT * FROM "analytics_warehouse"."public"."raw_customers"
)
SELECT
    TRIM(customer_id) AS customer_id,
    TRIM(company_name) AS company_name,
    TRIM(industry) AS industry,
    tier,
    CAST(signup_date AS DATE) AS signup_date
FROM source