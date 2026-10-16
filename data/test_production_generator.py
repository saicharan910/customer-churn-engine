

import datetime
import random
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()

OUTPUT_DIR = Path(__file__).resolve().parent / "test_output"
NUM_CUSTOMERS = 500
SEED = 42


def generate_csv_datasets():
    random.seed(SEED)
    np.random.seed(SEED)
    Faker.seed(SEED)
    fake.seed_instance(SEED)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today()
    observation_start = today - datetime.timedelta(days=180)

    # ---------------------------------------------------------
    # 1. Generate customers
    # ---------------------------------------------------------
    customer_ids = [
        f"CUST-{1000 + i}" for i in range(NUM_CUSTOMERS)
    ]

    tiers = np.random.choice(
        ["Startup", "Growth", "Enterprise"],
        size=NUM_CUSTOMERS,
        p=[0.50, 0.35, 0.15],
    )

    signup_dates = [
        fake.date_between(start_date="-2y", end_date="today")
        for _ in customer_ids
    ]

    customers = pd.DataFrame({
        "customer_id": customer_ids,
        "company_name": [
            fake.company() for _ in customer_ids
        ],
        "industry": np.random.choice(
            [
                "Fintech",
                "Healthtech",
                "DevOps",
                "EdTech",
                "E-Commerce",
            ],
            size=NUM_CUSTOMERS,
        ),
        "tier": tiers,
        "signup_date": pd.to_datetime(signup_dates),
    })

    # ---------------------------------------------------------
    # 2. Generate subscriptions and customer behavior
    # ---------------------------------------------------------
    base_mrr = {
        "Startup": 299,
        "Growth": 899,
        "Enterprise": 2499,
    }

    subscriptions = []
    behavior_by_customer = {}

    for _, customer in customers.iterrows():
        customer_id = customer["customer_id"]
        signup_date = customer["signup_date"].date()
        tier = customer["tier"]

        # First annual renewal anniversary.
        renewal_date = (
            pd.Timestamp(signup_date)
            + pd.DateOffset(years=1)
        ).date()

        behavior = random.choices(
            ["healthy", "declining", "churned"],
            weights=[0.55, 0.25, 0.20],
            k=1,
        )[0]

        churn_date = None

        # Churn is permitted only on or after the first renewal.
        # Churn dates must also be before today.
        if behavior == "churned":
            earliest = renewal_date
            latest = today - datetime.timedelta(days=1)

            if earliest <= latest:
                span = (latest - earliest).days

                churn_date = earliest + datetime.timedelta(
                    days=random.randint(0, span)
                )
            else:
                # No valid churn date: retain the customer as active.
                behavior = "healthy"

        if churn_date is not None:
            status = "Churned"
        else:
            status = "Active"

        # Active subscriptions must have a future renewal date.
        # Preserve the annual renewal anniversary.
        if status == "Active":
            while renewal_date <= today:
                renewal_date = (
                    pd.Timestamp(renewal_date)
                    + pd.DateOffset(years=1)
                ).date()

        behavior_by_customer[customer_id] = (
            behavior,
            churn_date,
        )

        subscriptions.append({
            "subscription_id": f"SUB-{customer_id[5:]}",
            "customer_id": customer_id,
            "mrr_amount": round(
                base_mrr[tier] + random.uniform(-50, 150),
                2,
            ),
            "status": status,
            "start_date": signup_date,
            "renewal_date": renewal_date,
            "churn_date": churn_date,
        })

    subscriptions_df = pd.DataFrame(subscriptions)

    # ---------------------------------------------------------
    # 3. Generate daily usage events
    # ---------------------------------------------------------
    base_logins = {
        "Startup": 8,
        "Growth": 25,
        "Enterprise": 70,
    }

    usage_events = []

    for _, customer in customers.iterrows():
        customer_id = customer["customer_id"]
        signup_date = customer["signup_date"].date()
        tier = customer["tier"]

        behavior, churn_date = behavior_by_customer[customer_id]

        # Generate usage only after signup and within the
        # observation window. Do not generate usage after churn.
        current_date = max(observation_start, signup_date)
        stop_date = min(today, churn_date) if churn_date else today

        while current_date <= stop_date:
            days_since_signup = (current_date - signup_date).days

            if behavior == "healthy":
                probability = 0.70
                volume_factor = 1.0

            elif behavior == "declining":
                decline = min(days_since_signup / 240.0, 0.80)

                probability = max(
                    0.15,
                    0.65 * (1 - decline),
                )

                volume_factor = max(
                    0.20,
                    1 - decline,
                )

            else:
                # Churned customers may have usage before churn.
                probability = 0.65
                volume_factor = 1.0

            if random.random() < probability:
                logins = int(
                    np.random.poisson(base_logins[tier])
                    * volume_factor
                )

                # Emit an event only when login activity is > 0.
                if logins > 0:
                    active_users = max(1, int(logins / 3))
                    active_users = min(active_users, logins)

                    usage_events.append({
                        "event_id": fake.uuid4(),
                        "customer_id": customer_id,
                        "event_date": current_date,
                        "active_users": active_users,
                        "login_count": logins,
                        "export_count": int(
                            logins * random.uniform(0.1, 0.4)
                        ),
                        "api_calls": (
                            logins * random.randint(10, 50)
                        ),
                    })

            current_date += datetime.timedelta(days=1)

    usage_df = pd.DataFrame(
        usage_events,
        columns=[
            "event_id",
            "customer_id",
            "event_date",
            "active_users",
            "login_count",
            "export_count",
            "api_calls",
        ],
    )

    # ---------------------------------------------------------
    # 4. Write candidate CSVs only
    # ---------------------------------------------------------
    customers.to_csv(
        OUTPUT_DIR / "candidate_raw_customers.csv",
        index=False,
    )

    subscriptions_df.to_csv(
        OUTPUT_DIR / "candidate_raw_subscriptions.csv",
        index=False,
    )

    usage_df.to_csv(
        OUTPUT_DIR / "candidate_raw_usage_events.csv",
        index=False,
    )

    print("Candidate CSV datasets created.")
    print("PostgreSQL was not modified.")
    print(f"Customers: {len(customers)}")
    print(f"Subscriptions: {len(subscriptions_df)}")
    print(f"Usage events: {len(usage_df)}")
    print(
        "Churned subscriptions: "
        f"{(subscriptions_df['status'] == 'Churned').sum()}"
    )
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_csv_datasets()

