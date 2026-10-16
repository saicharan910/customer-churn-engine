import os
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text


# --------------------------------------------------
# Page Configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Enterprise Churn & Retention Analytics",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# Custom Styling (Crisp Professional Enterprise Light Aesthetic)
# --------------------------------------------------
st.markdown(
    """
    <style>
        .stApp {
            background-color: #FFFFFF !important;
            color: #0F172A !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        h1, h2, h3, h4, p, span, label {
            color: #0F172A !important;
        }

        div[data-testid="stMetric"] {
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 6px !important;
            padding: 14px 18px !important;
        }

        [data-testid="stMetricValue"] {
            font-size: clamp(1.15rem, 2vw, 1.6rem);
            font-weight: 700 !important;
            color: #0F172A !important;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            color: #475569 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        hr {
            border: 0;
            border-top: 1px solid #E2E8F0 !important;
            margin: 1.5rem 0 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Database Configuration (Robust Cloud & Local Resolution)
# --------------------------------------------------
if "DATABASE_URL" in st.secrets:
    DB_URL = st.secrets["DATABASE_URL"]
else:
    DB_USER = os.getenv("DB_USER", "analytics_user")
    DB_PASS = os.getenv("DB_PASS", "analytics_password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5433")
    DB_NAME = os.getenv("DB_NAME", "analytics_warehouse")

    user = quote_plus(DB_USER)
    password = quote_plus(DB_PASS)
    DB_URL = f"postgresql+psycopg2://{user}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


@st.cache_resource
def get_db_engine():
    return create_engine(
        DB_URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )


@st.cache_data(ttl=300)
def load_data():
    engine = get_db_engine()

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

        # Load tables safely (falling back if schema prefix isn't required by Postgres)
        try:
            churn_df = pd.read_sql("SELECT * FROM public.mart_churn_risk_scores", con=connection)
        except Exception:
            churn_df = pd.read_sql("SELECT * FROM mart_churn_risk_scores", con=connection)

        try:
            retention_df = pd.read_sql("SELECT * FROM public.fct_monthly_retention", con=connection)
        except Exception:
            retention_df = pd.read_sql("SELECT * FROM fct_monthly_retention", con=connection)

        try:
            customer_dim = pd.read_sql("SELECT * FROM public.dim_customers", con=connection)
        except Exception:
            customer_dim = pd.read_sql("SELECT * FROM dim_customers", con=connection)

    return churn_df, retention_df, customer_dim


try:
    churn_df, retention_df, customer_dim = load_data()
except Exception as exc:
    st.error("Unable to load dashboard data from PostgreSQL.")
    st.exception(exc)
    st.stop()


# --------------------------------------------------
# Validate Required Columns
# --------------------------------------------------
required_churn_columns = {
    "tier",
    "risk_tier",
    "arr",
    "company_name",
    "days_until_renewal",
    "recency_days",
    "frequency_score",
}

required_customer_columns = {
    "subscription_status",
    "arr",
}

required_retention_columns = {
    "cohort_month",
    "period_number",
    "retention_percentage",
}

missing_churn = required_churn_columns - set(churn_df.columns)
missing_customer = required_customer_columns - set(customer_dim.columns)
missing_retention = required_retention_columns - set(retention_df.columns)

if missing_churn or missing_customer or missing_retention:
    st.error("Database models are missing required columns.")

    if missing_churn:
        st.write("Churn model:", sorted(missing_churn))

    if missing_customer:
        st.write("Customer dimension:", sorted(missing_customer))

    if missing_retention:
        st.write("Retention model:", sorted(missing_retention))

    st.stop()

if churn_df.empty:
    st.warning("No churn-risk records are available.")
    st.stop()

# Normalize fields used in filters and calculations.
churn_df["arr"] = pd.to_numeric(churn_df["arr"], errors="coerce")
customer_dim["arr"] = pd.to_numeric(
    customer_dim["arr"], errors="coerce"
)

churn_df["risk_tier"] = churn_df["risk_tier"].astype("string").str.strip()
churn_df["tier"] = churn_df["tier"].astype("string").str.strip()


# --------------------------------------------------
# Sidebar Filters
# --------------------------------------------------
st.sidebar.title("🎛️ Control Center")
st.sidebar.caption("Filter and drill down across enterprise accounts.")

available_tiers = sorted(churn_df["tier"].dropna().unique().tolist())

risk_order = ["Critical", "High", "Medium", "Low"]
available_risks = [
    risk for risk in risk_order
    if risk in churn_df["risk_tier"].dropna().unique()
]

selected_tiers = st.sidebar.multiselect(
    "Customer Tier",
    options=available_tiers,
    default=available_tiers,
)

selected_risks = st.sidebar.multiselect(
    "Risk Classification",
    options=available_risks,
    default=[r for r in ["Critical", "High"] if r in available_risks],
)

valid_arr = churn_df["arr"].dropna()

if valid_arr.empty:
    st.error("The churn model contains no valid ARR values.")
    st.stop()

max_arr = max(0.0, float(valid_arr.max()))

selected_arr_range = st.sidebar.slider(
    "ARR Threshold ($)",
    min_value=0.0,
    max_value=max_arr if max_arr > 0 else 1.0,
    value=(0.0, max_arr if max_arr > 0 else 1.0),
    step=max(max_arr / 100, 1.0),
    format="$%.0f",
)

filtered_risk = churn_df[
    churn_df["tier"].isin(selected_tiers)
    & churn_df["risk_tier"].isin(selected_risks)
    & churn_df["arr"].between(
        selected_arr_range[0],
        selected_arr_range[1],
    )
].copy()


# --------------------------------------------------
# Header and KPIs
# --------------------------------------------------
st.title("🛡️ Enterprise Churn Prevention & Retention Engine")
st.caption(
    "Executive decision support and account-level telemetry "
    "tracking ARR exposure."
)

active_customers = customer_dim[
    customer_dim["subscription_status"].astype("string").str.strip().str.casefold()
    == "active"
]

total_arr = active_customers["arr"].sum()

critical_df = churn_df[churn_df["risk_tier"] == "Critical"]
high_df = churn_df[churn_df["risk_tier"] == "High"]

critical_arr = critical_df["arr"].sum()
critical_count = len(critical_df)
high_arr = high_df["arr"].sum()

risk_pct = (
    critical_arr / total_arr * 100
    if pd.notna(total_arr) and total_arr > 0
    else 0.0
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Active ARR",
    f"${total_arr:,.0f}",
)

col2.metric(
    "Critical Risk ARR",
    f"${critical_arr:,.0f}",
    help=f"Critical-risk ARR is {risk_pct:.1f}% of active customer ARR.",
)

col3.metric(
    "High Risk ARR",
    f"${high_arr:,.0f}",
)

col4.metric(
    label="Action Required Accounts",
    value=f"{critical_count:,}",
    help="Number of customer records classified as Critical risk."
)

st.divider()


# --------------------------------------------------
# Tabs
# --------------------------------------------------
tab_risk, tab_analytics, tab_retention = st.tabs(
    [
        "⚡ Priority Intervention Queue",
        "📊 Exposure Breakdown & Distribution",
        "📈 Cohort Retention Matrix",
    ]
)


# --------------------------------------------------
# TAB 1: Priority Intervention Queue
# --------------------------------------------------
with tab_risk:
    st.subheader("Account Action List")

    st.write(
        f"Showing **{len(filtered_risk):,}** accounts matching "
        "the current filters."
    )

    st.download_button(
        label="📥 Export Target Accounts to CSV",
        data=filtered_risk.to_csv(index=False).encode("utf-8"),
        file_name="churn_intervention_targets.csv",
        mime="text/csv",
    )

    if filtered_risk.empty:
        st.info(
            "No accounts match the selected filters. "
            "Adjust the filters in the sidebar."
        )
    else:
        available_sort_columns = [
            column
            for column in [
                "arr",
                "days_until_renewal",
                "recency_days",
            ]
            if column in filtered_risk.columns
        ]

        sort_col = st.selectbox(
            "Sort list by",
            available_sort_columns,
            index=0,
        )

        display_df = filtered_risk.sort_values(
            by=sort_col,
            ascending=(sort_col != "arr"),
            na_position="last",
        )

        display_cols = [
            column
            for column in [
                "company_name",
                "tier",
                "arr",
                "days_until_renewal",
                "recency_days",
                "frequency_score",
                "usage_growth_rate",
                "risk_tier",
            ]
            if column in display_df.columns
        ]

        formatters = {
            "arr": "${:,.2f}",
            "days_until_renewal": "{:.0f} days",
            "recency_days": "{:.0f} days",
            "frequency_score": "{:.0f} events",
            "usage_growth_rate": "{:+.1f}%",
        }

        st.dataframe(
            display_df[display_cols].style.format(
                {
                    column: formatter
                    for column, formatter in formatters.items()
                    if column in display_cols
                },
                na_rep="—",
            ),
            use_container_width=True,
            height=380,
        )

        st.markdown("### 🔍 Customer Telemetry Inspection")

        if "company_name" in display_df.columns:
            account_names = (
                display_df["company_name"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            if account_names:
                selected_account = st.selectbox(
                    "Select an account for deep dive",
                    account_names,
                )

                account_rows = display_df[
                    display_df["company_name"].astype(str)
                    == selected_account
                ]

                if not account_rows.empty:
                    acct = account_rows.iloc[0]

                    c1, c2, c3, c4 = st.columns(4)

                    c1.write(f"**Tier:** {acct['tier']}")
                    c2.write(f"**Contract ARR:** ${acct['arr']:,.2f}")

                    recency = acct.get("recency_days")
                    if pd.notna(recency):
                        c3.write(f"**Inactivity:** {recency:.0f} days")
                    else:
                        c3.write("**Inactivity:** Unknown")

                    if acct["risk_tier"] == "Critical":
                        action = "Executive escalation and account review"
                    elif acct["risk_tier"] == "High":
                        action = "Priority customer success review"
                    else:
                        action = "Routine customer health review"

                    c4.write(f"**Recommended Action:** {action}")


# --------------------------------------------------
# TAB 2: Exposure Analytics
# --------------------------------------------------
with tab_analytics:
    st.subheader("ARR at Risk by Tier and Risk Classification")

    chart1, chart2 = st.columns(2)

    risk_colors = {
        "Critical": "#DC2626",
        "High": "#EA580C",
        "Medium": "#64748B",
        "Low": "#0284C7",
    }

    with chart1:
        tier_summary = (
            churn_df.groupby(
                ["tier", "risk_tier"],
                dropna=False,
            )["arr"]
            .sum()
            .reset_index()
        )

        if tier_summary.empty:
            st.info("No data is available for the tier exposure chart.")
        else:
            fig_bar = px.bar(
                tier_summary,
                x="tier",
                y="arr",
                color="risk_tier",
                title="ARR Exposure by Subscription Tier",
                color_discrete_map=risk_colors,
                barmode="stack",
                labels={
                    "arr": "Annual Recurring Revenue ($)",
                    "tier": "Customer Tier",
                    "risk_tier": "Risk Classification",
                },
            )

            fig_bar.update_layout(
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font_color="#0F172A",
            )

            st.plotly_chart(
                fig_bar,
                use_container_width=True,
            )

    with chart2:
        risk_summary = (
            churn_df.groupby("risk_tier", dropna=False)["arr"]
            .sum()
            .reset_index()
        )

        if risk_summary.empty:
            st.info("No data is available for the risk distribution chart.")
        else:
            fig_donut = px.pie(
                risk_summary,
                values="arr",
                names="risk_tier",
                title="Portfolio ARR Distribution by Risk Tier",
                hole=0.45,
                color="risk_tier",
                color_discrete_map=risk_colors,
            )

            fig_donut.update_layout(
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font_color="#0F172A",
            )

            st.plotly_chart(
                fig_donut,
                use_container_width=True,
            )


# --------------------------------------------------
# TAB 3: Cohort Retention Matrix
# --------------------------------------------------
with tab_retention:
    st.subheader("Product Usage Cohort Heatmap")
    st.caption(
        "Percentage of acquired cohorts maintaining product activity "
        "across subsequent calendar months."
    )

    retention_df["retention_percentage"] = pd.to_numeric(
        retention_df["retention_percentage"],
        errors="coerce",
    )

    valid_retention = retention_df.dropna(
        subset=[
            "cohort_month",
            "period_number",
            "retention_percentage",
        ]
    )

    if valid_retention.empty:
        st.info("No valid retention data is available for the heatmap.")
    else:
        retention_pivot = valid_retention.pivot_table(
            index="cohort_month",
            columns="period_number",
            values="retention_percentage",
            aggfunc="mean",
        )

        if retention_pivot.empty:
            st.info("The retention matrix contains no plottable values.")
        else:
            cohort_labels = [
                (
                    value.strftime("%b %Y")
                    if hasattr(value, "strftime")
                    else str(value)[:7]
                )
                for value in retention_pivot.index
            ]

            fig_heat = px.imshow(
                retention_pivot,
                labels={
                    "x": "Months Since Signup",
                    "y": "Cohort Acquisition Month",
                    "color": "Retention %",
                },
                x=retention_pivot.columns,
                y=cohort_labels,
                color_continuous_scale=["#F1F5F9", "#94A3B8", "#1E293B"],
                aspect="auto",
                text_auto=".1f",
            )

            fig_heat.update_layout(
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font_color="#0F172A",
                height=450,
            )

            st.plotly_chart(
                fig_heat,
                use_container_width=True,
            )