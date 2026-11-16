import os
import json
import numpy as np
import pandas as pd
from datetime import datetime

RAW_DIR = os.path.join("data", "raw")
BRONZE_DIR = os.path.join("data", "bronze")
SILVER_DIR = os.path.join("data", "silver")
GOLD_DIR = os.path.join("data", "gold")

for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR]:
    os.makedirs(d, exist_ok=True)

print("==========================================================")
print("STAGE 1: BRONZE LAYER INGESTION (Raw CSV -> Bronze Parquet)")
print("==========================================================")

raw_tables = ["stores", "products", "customers", "transactions"]
bronze_dfs = {}

for tbl in raw_tables:
    df = pd.read_csv(os.path.join(RAW_DIR, f"{tbl}.csv"))
    df["_ingested_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["_source_file"] = f"{tbl}.csv"
    df.to_parquet(os.path.join(BRONZE_DIR, f"{tbl}.parquet"), index=False)
    bronze_dfs[tbl] = df
    print(f" [Bronze] {tbl}.parquet written -> {len(df):,} rows")

print("\n==========================================================")
print("STAGE 2: SILVER LAYER CLEANSING & STANDARDIZATION")
print("==========================================================")

# 1. Clean Stores
df_stores_s = bronze_dfs["stores"].drop(columns=["_ingested_at", "_source_file"]).copy()
df_stores_s["store_id"] = df_stores_s["store_id"].str.strip().str.upper()
df_stores_s = df_stores_s.drop_duplicates(subset=["store_id"])

# 2. Clean Products
df_products_s = bronze_dfs["products"].drop(columns=["_ingested_at", "_source_file"]).copy()
df_products_s["product_id"] = df_products_s["product_id"].str.strip().str.upper()
df_products_s["unit_price"] = df_products_s["unit_price"].astype(float)
df_products_s["unit_cost"] = df_products_s["unit_cost"].astype(float)
df_products_s["gross_margin_pct"] = (
    (df_products_s["unit_price"] - df_products_s["unit_cost"]) / df_products_s["unit_price"] * 100
).round(2)
df_products_s = df_products_s.drop_duplicates(subset=["product_id"])

# 3. Clean Customers
df_cust_s = bronze_dfs["customers"].drop(columns=["_ingested_at", "_source_file"]).copy()
df_cust_s["customer_id"] = df_cust_s["customer_id"].str.strip().str.upper()
df_cust_s["signup_date"] = pd.to_datetime(df_cust_s["signup_date"])
df_cust_s["gender"] = df_cust_s["gender"].fillna("Not Disclosed")
df_cust_s["email"] = df_cust_s["email"].fillna("unknown@noemail.local").str.strip().str.lower()
df_cust_s["age_group"] = pd.cut(
    df_cust_s["age"],
    bins=[17, 25, 35, 45, 55, 100],
    labels=["18-25", "26-35", "36-45", "46-55", "56+"],
).astype(str)
df_cust_s = df_cust_s.drop_duplicates(subset=["customer_id"])

# 4. Clean Transactions (Data Quality Rules)
df_txn_raw = bronze_dfs["transactions"].drop(columns=["_ingested_at", "_source_file"]).copy()
initial_txn_count = len(df_txn_raw)

# Rule A: Remove exact duplicate transaction_ids
df_txn_s = df_txn_raw.drop_duplicates(subset=["transaction_id"]).copy()
dups_removed = initial_txn_count - len(df_txn_s)

# Rule B: Quarantine invalid quantities (<= 0) and missing store_ids
invalid_qty_mask = df_txn_s["quantity"] <= 0
null_store_mask = df_txn_s["store_id"].isna() | (df_txn_s["store_id"].astype(str).str.strip() == "")
quarantine_df = df_txn_s[invalid_qty_mask | null_store_mask].copy()
quarantine_df.to_csv(os.path.join(SILVER_DIR, "quarantined_transactions.csv"), index=False)

df_txn_s = df_txn_s[~(invalid_qty_mask | null_store_mask)].copy()
df_txn_s["transaction_date"] = pd.to_datetime(df_txn_s["transaction_date"])
df_txn_s["store_id"] = df_txn_s["store_id"].str.strip().str.upper()
df_txn_s["product_id"] = df_txn_s["product_id"].str.strip().str.upper()
df_txn_s["customer_id"] = df_txn_s["customer_id"].str.strip().str.upper()

# Join product pricing to compute financial metrics
df_txn_s = df_txn_s.merge(
    df_products_s[["product_id", "unit_price", "unit_cost"]],
    on="product_id",
    how="inner",
)
df_txn_s["gross_amount"] = (df_txn_s["quantity"] * df_txn_s["unit_price"]).round(2)
df_txn_s["discount_amount"] = (df_txn_s["gross_amount"] * df_txn_s["discount_pct"]).round(2)
df_txn_s["net_revenue"] = (df_txn_s["gross_amount"] - df_txn_s["discount_amount"]).round(2)
df_txn_s["total_cost"] = (df_txn_s["quantity"] * df_txn_s["unit_cost"]).round(2)
df_txn_s["net_profit"] = np.where(
    df_txn_s["order_status"] == "Completed",
    (df_txn_s["net_revenue"] - df_txn_s["total_cost"]).round(2),
    0.0,
)

# Save Silver Parquet tables
df_stores_s.to_parquet(os.path.join(SILVER_DIR, "stores_clean.parquet"), index=False)
df_products_s.to_parquet(os.path.join(SILVER_DIR, "products_clean.parquet"), index=False)
df_cust_s.to_parquet(os.path.join(SILVER_DIR, "customers_clean.parquet"), index=False)
df_txn_s.to_parquet(os.path.join(SILVER_DIR, "transactions_clean.parquet"), index=False)

print(f" [Silver] Deduplication: removed {dups_removed:,} duplicate transactions")
print(f" [Silver] Data Quality Quarantine: isolated {len(quarantine_df):,} invalid/null rows")
print(f" [Silver] Clean Transactions ready: {len(df_txn_s):,} valid rows")

print("\n==========================================================")
print("STAGE 3: GOLD LAYER DIMENSIONAL STAR SCHEMA MODELING")
print("==========================================================")

# 1. dim_date (2024-01-01 to 2026-12-31)
date_rng = pd.date_range(start="2024-01-01", end="2026-12-31", freq="D")
dim_date = pd.DataFrame({"full_date": date_rng})
dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
dim_date["year"] = dim_date["full_date"].dt.year
dim_date["quarter"] = "Q" + dim_date["full_date"].dt.quarter.astype(str)
dim_date["month_num"] = dim_date["full_date"].dt.month
dim_date["month_name"] = dim_date["full_date"].dt.strftime("%b")
dim_date["year_month"] = dim_date["full_date"].dt.strftime("%Y-%m")
dim_date["day_of_week"] = dim_date["full_date"].dt.strftime("%A")
dim_date["is_weekend"] = dim_date["full_date"].dt.dayofweek.isin([5, 6]).astype(int)
dim_date["full_date"] = dim_date["full_date"].dt.strftime("%Y-%m-%d")

# 2. dim_store
dim_store = df_stores_s.copy()
dim_store.insert(0, "store_key", range(1, len(dim_store) + 1))

# 3. dim_product
dim_product = df_products_s.copy()
dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))

