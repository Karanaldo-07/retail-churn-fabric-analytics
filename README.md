# End-to-End Retail Sales & Customer Churn Analytics (Microsoft Fabric & Power BI)

[![Microsoft Fabric](https://img.shields.io/badge/Microsoft%20Fabric-Lakehouse%20%26%20Warehouse-0078D4?logo=microsoft)](https://learn.microsoft.com/en-us/fabric/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![SQL](https://img.shields.io/badge/SQL-T--SQL%20%2F%20DuckDB-CC2927?logo=microsoftsqlserver&logoColor=white)](https://learn.microsoft.com/en-us/sql/)
[![Power BI](https://img.shields.io/badge/Power%20BI-DirectLake%20%26%20DAX-F2C811?logo=powerbi&logoColor=black)](https://powerbi.microsoft.com/)

## Project Overview
An end-to-end data engineering and business intelligence solution built on the **Medallion Lakehouse Architecture (`Bronze -> Silver -> Gold Star Schema`)**. This pipeline ingests **152,000+ multi-store retail transactions** across **15 stores**, **240 SKUs (12 product categories)**, and **25,000 customers**, enforces automated data quality quarantine rules, models a dimensional **Star Schema**, executes **T-SQL RFM & Cohort Retention** analytics, and powers an executive **Power BI** churn dashboard.

---

## Architecture Pipeline

```text
+-------------------+      +---------------------+      +-----------------------+      +-------------------------+
|   RAW SOURCES     | ---> |    BRONZE LAYER     | ---> |     SILVER LAYER      | ---> |       GOLD LAYER        |
| (152K+ CSV Rows)  |      | (Parquet + Audit    |      | (Deduplicated, Null   |      | (Dimensional Star       |
| stores, products, |      |  Metadata)          |      |  Quarantine, Metrics) |      |  Schema: Parquet & CSV) |
| customers, txns   |      +---------------------+      +-----------------------+      +-------------------------+
                                                                                                    |
                                                                                                    v
+-------------------+      +---------------------+      +-----------------------+      +-------------------------+
| POWER BI DASHBOARD| <--- |  DAX KPI MEASURES   | <--- |  T-SQL / DUCKDB       | <--- |  DIRECTLAKE / SQL       |
| (Sales & Churn    |      | (Churn %, LTV, AOV, |      |  WAREHOUSE QUERIES    |      |  ANALYTICS ENDPOINT     |
|  Executive Views) |      |  MoM Growth %)      |      | (RFM, Cohort, Margin) |      |                         |
+-------------------+      +---------------------+      +-----------------------+      +-------------------------+
```

---

## Key Technical Highlights
- **Medallion Data Engineering (`01_medallion_lakehouse_etl.py`):**
  - **Bronze Layer:** Ingests raw operational files into columnar Parquet format with `_ingested_at` and `_source_file` lineage columns.
  - **Silver Layer:** Removes exact duplicate `transaction_id` records, isolates invalid quantities (`<= 0`) and missing `store_id` records into a `quarantined_transactions.csv` audit log, standardizes customer demographics, and computes transaction-level `net_revenue` and `net_profit`.
  - **Gold Layer:** Builds a clean Star Schema (`fact_sales`, `dim_customer`, `dim_product`, `dim_store`, `dim_date`) with surrogate keys and a `>90-day` inactivity churn classification rule.
- **Warehouse SQL Analytics (`02_warehouse_analytics.sql`):**
  - **RFM Segmentation:** Uses `NTILE(5)` window functions across Recency, Frequency, and Monetary metrics to classify customers into *Champions, Loyal Customers, Recent/Promising, Need Attention, At-Risk High Value,* and *Hibernating/Churned*.
  - **Cohort Retention Matrix:** Tracks Month 0 through Month 6 customer retention rates across monthly signup cohorts.
  - **Churn & Category Attribution:** Pinpoints high-churn acquisition channels, loyalty tier drop-offs, and SKU return rates across 12 product categories.
- **Power BI & DAX (`03_powerbi_dax_guide.md`):**
  - Implements Star Schema modeling with custom DAX measures (`Customer Churn Rate %`, `Revenue at Risk`, `Gross Profit Margin %`, `MoM Revenue Growth %`).

---

## Repository Structure
```text
retail-churn-fabric-analytics/
├── generate_retail_data.py          # Synthetic 152K+ row multi-store retail data generator
├── 01_medallion_lakehouse_etl.py    # Bronze -> Silver -> Gold Star Schema ETL pipeline
├── 02_warehouse_analytics.sql       # T-SQL / DuckDB queries (RFM, Cohorts, Churn, Margins)
├── 02_run_sql_analytics.py          # Zero-copy Parquet SQL warehouse execution script
├── 03_powerbi_dax_guide.md          # Power BI relationship model, DAX formulas & layout guide
├── data/
│   ├── gold/etl_audit_summary.json  # Automated pipeline row counts & data quality audit
│   └── analytics_outputs/           # Exported SQL analytical tables (RFM, Cohorts, Churn)
└── README.md
```

---

## How to Run Locally
```bash
# 1. Install dependencies
pip install pandas numpy pyarrow duckdb

# 2. Generate 152,000+ raw retail records
python generate_retail_data.py

# 3. Execute Bronze -> Silver -> Gold Medallion ETL pipeline
python 01_medallion_lakehouse_etl.py

# 4. Run Warehouse SQL queries (RFM, Cohort Retention, Churn Drivers)
python 02_run_sql_analytics.py
```
