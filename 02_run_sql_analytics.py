import os
import duckdb
import pandas as pd

GOLD_DIR = os.path.join("data", "gold")
OUT_DIR = os.path.join("data", "analytics_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

print("Connecting to local DuckDB Warehouse over Gold Parquet Star Schema...")
con = duckdb.connect(database=":memory:")

# Register Gold Parquet tables as Warehouse Views (mirrors Fabric Warehouse DirectLake)
for tbl in ["fact_sales", "dim_customer", "dim_product", "dim_store", "dim_date"]:
    parquet_path = os.path.join(GOLD_DIR, f"{tbl}.parquet").replace("\\", "/")
    con.execute(f"CREATE VIEW {tbl} AS SELECT * FROM read_parquet('{parquet_path}')")

with open("02_warehouse_analytics.sql", "r") as f:
    raw_sql = f.read()

# Split individual SQL statements cleanly
statements = [s.strip() for s in raw_sql.split(";") if s.strip()]
output_names = [
    "01_rfm_customer_segments.csv",
    "02_monthly_cohort_retention.csv",
    "03_churn_drivers_by_channel_tier.csv",
    "04_category_performance_kpis.csv",
]

for idx, (stmt, out_file) in enumerate(zip(statements, output_names), start=1):
    df_res = con.execute(stmt).df()
    out_path = os.path.join(OUT_DIR, out_file)
    df_res.to_csv(out_path, index=False)
    print(f"\n--- Query {idx}: {out_file} ({len(df_res)} rows) ---")
    print(df_res.head(8).to_string(index=False))

print(f"\nAll 4 T-SQL analytics outputs saved to: {OUT_DIR}")
