import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Set seeds for reproducibility
random.seed(42)
np.random.seed(42)

RAW_DIR = os.path.join("data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

print("1. Generating Stores Dimension (15 stores across 4 regions)...")
stores_data = [
    ("STR-01", "Mumbai Flagship", "West", "Mumbai", "Maharashtra", "Metro"),
    ("STR-02", "Pune Koregaon Park", "West", "Pune", "Maharashtra", "Metro"),
    ("STR-03", "Pune Hinjewadi", "West", "Pune", "Maharashtra", "Urban"),
    ("STR-04", "Ahmedabad SG Highway", "West", "Ahmedabad", "Gujarat", "Metro"),
    ("STR-05", "Bengaluru Indiranagar", "South", "Bengaluru", "Karnataka", "Metro"),
    ("STR-06", "Bengaluru Whitefield", "South", "Bengaluru", "Karnataka", "Metro"),
    ("STR-07", "Hyderabad Banjara Hills", "South", "Hyderabad", "Telangana", "Metro"),
    ("STR-08", "Chennai Anna Nagar", "South", "Chennai", "Tamil Nadu", "Metro"),
    ("STR-09", "Delhi Connaught Place", "North", "New Delhi", "Delhi", "Metro"),
    ("STR-10", "Gurugram Cyber Hub", "North", "Gurugram", "Haryana", "Metro"),
    ("STR-11", "Noida Sector 18", "North", "Noida", "Uttar Pradesh", "Urban"),
    ("STR-12", "Jaipur MI Road", "North", "Jaipur", "Rajasthan", "Tier-2"),
    ("STR-13", "Kolkata Park Street", "East", "Kolkata", "West Bengal", "Metro"),
    ("STR-14", "Bhubaneswar Janpath", "East", "Bhubaneswar", "Odisha", "Tier-2"),
    ("STR-15", "Online E-Commerce Hub", "Pan-India", "Digital", "National", "Digital"),
]
df_stores = pd.DataFrame(
    stores_data,
    columns=["store_id", "store_name", "region", "city", "state", "store_tier"],
)
df_stores.to_csv(os.path.join(RAW_DIR, "stores.csv"), index=False)

print("2. Generating Products Dimension (240 SKUs across 12 categories)...")
categories = [
    ("Electronics", 1200, 45000, 0.22),
    ("Home Appliances", 1500, 35000, 0.25),
    ("Fashion & Apparel", 400, 4500, 0.45),
    ("Footwear", 600, 6000, 0.42),
    ("Groceries & Staples", 80, 1200, 0.18),
    ("Personal Care & Beauty", 150, 2800, 0.48),
    ("Sports & Fitness", 500, 15000, 0.35),
    ("Books & Stationery", 120, 1500, 0.38),
    ("Kitchen & Dining", 250, 8000, 0.36),
    ("Furniture & Decor", 1800, 28000, 0.32),
    ("Baby & Kids", 300, 5500, 0.40),
    ("Automotive Accessories", 250, 7500, 0.34),
]

products_list = []
sku_idx = 1
for cat_name, min_p, max_p, margin in categories:
    for item_num in range(1, 21):  # 20 products per category = 240 SKUs
        unit_price = round(np.random.uniform(min_p, max_p), 2)
        unit_cost = round(unit_price * (1 - margin + np.random.uniform(-0.04, 0.04)), 2)
        products_list.append(
            {
                "product_id": f"PRD-{sku_idx:04d}",
                "product_name": f"{cat_name.split()[0]} Item {item_num:02d}",
                "category": cat_name,
                "unit_price": unit_price,
                "unit_cost": unit_cost,
                "is_active": 1 if np.random.rand() > 0.05 else 0,
            }
        )
        sku_idx += 1

df_products = pd.DataFrame(products_list)
df_products.to_csv(os.path.join(RAW_DIR, "products.csv"), index=False)

print("3. Generating Customers Dimension (25,000 customers with realistic churn behavior)...")
num_customers = 25000
start_signup = datetime(2024, 1, 1)
end_signup = datetime(2026, 9, 30)
signup_days_range = (end_signup - start_signup).days

signup_offsets = np.random.randint(0, signup_days_range, size=num_customers)
signup_dates = [start_signup + timedelta(days=int(d)) for d in signup_offsets]

loyalty_tiers = np.random.choice(
    ["Bronze", "Silver", "Gold", "Platinum"],
    size=num_customers,
    p=[0.50, 0.28, 0.15, 0.07],
)
acquisition_channels = np.random.choice(
    ["Organic Search", "Instagram Ads", "In-Store Walk-in", "Referral", "Email Campaign"],
    size=num_customers,
    p=[0.28, 0.24, 0.26, 0.12, 0.10],
)
home_stores = np.random.choice(df_stores["store_id"].values, size=num_customers)

# Assign hidden behavioral archetype: Active Loyal (45%), At-Risk / Sporadic (25%), Churned (30%)
archetypes = np.random.choice(
    ["loyal", "sporadic", "churned"],
    size=num_customers,
    p=[0.45, 0.25, 0.30],
)

customers_list = []
for i in range(num_customers):
    cid = f"CUST-{i+1:06d}"
    s_date = signup_dates[i]
    arch = archetypes[i]
    tier = loyalty_tiers[i]
    
    # Intentionally inject ~1.5% dirty/missing emails or whitespace for Silver ETL cleansing
    email = f"customer{i+1}@example.com" if np.random.rand() > 0.015 else None
    gender = np.random.choice(["Male", "Female", "Other", None], p=[0.48, 0.47, 0.03, 0.02])
    age = int(np.clip(np.random.normal(34, 10), 18, 72))
    
    customers_list.append(
        {
            "customer_id": cid,
            "signup_date": s_date.strftime("%Y-%m-%d"),
            "gender": gender,
            "age": age,
            "email": email,
            "loyalty_tier": tier,
            "acquisition_channel": acquisition_channels[i],
            "preferred_store_id": home_stores[i],
            "archetype": arch,  # Used only to generate realistic transaction timelines
        }
    )

df_cust_internal = pd.DataFrame(customers_list)
df_cust_raw = df_cust_internal.drop(columns=["archetype"])
df_cust_raw.to_csv(os.path.join(RAW_DIR, "customers.csv"), index=False)

print("4. Generating 155,000+ Retail Transactions (Bronze Layer)...")
analysis_cutoff = datetime(2026, 10, 31)
product_ids = df_products["product_id"].values
product_prices = dict(zip(df_products["product_id"], df_products["unit_price"]))
payment_methods = ["UPI", "Credit Card", "Debit Card", "Cash", "Net Banking"]

transactions = []
tx_counter = 1

for row in df_cust_internal.itertuples(index=False):
    s_date = datetime.strptime(row.signup_date, "%Y-%m-%d")
    arch = row.archetype
    
    # Determine customer's active window end date based on archetype
    if arch == "churned":
        # Stopped buying at least 95 to 360 days before cutoff
        max_active_end = analysis_cutoff - timedelta(days=random.randint(95, 360))
        if max_active_end <= s_date:
            max_active_end = s_date + timedelta(days=random.randint(1, 30))
        n_orders = random.randint(1, 5)
    elif arch == "sporadic":
        max_active_end = analysis_cutoff - timedelta(days=random.randint(45, 110))
        if max_active_end <= s_date:
            max_active_end = analysis_cutoff - timedelta(days=10)
        n_orders = random.randint(2, 7)
    else:  # loyal
        max_active_end = analysis_cutoff - timedelta(days=random.randint(0, 35))
        if max_active_end <= s_date:
            max_active_end = analysis_cutoff
        n_orders = random.randint(4, 14)

    span_days = max(1, (max_active_end - s_date).days)
    order_offsets = sorted(np.random.randint(0, span_days + 1, size=n_orders))

    for offset in order_offsets:
        order_dt = s_date + timedelta(days=int(offset))
        if order_dt > analysis_cutoff:
            order_dt = analysis_cutoff
            
        prod_id = random.choice(product_ids)
        qty = int(np.random.choice([1, 2, 3, 4], p=[0.62, 0.24, 0.10, 0.04]))
        discount_pct = float(np.random.choice([0.0, 0.05, 0.10, 0.15, 0.20], p=[0.45, 0.20, 0.20, 0.10, 0.05]))
        
        # Store is 75% preferred store, 25% another store
        store_id = row.preferred_store_id if random.random() < 0.75 else random.choice(df_stores["store_id"].values)
        pay_method = random.choice(payment_methods)
        order_status = np.random.choice(["Completed", "Returned", "Cancelled"], p=[0.91, 0.05, 0.04])

        # Inject ~0.8% dirty negative/zero quantities or null store_ids for Silver layer data quality checks
        if random.random() < 0.004:
            qty = -1
        if random.random() < 0.004:
            store_id = None

        transactions.append(
            {
                "transaction_id": f"TXN-{tx_counter:07d}",
                "transaction_date": order_dt.strftime("%Y-%m-%d"),
                "customer_id": row.customer_id,
                "product_id": prod_id,
                "store_id": store_id,
                "quantity": qty,
                "discount_pct": discount_pct,
                "payment_method": pay_method,
                "order_status": order_status,
            }
        )
        tx_counter += 1

df_txn = pd.DataFrame(transactions)

# Inject 500 exact duplicate rows to test deduplication in Silver ETL
duplicates = df_txn.sample(n=500, random_state=42)
df_txn_dirty = pd.concat([df_txn, duplicates], ignore_index=True)

txn_path = os.path.join(RAW_DIR, "transactions.csv")
df_txn_dirty.to_csv(txn_path, index=False)

print("\nDataset Generation Complete!")
print(f" - stores.csv:       {len(df_stores):,} rows")
print(f" - products.csv:     {len(df_products):,} rows")
print(f" - customers.csv:    {len(df_cust_raw):,} rows")
print(f" - transactions.csv: {len(df_txn_dirty):,} rows (includes intentional duplicates & anomalies for ETL cleaning)")
