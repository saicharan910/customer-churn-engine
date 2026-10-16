WITH observation_bounds AS (
    SELECT
        DATE_TRUNC('month', CURRENT_DATE - INTERVAL '180 days')::DATE AS observation_start_month,
        DATE_TRUNC('month', CURRENT_DATE)::DATE AS current_month
),

cohort_items AS (
    SELECT
        c.customer_id,
        DATE_TRUNC('month', c.signup_date)::DATE AS cohort_month
    FROM {{ ref('stg_customers') }} c
    CROSS JOIN observation_bounds b
    WHERE c.signup_date IS NOT NULL
      AND c.signup_date <= CURRENT_DATE
      -- Fix: restrict cohorts to observable activity window so unobserved historical users don't distort denominators
      AND c.signup_date >= b.observation_start_month
),

cohort_size AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS total_cohort_users
    FROM cohort_items
    GROUP BY cohort_month
),

monthly_usage AS (
    SELECT DISTINCT
        customer_id,
        DATE_TRUNC('month', event_date)::DATE AS activity_month
    FROM {{ ref('stg_usage_events') }}
    WHERE event_date IS NOT NULL
),

cohort_activity AS (
    SELECT
        c.cohort_month,
        m.activity_month,
        COUNT(DISTINCT m.customer_id) AS active_users
    FROM cohort_items c
    INNER JOIN monthly_usage m
        ON m.customer_id = c.customer_id
       AND m.activity_month >= c.cohort_month
    GROUP BY
        c.cohort_month,
        m.activity_month
),

observable_months AS (
    SELECT
        GENERATE_SERIES(
            b.observation_start_month,
            b.current_month,
            INTERVAL '1 month'
        )::DATE AS activity_month
    FROM observation_bounds b
),

cohort_month_grid AS (
    SELECT
        cs.cohort_month,
        om.activity_month,
        cs.total_cohort_users
    FROM cohort_size cs
    INNER JOIN observable_months om
        ON om.activity_month >= cs.cohort_month
),

retention_matrix AS (
    SELECT
        g.cohort_month,
        g.activity_month,
        (
            (EXTRACT(YEAR FROM g.activity_month) - EXTRACT(YEAR FROM g.cohort_month)) * 12
            + EXTRACT(MONTH FROM g.activity_month) - EXTRACT(MONTH FROM g.cohort_month)
        )::INTEGER AS period_number,
        COALESCE(a.active_users, 0) AS active_users,
        g.total_cohort_users
    FROM cohort_month_grid g
    LEFT JOIN cohort_activity a
        ON a.cohort_month = g.cohort_month
       AND a.activity_month = g.activity_month
)

SELECT
    cohort_month,
    activity_month,
    period_number,
    active_users,
    total_cohort_users,
    ROUND(
        100.0 * active_users / NULLIF(total_cohort_users, 0),
        2
    ) AS retention_percentage
FROM retention_matrix
ORDER BY cohort_month, period_number