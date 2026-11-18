
import pandas as pd
import random
from pathlib import Path
from datetime import datetime, timedelta

# Reproducible synthetic data
random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "data" / "infrastructure_logs" / "storage"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "storage_capacity_metrics.csv"

# Synthetic storage inventory
storage_devices = [
    ("STG001", "SAN", 100, 25_000),
    ("STG002", "NAS", 200, 40_000),
    ("STG003", "SAN", 150, 35_000),
    ("STG004", "SSD", 50, 30_000),
    ("STG005", "HDD", 300, 45_000),
    ("STG006", "SSD", 100, 38_000),
    ("STG007", "NAS", 250, 42_000),
    ("STG008", "SAN", 200, 50_000),
    ("STG009", "HDD", 400, 55_000),
    ("STG010", "SSD", 80, 32_000),
]

records = []

start_date = datetime(2026, 8, 1)

# Generate 90 days of daily observations
for day in range(90):

    timestamp = start_date + timedelta(days=day)

    for storage_id, device_type, total_tb, monthly_cost in storage_devices:

        # Different utilization patterns
        if storage_id in ["STG001", "STG004", "STG010"]:
            utilization = random.uniform(10, 35)

        elif storage_id in ["STG002", "STG006", "STG007"]:
            utilization = random.uniform(40, 70)

        else:
            utilization = random.uniform(75, 95)

        # Small daily variation
        utilization = min(100, max(0, utilization + random.uniform(-2, 2)))

        used_tb = round(total_tb * utilization / 100, 2)
        free_tb = round(total_tb - used_tb, 2)

        records.append({
            "timestamp": timestamp.isoformat(),
            "storage_id": storage_id,
            "device_type": device_type,
            "total_capacity_tb": total_tb,
            "used_capacity_tb": used_tb,
            "free_capacity_tb": free_tb,
            "utilization_pct": round(utilization, 2),
            "monthly_cost_inr": monthly_cost,
            "currency": "INR"
        })

df = pd.DataFrame(records)

df.to_csv(OUTPUT_FILE, index=False)

print("Storage capacity dataset generated successfully.")
print(f"Output: {OUTPUT_FILE}")
print(f"Total records: {len(df)}")
print(f"Unique storage devices: {df['storage_id'].nunique()}")
print("\nSample records:")
print(df.head(10).to_string(index=False))
