
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent

file_path = ROOT / "data/infrastructure_logs/backup/backup_cost_records.csv"
df = pd.read_csv(file_path)

df["billing_month"] = pd.to_datetime(
    df["billing_month"], errors="coerce"
)

latest_month = df["billing_month"].max()

latest = df[df["billing_month"] == latest_month]

print("\nLATEST BILLING MONTH:", latest_month)
print("\nCOST BY CATEGORY:")

print(
    latest.groupby(["cost_category", "currency"])["amount"]
    .agg(["count", "sum"])
)

print("\nCOST BY REPOSITORY:")

print(
    latest.groupby(["repository_id", "currency"])["amount"]
    .sum()
    .to_string()
)

print("\nTOTAL LATEST MONTH COST:")
print(latest.groupby("currency")["amount"].sum())
