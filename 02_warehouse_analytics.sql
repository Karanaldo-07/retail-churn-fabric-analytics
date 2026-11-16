-- ============================================================================
-- RETAIL SALES & CUSTOMER CHURN WAREHOUSE ANALYTICS (T-SQL / DuckDB Compatible)
-- Star Schema: fact_sales, dim_customer, dim_product, dim_store, dim_date
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. RFM CUSTOMER SEGMENTATION (CTEs + NTILE Window Functions)
-- Calculates Recency (days), Frequency (orders), Monetary (net revenue)
-- ----------------------------------------------------------------------------
WITH customer_rfm_base AS (
    SELECT
        c.customer_key,
        c.customer_id,
        c.loyalty_tier,
        c.acquisition_channel,
        c.recency_days,
        COUNT(DISTINCT f.transaction_id) AS frequency,
        ROUND(SUM(f.net_revenue), 2) AS monetary
    FROM dim_customer c
    LEFT JOIN fact_sales f
        ON c.customer_key = f.customer_key
        AND f.order_status = 'Completed'
    GROUP BY
        c.customer_key,
        c.customer_id,
        c.loyalty_tier,
        c.acquisition_channel,
        c.recency_days
),
rfm_scores AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM customer_rfm_base
),
rfm_segmented AS (
    SELECT
        *,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
            WHEN r_score = 3 AND f_score <= 2 THEN 'Need Attention'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At-Risk High Value'
            ELSE 'Hibernating / Churned'
        END AS rfm_segment
    FROM rfm_scores
)
SELECT
    rfm_segment,
    COUNT(*) AS customer_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_customers,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency), 2) AS avg_orders,
    ROUND(AVG(monetary), 2) AS avg_ltv,
    ROUND(SUM(monetary), 2) AS total_segment_revenue
FROM rfm_segmented
GROUP BY rfm_segment
ORDER BY total_segment_revenue DESC;


-- ----------------------------------------------------------------------------
-- 2. MONTHLY COHORT RETENTION ANALYSIS (CTEs + DATEDIFF / Month Offset)
-- Tracks active customer retention from Month 0 through Month 6
-- ----------------------------------------------------------------------------
WITH cohort_base AS (
    SELECT
        c.customer_key,
        CAST(SUBSTRING(c.signup_cohort, 1, 4) AS INT) * 12 + CAST(SUBSTRING(c.signup_cohort, 6, 2) AS INT) AS cohort_idx,
        c.signup_cohort,
        (d.year * 12 + d.month_num) - (CAST(SUBSTRING(c.signup_cohort, 1, 4) AS INT) * 12 + CAST(SUBSTRING(c.signup_cohort, 6, 2) AS INT)) AS month_number
    FROM dim_customer c
    JOIN fact_sales f
        ON c.customer_key = f.customer_key
        AND f.order_status = 'Completed'
    JOIN dim_date d
        ON f.date_key = d.date_key
    WHERE c.signup_cohort BETWEEN '2025-01' AND '2026-04'
),
cohort_counts AS (
    SELECT
        signup_cohort,
        month_number,
        COUNT(DISTINCT customer_key) AS active_customers
    FROM cohort_base
    WHERE month_number BETWEEN 0 AND 6
    GROUP BY signup_cohort, month_number
),
cohort_sizes AS (
    SELECT
        signup_cohort,
        active_customers AS initial_customers
    FROM cohort_counts
    WHERE month_number = 0
)
SELECT
    cc.signup_cohort,
    cs.initial_customers,
    MAX(CASE WHEN cc.month_number = 0 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m0_pct,
    MAX(CASE WHEN cc.month_number = 1 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m1_pct,
    MAX(CASE WHEN cc.month_number = 2 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m2_pct,
    MAX(CASE WHEN cc.month_number = 3 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m3_pct,
    MAX(CASE WHEN cc.month_number = 4 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m4_pct,
    MAX(CASE WHEN cc.month_number = 5 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m5_pct,
    MAX(CASE WHEN cc.month_number = 6 THEN ROUND(100.0 * cc.active_customers / cs.initial_customers, 1) END) AS m6_pct
FROM cohort_counts cc
JOIN cohort_sizes cs
    ON cc.signup_cohort = cs.signup_cohort
GROUP BY cc.signup_cohort, cs.initial_customers
ORDER BY cc.signup_cohort;


-- ----------------------------------------------------------------------------
-- 3. CHURN DRIVERS BY ACQUISITION CHANNEL & LOYALTY TIER
-- Identifies highest-churn segments and revenue at risk
-- ----------------------------------------------------------------------------
SELECT
    acquisition_channel,
    loyalty_tier,
    COUNT(*) AS total_customers,
    SUM(is_churned) AS churned_customers,
    ROUND(100.0 * SUM(is_churned) / COUNT(*), 2) AS churn_rate_pct,
    ROUND(AVG(lifetime_revenue), 2) AS avg_ltv,
    ROUND(SUM(CASE WHEN is_churned = 1 THEN lifetime_revenue ELSE 0 END), 2) AS churned_historical_revenue
FROM dim_customer
GROUP BY acquisition_channel, loyalty_tier
ORDER BY churn_rate_pct DESC, total_customers DESC;


-- ----------------------------------------------------------------------------
-- 4. CATEGORY & REGIONAL PERFORMANCE WITH MoM GROWTH (LAG Window Function)
-- Evaluates underperforming SKUs, return rates, and gross profit margins
-- ----------------------------------------------------------------------------
WITH category_kpis AS (
    SELECT
        p.category,
        COUNT(DISTINCT f.transaction_id) AS total_orders,
        SUM(CASE WHEN f.order_status = 'Completed' THEN f.quantity ELSE 0 END) AS units_sold,
        ROUND(SUM(CASE WHEN f.order_status = 'Completed' THEN f.net_revenue ELSE 0 END), 2) AS net_revenue,
        ROUND(SUM(f.net_profit), 2) AS net_profit,
        ROUND(100.0 * SUM(CASE WHEN f.order_status = 'Returned' THEN 1 ELSE 0 END) / COUNT(*), 2) AS return_rate_pct
    FROM fact_sales f
    JOIN dim_product p
        ON f.product_key = p.product_key
    GROUP BY p.category
)
SELECT
    category,
    total_orders,
    units_sold,
    net_revenue,
    net_profit,
    ROUND(100.0 * net_profit / NULLIF(net_revenue, 0), 2) AS profit_margin_pct,
    return_rate_pct,
    RANK() OVER (ORDER BY net_revenue DESC) AS revenue_rank
FROM category_kpis
ORDER BY revenue_rank;
