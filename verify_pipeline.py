import os
import json
import pandas as pd

print("==========================================================")
print("END-TO-END PIPELINE & DATA QUALITY VERIFICATION AUDIT")
print("==========================================================")

errors = []

# 1. Check Required Project Files
required_files = [
    "generate_retail_data.py",
    "01_medallion_lakehouse_etl.py",
    "02_warehouse_analytics.sql",
    "02_run_sql_analytics.py",
    "03_powerbi_dax_guide.md",
    "README.md",
]
print("\n[1/5] Checking Project Scripts & Documentation...")
for f in required_files:
    if os.path.exists(f):
        print(f"  OK -> {f}")
    else:
        print(f"  MISSING -> {f}")
        errors.append(f"Missing file: {f}")

# 2. Check Medallion Layer Folders & Audit JSON
print("\n[2/5] Checking Bronze, Silver, and Gold Data Layers...")
audit_path = os.path.join("data", "gold", "etl_audit_summary.json")
if os.path.exists(audit_path):
    with open(audit_path, "r") as f:
        audit = json.load(f)
    print(f"  OK -> Raw Transactions:      {audit['raw_transactions']:,}")
    print(f"  OK -> Duplicates Removed:    {audit['duplicates_removed']:,}")
    print(f"  OK -> Quarantined Rows:      {audit['quarantined_rows']:,}")
    print(f"  OK -> Gold Fact Sales Rows:  {audit['gold_fact_sales_rows']:,}")
    print(f"  OK -> Overall Churn Rate:    {audit['overall_churn_rate_pct']}%")
    
    # Verify exact row reconciliation: raw - duplicates - quarantined == gold_fact_sales
    expected_gold = audit["raw_transactions"] - audit["duplicates_removed"] - audit["quarantined_rows"]
    if expected_gold == audit["gold_fact_sales_rows"]:
        print(f"  PASS -> Row Reconciliation Verified ({audit['raw_transactions']:,} - {audit['duplicates_removed']:,} - {audit['quarantined_rows']:,} = {expected_gold:,})")
    else:
        msg = f"Row mismatch: expected {expected_gold}, got {audit['gold_fact_sales_rows']}"
        print(f"  FAIL -> {msg}")
        errors.append(msg)
else:
    errors.append("Missing data/gold/etl_audit_summary.json")

# 3. Check Star Schema Referential Integrity & Zero Nulls
print("\n[3/5] Checking Gold Star Schema Referential Integrity...")
try:
    fact = pd.read_parquet(os.path.join("data", "gold", "fact_sales.parquet"))
    dim_cust = pd.read_parquet(os.path.join("data", "gold", "dim_customer.parquet"))
    dim_prod = pd.read_parquet(os.path.join("data", "gold", "dim_product.parquet"))
    dim_store = pd.read_parquet(os.path.join("data", "gold", "dim_store.parquet"))
    dim_date = pd.read_parquet(os.path.join("data", "gold", "dim_date.parquet"))

    # Check primary key uniqueness
    assert fact["transaction_id"].is_unique, "Duplicate transaction_id in fact_sales!"
    assert dim_cust["customer_key"].is_unique, "Duplicate customer_key in dim_customer!"
    assert dim_prod["product_key"].is_unique, "Duplicate product_key in dim_product!"
    assert dim_store["store_key"].is_unique, "Duplicate store_key in dim_store!"
    assert dim_date["date_key"].is_unique, "Duplicate date_key in dim_date!"
    print("  PASS -> All Primary & Surrogate Keys are 100% unique")

    # Check zero orphan foreign keys
    assert fact["customer_key"].isin(dim_cust["customer_key"]).all(), "Orphan customer_key found!"
    assert fact["product_key"].isin(dim_prod["product_key"]).all(), "Orphan product_key found!"
    assert fact["store_key"].isin(dim_store["store_key"]).all(), "Orphan store_key found!"
    assert fact["date_key"].isin(dim_date["date_key"]).all(), "Orphan date_key found!"
    print("  PASS -> Zero orphan Foreign Keys across all 4 dimensions")

    # Check zero negative quantities or null revenues
    assert (fact["quantity"] > 0).all(), "Invalid quantity <= 0 found in Gold fact_sales!"
    assert fact["net_revenue"].notna().all(), "Null net_revenue found in Gold fact_sales!"
    print("  PASS -> Financial & Quantity constraints verified (100% valid)")
except Exception as e:
    print(f"  FAIL -> Star Schema Integrity Error: {e}")
    errors.append(str(e))

# 4. Check SQL Analytics Output CSVs
print("\n[4/5] Checking Warehouse SQL Output CSVs...")
sql_outputs = [
    "01_rfm_customer_segments.csv",
    "02_monthly_cohort_retention.csv",
    "03_churn_drivers_by_channel_tier.csv",
    "04_category_performance_kpis.csv",
]
for out_f in sql_outputs:
    p = os.path.join("data", "analytics_outputs", out_f)
    if os.path.exists(p):
        df_tmp = pd.read_csv(p)
        print(f"  OK -> {out_f:<38} ({len(df_tmp)} rows)")
    else:
        print(f"  MISSING -> {out_f}")
        errors.append(f"Missing SQL output: {out_f}")

# 5. Final Verdict
print("\n==========================================================")
if not errors:
    print("ALL CHECKS PASSED! Your pipeline, Star Schema, and SQL outputs are 100% verified.")
else:
    print(f"FOUND {len(errors)} ISSUE(S):")
    for err in errors:
        print(f" - {err}")
print("==========================================================")
