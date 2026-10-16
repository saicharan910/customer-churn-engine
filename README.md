# 🛡️ Enterprise Customer Churn & Retention Analytics Engine

An end-to-end analytics engineering platform and executive decision engine designed to detect early B2B SaaS customer churn, track ARR exposure, model cohort retention decay, and recommend targeted Customer Success interventions.

---

## 🏛️ System Architecture & Data Flow

```text
[Synthetic Generator] 
       │ (Pandas / SQLAlchemy)
       ▼
[PostgreSQL 15 (Docker: 5433)]
       │
       ▼  (dbt-postgres 1.11+)
├── Staging Layer (stg_customers, stg_subscriptions, stg_usage_events)
├── Intermediate Layer (int_customer_rfm_metrics, int_usage_sessionized)
└── Marts Layer (dim_customers, mart_churn_risk_scores, fct_monthly_retention)
       │
       ├──► [Great Expectations 1.0+] (Automated Data Quality & Boundary Assertions)
       │
       └──► [Streamlit Enterprise Dashboard] (Telemetry Inspection, Risk Scoring, Cohort Heatmap)
📦 Project Structure
Plaintext
customer-churn-engine/
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI for ingestion, dbt, and GX
├── analysis/
│   └── validate_expectations.py # Modern GX 1.0+ ephemeral test suite
├── dashboard/
│   └── app.py                  # Streamlit enterprise decision terminal
├── data/
│   ├── generate_data.py        # Idempotent synthetic data generator
│   └── test_output/            # Audited candidate CSV datasets
├── dbt_project/
│   ├── models/
│   │   ├── staging/            # Base source views with schema assertions
│   │   ├── intermediate/       # Sessionization & RFM scoring models
│   │   └── marts/              # Customer dimensions, risk tiers & cohort matrices
│   ├── dbt_project.yml
│   └── profiles.yml
├── docker-compose.yml          # Containerized PostgreSQL service
├── requirements.txt
└── README.md
🚀 Quickstart Guide
1. Environment & Infrastructure Setup
PowerShell
# Start PostgreSQL warehouse
docker-compose up -d postgres

# Install dependencies
pip install -r requirements.txt
2. Ingest Synthetic Telemetry
PowerShell
python data/generate_data.py
3. Run Transformations & Quality Tests
PowerShell
cd dbt_project
dbt run --profiles-dir .
dbt test --profiles-dir .
cd ..
4. Execute Great Expectations Assertions
PowerShell
python analysis/validate_expectations.py
5. Launch Executive Dashboard
PowerShell
python -m streamlit run dashboard/app.py
📊 Analytical Methodology
RFM Segmentation: Uses PostgreSQL window functions (NTILE(5)) to dynamically score accounts across Recency (days since last login), Frequency (distinct active days), and Monetary Value (total MRR).

Session Cycle Inactivity: Tracks usage gaps exceeding 7 days across event logs to detect decaying engagement patterns before contract renewal windows.

Risk Classification Rules:

Critical: RFM recency/frequency score <= 2 with upcoming contract renewal within 60 days.

High: RFM recency <= 2 or frequency <= 3 with renewal within 90 days.

Medium: RFM recency <= 3.

Low: Healthy accounts actively utilizing the platform.

Cohort Retention: Tracks month-over-month active logins partitioned by customer signup month to expose true organic SaaS retention decay curves.