# 4. dim_customer (enriched with Recency, Churn Flag & Signup Cohort)
analysis_cutoff = pd.Timestamp("2026-10-31")
completed_txns = df_txn_s[df_txn_s["order_status"] == "Completed"]

cust_activity = (
    completed_txns.groupby("customer_id")
    .agg(
        first_order_date=("transaction_date", "min"),
        last_order_date=("transaction_date", "max"),
        total_orders=("transaction_id", "count"),
        lifetime_revenue=("net_revenue", "sum"),
    )
    .reset_index()
)

dim_customer = df_cust_s.merge(cust_activity, on="customer_id", how="left")
dim_customer["total_orders"] = dim_customer["total_orders"].fillna(0).astype(int)
dim_customer["lifetime_revenue"] = dim_customer["lifetime_revenue"].fillna(0.0).round(2)
dim_customer["recency_days"] = (
    analysis_cutoff - dim_customer["last_order_date"].fillna(dim_customer["signup_date"])
).dt.days
# Business rule: Customer is Churned if inactive for > 90 days
dim_customer["is_churned"] = np.where(dim_customer["recency_days"] > 90, 1, 0)
dim_customer["churn_status"] = np.where(
    dim_customer["recency_days"] > 90,
    "Churned (>90d)",
    np.where(dim_customer["recency_days"] > 45, "At-Risk (46-90d)", "Active (0-45d)"),
)
dim_customer["signup_cohort"] = dim_customer["signup_date"].dt.strftime("%Y-%m")
dim_customer["signup_date"] = dim_customer["signup_date"].dt.strftime("%Y-%m-%d")
dim_customer["first_order_date"] = dim_customer["first_order_date"].dt.strftime("%Y-%m-%d")
dim_customer["last_order_date"] = dim_customer["last_order_date"].dt.strftime("%Y-%m-%d")
dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))

# 5. fact_sales (Surrogate Keys + Additive Measures)
fact_sales = df_txn_s.copy()
fact_sales["date_key"] = fact_sales["transaction_date"].dt.strftime("%Y%m%d").astype(int)
fact_sales = fact_sales.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="inner")
fact_sales = fact_sales.merge(dim_product[["product_id", "product_key"]], on="product_id", how="inner")
fact_sales = fact_sales.merge(dim_store[["store_id", "store_key"]], on="store_id", how="inner")

fact_cols = [
    "transaction_id",
    "date_key",
    "customer_key",
    "product_key",
    "store_key",
    "order_status",
    "payment_method",
    "quantity",
    "unit_price",
    "discount_pct",
    "gross_amount",
    "discount_amount",
    "net_revenue",
    "total_cost",
    "net_profit",
]
fact_sales = fact_sales[fact_cols]

# Export Gold Star Schema to both Parquet (for Fabric DirectLake) and CSV (for Power BI Desktop / DuckDB)
gold_tables = {
    "dim_date": dim_date,
    "dim_store": dim_store,
    "dim_product": dim_product,
    "dim_customer": dim_customer,
    "fact_sales": fact_sales,
}

for name, df_g in gold_tables.items():
    df_g.to_parquet(os.path.join(GOLD_DIR, f"{name}.parquet"), index=False)
    df_g.to_csv(os.path.join(GOLD_DIR, f"{name}.csv"), index=False)
    print(f" [Gold] {name:<14} -> {len(df_g):>8,} rows (Parquet + CSV)")

# Save ETL pipeline audit summary
audit_summary = {
    "pipeline_run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "raw_transactions": int(initial_txn_count),
    "duplicates_removed": int(dups_removed),
    "quarantined_rows": int(len(quarantine_df)),
    "gold_fact_sales_rows": int(len(fact_sales)),
    "total_customers": int(len(dim_customer)),
    "churned_customers": int(dim_customer["is_churned"].sum()),
    "overall_churn_rate_pct": round(float(dim_customer["is_churned"].mean() * 100), 2),
}
with open(os.path.join(GOLD_DIR, "etl_audit_summary.json"), "w") as f:
    json.dump(audit_summary, f, indent=2)

print("\nGold Star Schema Build Complete! Summary:")
print(json.dumps(audit_summary, indent=2))
