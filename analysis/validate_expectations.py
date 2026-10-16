import os
import sys
import pandas as pd
from sqlalchemy import create_engine
import great_expectations as gx

# Database configuration
DB_USER = os.getenv("DB_USER", "analytics_user")
DB_PASS = os.getenv("DB_PASS", "analytics_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_NAME = os.getenv("DB_NAME", "analytics_warehouse")


def get_db_connection():
    return create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )


def run_validations():
    print("Executing Great Expectations validation suite...")

    engine = get_db_connection()

    # Load mart analytical data
    query = "SELECT * FROM public.mart_churn_risk_scores"
    df = pd.read_sql(query, con=engine)

    if df.empty:
        raise ValueError(
            "Validation aborted: 'mart_churn_risk_scores' table is empty. Ensure dbt models have run."
        )

    # Initialize Great Expectations context
    context = gx.get_context(mode="ephemeral")

    # Add in-memory Pandas data source
    data_source_name = "postgres_mart_source"
    try:
        data_source = context.data_sources.add_pandas(data_source_name)
    except Exception:
        data_source = context.data_sources.get(data_source_name)

    data_asset_name = "mart_churn_risk_asset"
    try:
        data_asset = data_source.add_dataframe_asset(name=data_asset_name)
    except Exception:
        data_asset = data_source.get_asset(data_asset_name)

    batch_definition_name = "full_batch"
    try:
        batch_definition = data_asset.add_batch_definition_whole_dataframe(
            batch_definition_name
        )
    except Exception:
        batch_definition = data_asset.get_batch_definition(batch_definition_name)

    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    # Define expectation suite
    suite_name = "mart_churn_risk_suite"
    suite = gx.ExpectationSuite(name=suite_name)

    # Business & Data Integrity Assertions
    expectations = [
        # 1. Primary key uniqueness & non-null
        gx.expectations.ExpectColumnValuesToBeUnique(column="customer_id"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id"),
        # 2. Risk tier categorical validity
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="risk_tier",
            value_set=["Critical", "High", "Medium", "Low"],
        ),
        # 3. Monetary value / ARR non-negativity
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="arr", min_value=0, max_value=1_000_000
        ),
        # 4. RFM score ranges [1, 5]
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="r_score", min_value=1, max_value=5
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="f_score", min_value=1, max_value=5
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="m_score", min_value=1, max_value=5
        ),
    ]

    for exp in expectations:
        suite.add_expectation(exp)

    # Run validation against the batch
    validation_results = batch.validate(suite)

    # Evaluate results
    success = validation_results.success
    if not success:
        print("\n--- VALIDATION FAILURES DETECTED ---")
        for res in validation_results.results:
            if not res.success:
                print(f"FAILED: {res.expectation_config.type} on {res.result}")
        sys.exit(1)

    print("All Great Expectations assertions PASSED successfully.")


if __name__ == "__main__":
    run_validations()