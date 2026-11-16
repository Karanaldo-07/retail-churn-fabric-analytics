# Power BI DirectLake Star Schema & DAX Measures Guide

## 1. Connecting Your Gold Star Schema in Power BI Desktop
1. Open **Power BI Desktop** (free on Windows) -> **Get Data** -> **Text/CSV** (or **Parquet**).
2. Load all 5 Gold Star Schema tables from `data/gold/`:
   - `fact_sales`
   - `dim_customer`
   - `dim_product`
   - `dim_store`
   - `dim_date`
3. Go to **Model View** and verify the **1-to-Many (`1:*`)** single-direction relationships:
   - `dim_date[date_key]` -> `fact_sales[date_key]`
   - `dim_customer[customer_key]` -> `fact_sales[customer_key]`
   - `dim_product[product_key]` -> `fact_sales[product_key]`
   - `dim_store[store_key]` -> `fact_sales[store_key]`
4. Right-click `dim_date` -> **Mark as date table** -> select `full_date`.

---

## 2. Core DAX KPI Measures (`_Measures` Table)
Create a dedicated Measures table (**Home -> Enter Data -> name it `_Measures`**) and add these production DAX formulas:

### Revenue & Profitability KPIs
```dax
Total Net Revenue = 
CALCULATE(
    SUM(fact_sales[net_revenue]),
    fact_sales[order_status] = "Completed"
)

Total Net Profit = 
CALCULATE(
    SUM(fact_sales[net_profit]),
    fact_sales[order_status] = "Completed"
)

Gross Profit Margin % = 
DIVIDE([Total Net Profit], [Total Net Revenue], 0)

Completed Orders = 
CALCULATE(
    DISTINCTCOUNT(fact_sales[transaction_id]),
    fact_sales[order_status] = "Completed"
)

Average Order Value (AOV) = 
DIVIDE([Total Net Revenue], [Completed Orders], 0)

Return Rate % = 
DIVIDE(
    CALCULATE(COUNTROWS(fact_sales), fact_sales[order_status] = "Returned"),
    COUNTROWS(fact_sales),
    0
)
```

### Customer Churn & Retention KPIs
```dax
Total Customers = 
DISTINCTCOUNT(dim_customer[customer_key])

Churned Customers = 
CALCULATE(
    DISTINCTCOUNT(dim_customer[customer_key]),
    dim_customer[is_churned] = 1
)

Active Customers = 
CALCULATE(
    DISTINCTCOUNT(dim_customer[customer_key]),
    dim_customer[is_churned] = 0
)

Customer Churn Rate % = 
DIVIDE([Churned Customers], [Total Customers], 0)

Revenue at Risk (Churned LTV) = 
CALCULATE(
    SUM(dim_customer[lifetime_revenue]),
    dim_customer[is_churned] = 1
)

Avg Customer LTV = 
AVERAGEX(
    dim_customer,
    dim_customer[lifetime_revenue]
)
```

### Time-Intelligence KPIs (MoM Growth)
```dax
Previous Month Revenue = 
CALCULATE(
    [Total Net Revenue],
    PREVIOUSMONTH(dim_date[full_date])
)

MoM Revenue Growth % = 
DIVIDE(
    [Total Net Revenue] - [Previous Month Revenue],
    [Previous Month Revenue],
    0
)
```

---

## 3. Recommended 2-Page Executive Dashboard Layout

### Page 1: Executive Sales & Category Performance
- **Top KPI Cards (5):** `Total Net Revenue`, `Total Net Profit`, `Gross Profit Margin %`, `Average Order Value (AOV)`, `MoM Revenue Growth %`
- **Line & Clustered Column Chart:** Monthly `Total Net Revenue` (bars) & `Gross Profit Margin %` (line) by `dim_date[year_month]`
- **Horizontal Bar Chart:** `Total Net Revenue` & `Return Rate %` by `dim_product[category]` (12 categories)
- **Filled Map / Bar Chart:** `Total Net Revenue` by `dim_store[region]` & `dim_store[city]`
- **Slicers:** `Year`, `Region`, `Product Category`, `Store Tier`

### Page 2: Customer Churn & RFM Retention Analytics
- **Top KPI Cards (4):** `Total Customers`, `Customer Churn Rate %`, `Churned Customers`, `Revenue at Risk (Churned LTV)`
- **Donut / Stacked Bar Chart:** Customer distribution by `dim_customer[churn_status]` (`Active (0-45d)`, `At-Risk (46-90d)`, `Churned (>90d)`)
- **Clustered Bar Chart:** `Customer Churn Rate %` by `dim_customer[acquisition_channel]` & `loyalty_tier`
- **Matrix Visual:** Cohort Retention Heatmap (`signup_cohort` rows vs. retention months) imported from `data/analytics_outputs/02_monthly_cohort_retention.csv`
- **Table Visual:** Top At-Risk High-Value Customers (`customer_id`, `loyalty_tier`, `recency_days`, `total_orders`, `lifetime_revenue`)
