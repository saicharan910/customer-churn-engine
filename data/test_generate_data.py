

import datetime
import random
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)


def generate_test_data(num_customers=500):
    output_dir = Path(__file__).resolve().parent / "test_output"
    output_dir.mkdir(exist_ok=True)

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=180)

    customer_ids = [f"CUST-{1000 + i}" for i in range(num_customers)]
    tiers = np.random.choice(
        ["Startup", "Growth", "Enterprise"],
        size=num_customers,
        p=[0.50, 0.35, 0.15],
    )
    signup_dates = [
        fake.date_between(start_date="-2y", end_date="-6m")
        for _ in range(num_customers)
    ]

    customers = pd.DataFrame({
        "customer_id": customer_ids,
        "tier": tiers,
        "signup_date": pd.to_datetime(signup_dates),
    })

    usage_events = []

    for _, customer in customers.iterrows():
        customer_id = customer["customer_id"]
        signup_date = customer["signup_date"].date()
        tier = customer["tier"]

        customer_start = max(start_date, signup_date)
        base_logins = {
            "Startup": 8,
            "Growth": 25,
            "Enterprise": 70,
        }[tier]

        behavior = random.choices(
            ["healthy", "declining", "churned"],
            weights=[0.55, 0.25, 0.20],
            k=1,
        )[0]

        # Churned customers stop using the product before today.
        churn_date = None
        if behavior == "churned":
            days_before_today = random.randint(30, 150)
            churn_date = today - datetime.timedelta(days=days_before_today)

        current_date = customer_start

        while current_date <= today:
            if churn_date is not None and current_date >= churn_date:
                break

            days_since_signup = (current_date - signup_date).days

            if behavior == "healthy":
                activity_probability = 0.70
                login_factor = 1.0
            elif behavior == "declining":
                decline = min(days_since_signup / 180, 0.85)
                activity_probability = max(0.15, 0.65 * (1 - decline))
                login_factor = max(0.20, 1 - decline)
            else:
                activity_probability = 0.65
                login_factor = 1.0

            if random.random() < activity_probability:
                logins = int(np.random.poisson(base_logins) * login_factor)

                if logins > 0:
                    usage_events.append({
                        "event_id": fake.uuid4(),
                        "customer_id": customer_id,
                        "event_date": current_date,
                        "login_count": logins,
                    })

            current_date += datetime.timedelta(days=1)

    usage = pd.DataFrame(
        usage_events,
        columns=["event_id", "customer_id", "event_date", "login_count"],
    )

    customers.to_csv(output_dir / "test_customers.csv", index=False)
    usage.to_csv(output_dir / "test_usage_events.csv", index=False)

    usage["event_date"] = pd.to_datetime(usage["event_date"])
    usage["event_month"] = usage["event_date"].dt.to_period("M")
    customers["signup_month"] = customers["signup_date"].dt.to_period("M")

    cohort_sizes = customers.groupby("signup_month")["customer_id"].nunique()
    monthly_active = (
        usage.merge(
            customers[["customer_id", "signup_month"]],
            on="customer_id",
            how="inner",
        )
        .groupby(["signup_month", "event_month"])["customer_id"]
        .nunique()
        .reset_index(name="active_customers")
    )

    monthly_active["period_number"] = (
        (monthly_active["event_month"].dt.year
         - monthly_active["signup_month"].dt.year) * 12
        + monthly_active["event_month"].dt.month
        - monthly_active["signup_month"].dt.month
    )

    monthly_active = monthly_active[
        monthly_active["period_number"] >= 0
    ].copy()

    monthly_active["cohort_size"] = monthly_active["signup_month"].map(
        cohort_sizes
    )
    monthly_active["retention_percentage"] = (
        monthly_active["active_customers"]
        / monthly_active["cohort_size"] * 100
    ).round(2)

    monthly_active.to_csv(
        output_dir / "test_retention_diagnostic.csv",
        index=False,
    )

    print("CSV test complete. PostgreSQL was not modified.")
    print(f"Customers: {len(customers)}")
    print(f"Usage events: {len(usage)}")
    print(f"Customers with no usage: "
          f"{customers['customer_id'].isin(usage['customer_id']).eq(False).sum()}")
    print("\nMonthly active customers:")
    print(
        usage.groupby("event_month")["customer_id"]
        .nunique()
        .to_string()
    )
    print("\nRetention distribution:")
    print(
        monthly_active["retention_percentage"]
        .describe()
        .round(2)
        .to_string()
    )
    print("\nRetention values by cohort and period:")
    print(
        monthly_active[
            ["signup_month", "period_number", "active_customers",
             "cohort_size", "retention_percentage"]
        ].to_string(index=False)
    )
    print(f"\nCSV output folder: {output_dir}")


if __name__ == "__main__":
    generate_test_data()

