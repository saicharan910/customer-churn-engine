import os
import random
import datetime
import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import create_engine

fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_USER = os.getenv("DB_USER", "analytics_user")
DB_PASS = os.getenv("DB_PASS", "analytics_password")
DB_NAME = os.getenv("DB_NAME", "analytics_warehouse")

ENGINE = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def generate_enterprise_data(num_customers=500):
    print(f"Generating synthetic enterprise dataset for {num_customers} accounts...")

    # 1. Accounts
    customer_ids = [f"CUST-{1000 + i}" for i in range(num_customers)]
    tiers = np.random.choice(["Startup", "Growth", "Enterprise"], size=num_customers, p=[0.5, 0.35, 0.15])
    signup_dates = [fake.date_between(start_date="-2y", end_date="-6m") for _ in range(num_customers)]
    
    df_customers = pd.DataFrame({
        "customer_id": customer_ids,
        "company_name": [fake.company() for _ in range(num_customers)],
        "industry": np.random.choice(["Fintech", "Healthtech", "DevOps", "EdTech", "E-Commerce"], size=num_customers),
        "tier": tiers,
        "signup_date": pd.to_datetime(signup_dates)
    })

    # 2. Subscriptions
    subscriptions = []
    base_mrr = {"Startup": 299, "Growth": 899, "Enterprise": 2499}
    
    for _, row in df_customers.iterrows():
        c_id = row["customer_id"]
        start_d = row["signup_date"]
        tier = row["tier"]
        mrr = base_mrr[tier] + round(np.random.uniform(-50, 150), 2)
        
        # Renewal interval: 1 year
        renewal_d = start_d + pd.DateOffset(years=1)
        
        # Determine status
        is_churned = np.random.choice([True, False], p=[0.22, 0.78])
        status = "Active"
        churn_d = None
        
        if is_churned and renewal_d < pd.Timestamp.now():
            status = "Churned"
            churn_d = renewal_d
        
        subscriptions.append({
            "subscription_id": f"SUB-{c_id[5:]}",
            "customer_id": c_id,
            "mrr_amount": mrr,
            "status": status,
            "start_date": start_d,
            "renewal_date": renewal_d,
            "churn_date": churn_d
        })
    df_subscriptions = pd.DataFrame(subscriptions)

    # 3. Usage Events (Last 180 days)
    usage_events = []
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=180)

    for _, row in df_customers.iterrows():
        c_id = row["customer_id"]
        tier = row["tier"]
        signup_date = pd.Timestamp(row["signup_date"]).date()

        # Never generate activity before customer signup.
        customer_start = max(start_date, signup_date)

        base_logins = {
            "Startup": 8,
            "Growth": 25,
            "Enterprise": 70,
        }[tier]

        # Give customers different engagement patterns.
        engagement_type = np.random.choice(
            ["healthy", "declining", "low"],
            p=[0.55, 0.25, 0.20],
        )

        cur_date = customer_start

        while cur_date <= end_date:
            days_since_signup = (cur_date - signup_date).days
            days_remaining = (end_date - cur_date).days

            # Lower daily activity probability for less-engaged customers.
            activity_probability = {
                "healthy": 0.75,
                "declining": 0.55,
                "low": 0.30,
            }[engagement_type]

            # Declining accounts become less active near the present.
            if engagement_type == "declining":
                decline_factor = max(
                    0.15,
                    1.0 - (days_since_signup / 180.0) * 0.75,
                )
                activity_probability *= decline_factor

            if random.random() < activity_probability:
                logins = int(np.random.poisson(base_logins))

                # Declining and low-engagement accounts have lower usage.
                if engagement_type == "declining":
                    logins = int(logins * 0.6)
                elif engagement_type == "low":
                    logins = int(logins * 0.3)

                # Do not create active users when there are no logins.
                active_users = min(
                    logins,
                    max(0, int(logins / 3)),
                )

                usage_events.append({
                    "event_id": fake.uuid4(),
                    "customer_id": c_id,
                    "event_date": cur_date,
                    "active_users": active_users,
                    "login_count": logins,
                    "export_count": int(
                        logins * np.random.uniform(0.1, 0.4)
                    ),
                    "api_calls": logins * random.randint(10, 50),
                })

            cur_date += datetime.timedelta(days=1)

    df_usage = pd.DataFrame(usage_events)



    # Export to Postgres
    with ENGINE.begin() as conn:
        df_customers.to_sql("raw_customers", conn, if_exists="replace", index=False)
        df_subscriptions.to_sql("raw_subscriptions", conn, if_exists="replace", index=False)
        df_usage.to_sql("raw_usage_events", conn, if_exists="replace", index=False)
    
    print("Ingestion complete: raw_customers, raw_subscriptions, and raw_usage_events loaded.")

if __name__ == "__main__":
    generate_enterprise_data()