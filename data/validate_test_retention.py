
from pathlib import Path
from datetime import date, timedelta

import pandas as pd

folder = Path(__file__).resolve().parent / "test_output"

customers = pd.read_csv(folder / "test_customers.csv")
usage = pd.read_csv(folder / "test_usage_events.csv")

customers["signup_date"] = pd.to_datetime(customers["signup_date"])
customers["signup_month"] = customers["signup_date"].dt.to_period("M")

usage["event_date"] = pd.to_datetime(usage["event_date"])
usage["event_month"] = usage["event_date"].dt.to_period("M")

today = date.today()
observation_start = pd.Period(
    today - timedelta(days=180), freq="M"
)
current_month = pd.Period(today, freq="M")

# All signups are included in each cohort denominator.
cohort_sizes = (
    customers.groupby("signup_month")["customer_id"]
    .nunique()
)

# Attach each active customer to their signup cohort.
events = usage.merge(
    customers[["customer_id", "signup_month"]],
    on="customer_id",
    how="inner",
)

# Do not count activity before signup or outside the
# six-month observation window.
events = events[
    (events["event_month"] >= events["signup_month"])
    & (events["event_month"] >= observation_start)
    & (events["event_month"] <= current_month)
]

active_counts = (
    events.groupby(["signup_month", "event_month"])["customer_id"]
    .nunique()
)

rows = []

for cohort_month, cohort_size in cohort_sizes.items():
    first_observed_month = max(cohort_month, observation_start)

    if first_observed_month > current_month:
        continue

    for activity_month in pd.period_range(
        first_observed_month, current_month, freq="M"
    ):
        active = int(
            active_counts.get((cohort_month, activity_month), 0)
        )

        period_number = (
            (activity_month.year - cohort_month.year) * 12
            + activity_month.month - cohort_month.month
        )

        rows.append({
            "signup_month": str(cohort_month),
            "activity_month": str(activity_month),
            "period_number": period_number,
            "active_customers": active,
            "cohort_size": int(cohort_size),
            "retention_percentage": round(
                active / cohort_size * 100, 2
            ),
        })

matrix = pd.DataFrame(rows)

output_file = folder / "validated_retention_matrix.csv"
matrix.to_csv(output_file, index=False)

print("CSV validation complete. No database was modified.")
print(f"Signup cohorts: {matrix['signup_month'].nunique()}")
print(f"Matrix rows: {len(matrix)}")
print(f"Observation starts: {observation_start}")
print(f"Current month: {current_month}")
print(
    "Retention range: "
    f"{matrix['retention_percentage'].min():.2f}% - "
    f"{matrix['retention_percentage'].max():.2f}%"
)
print(
    "Rows with zero active customers: "
    f"{(matrix['active_customers'] == 0).sum()}"
)
print(
    "Invalid retention values: "
    f"{((matrix['retention_percentage'] < 0) | (matrix['retention_percentage'] > 100)).sum()}"
)

print("\nCohort period-0 retention where observable:")
period_zero = matrix[matrix["period_number"] == 0]
print(
    period_zero[
        ["signup_month", "active_customers", "cohort_size",
         "retention_percentage"]
    ].to_string(index=False)
    if not period_zero.empty
    else "No period-0 cohorts fall within the observation window."
)

print("\nLatest observed retention by signup cohort:")
latest = (
    matrix.sort_values("activity_month")
    .groupby("signup_month", as_index=False)
    .tail(1)
)
print(
    latest[
        ["signup_month", "activity_month", "active_customers",
         "cohort_size", "retention_percentage"]
    ].to_string(index=False)
)

print(f"\nSaved matrix: {output_file}")
