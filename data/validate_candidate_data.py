
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

folder = Path(__file__).resolve().parent / "test_output"

customers = pd.read_csv(folder / "candidate_raw_customers.csv")
subs = pd.read_csv(folder / "candidate_raw_subscriptions.csv")
usage = pd.read_csv(folder / "candidate_raw_usage_events.csv")

errors = []

required_columns = {
    "customers": {
        "customer_id", "company_name", "industry", "tier", "signup_date"
    },
    "subscriptions": {
        "subscription_id", "customer_id", "mrr_amount", "status",
        "start_date", "renewal_date", "churn_date"
    },
    "usage": {
        "event_id", "customer_id", "event_date", "active_users",
        "login_count", "export_count", "api_calls"
    },
}

for name, df, required in [
    ("customers", customers, required_columns["customers"]),
    ("subscriptions", subs, required_columns["subscriptions"]),
    ("usage", usage, required_columns["usage"]),
]:
    missing = required - set(df.columns)
    if missing:
        errors.append(f"{name}: missing columns {sorted(missing)}")

if errors:
    print("SCHEMA VALIDATION FAILED")
    print("\n".join(errors))
    raise SystemExit(1)

for col in ["signup_date"]:
    customers[col] = pd.to_datetime(customers[col], errors="coerce")

for col in ["start_date", "renewal_date", "churn_date"]:
    subs[col] = pd.to_datetime(subs[col], errors="coerce")

usage["event_date"] = pd.to_datetime(usage["event_date"], errors="coerce")

# Unique identifiers and one subscription per customer.
if customers["customer_id"].duplicated().any():
    errors.append("Duplicate customer_id values.")

if subs["subscription_id"].duplicated().any():
    errors.append("Duplicate subscription_id values.")

if subs["customer_id"].duplicated().any():
    errors.append("More than one subscription per customer.")

if usage["event_id"].duplicated().any():
    errors.append("Duplicate event_id values.")

if set(customers["customer_id"]) != set(subs["customer_id"]):
    errors.append("Customer and subscription IDs do not match.")

if not set(usage["customer_id"]).issubset(set(customers["customer_id"])):
    errors.append("Usage contains unknown customer IDs.")

# Subscription dates and status.
if (subs["start_date"] > subs["renewal_date"]).any():
    errors.append("Subscription renewal occurs before start.")

if (subs["start_date"] != subs["customer_id"].map(
    customers.set_index("customer_id")["signup_date"]
)).any():
    errors.append("Subscription start dates differ from signup dates.")

is_churned = subs["status"].eq("Churned")
has_churn_date = subs["churn_date"].notna()

if (is_churned != has_churn_date).any():
    errors.append("Churn status and churn_date are inconsistent.")

if (subs.loc[has_churn_date, "churn_date"]
        < subs.loc[has_churn_date, "start_date"]).any():
    errors.append("Churn date occurs before subscription start.")

if not subs["status"].isin(["Active", "Churned"]).all():
    errors.append("Unexpected subscription status.")

# Usage must be valid and occur after signup, never after churn.
events = usage.merge(
    customers[["customer_id", "signup_date"]],
    on="customer_id",
    how="left",
    validate="many_to_one",
)

events = events.merge(
    subs[["customer_id", "churn_date"]],
    on="customer_id",
    how="left",
    validate="many_to_one",
)

if events["event_date"].isna().any():
    errors.append("Usage contains invalid event dates.")

if (events["event_date"] < events["signup_date"]).any():
    errors.append("Usage occurs before customer signup.")

if (events["event_date"].dt.date > date.today()).any():
    errors.append("Usage contains future-dated events.")

after_churn = (
    events["churn_date"].notna()
    & (events["event_date"] > events["churn_date"])
)
if after_churn.any():
    errors.append(
        f"{int(after_churn.sum())} usage events occur after churn dates."
    )

if (usage["login_count"] <= 0).any():
    errors.append("Usage contains zero or negative login counts.")

if (usage["active_users"] <= 0).any():
    errors.append("Usage contains zero or negative active_users.")

if (usage[["export_count", "api_calls"]] < 0).any().any():
    errors.append("Usage contains negative exports or API calls.")

# Build a complete observable retention matrix.
today = date.today()
observation_start = pd.Period(today - timedelta(days=180), freq="M")
current_month = pd.Period(today, freq="M")

customers["signup_month"] = customers["signup_date"].dt.to_period("M")
usage["event_month"] = usage["event_date"].dt.to_period("M")

cohort_sizes = (
    customers.groupby("signup_month")["customer_id"].nunique()
)

events = usage.merge(
    customers[["customer_id", "signup_month"]],
    on="customer_id",
    how="left",
    validate="many_to_one",
)

events = events[
    (events["event_month"] >= events["signup_month"])
    & (events["event_month"] >= observation_start)
    & (events["event_month"] <= current_month)
]

active_events = events[events["login_count"] > 0]

active_counts = (
    active_events.groupby(["signup_month", "event_month"])["customer_id"]
    .nunique()
)

rows = []

for cohort_month, cohort_size in cohort_sizes.items():
    first_observed = max(cohort_month, observation_start)

    if first_observed > current_month:
        continue

    for activity_month in pd.period_range(
        first_observed, current_month, freq="M"
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

if not matrix.empty:
    if (matrix["retention_percentage"] > 100).any():
        errors.append("Retention exceeds 100%.")

    if (matrix["retention_percentage"] < 0).any():
        errors.append("Retention is below 0%.")

    if (matrix["active_customers"] > matrix["cohort_size"]).any():
        errors.append("Active customers exceed cohort size.")

    # Every observable month must appear once per cohort.
    if matrix.duplicated(["signup_month", "activity_month"]).any():
        errors.append("Duplicate cohort-month rows.")

matrix.to_csv(folder / "validated_candidate_retention.csv", index=False)

print("\n--- Candidate dataset validation ---")
print(f"Customers: {len(customers)}")
print(f"Subscriptions: {len(subs)}")
print(f"Usage events: {len(usage)}")
print(f"Churned subscriptions: {int(is_churned.sum())}")
print(f"Usage events after churn: {int(after_churn.sum())}")
print(f"Observation window: {observation_start} to {current_month}")
print(f"Retention matrix rows: {len(matrix)}")

if not matrix.empty:
    print(
        "Retention range: "
        f"{matrix['retention_percentage'].min():.2f}% to "
        f"{matrix['retention_percentage'].max():.2f}%"
    )
    print(
        "Zero-active cohort-months: "
        f"{int((matrix['active_customers'] == 0).sum())}"
    )
    print(
        "Period-0 retention range: "
        f"{matrix.loc[matrix['period_number'] == 0, 'retention_percentage'].min():.2f}% to "
        f"{matrix.loc[matrix['period_number'] == 0, 'retention_percentage'].max():.2f}%"
    )

print(f"Retention CSV: {folder / 'validated_candidate_retention.csv'}")

if errors:
    print("\nVALIDATION FAILED:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("\nSTRUCTURAL VALIDATION PASSED.")
print("Review the retention distribution before production loading.")
