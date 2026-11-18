
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Load repository capacity history
capacity_path = (
    ROOT / "data/infrastructure_logs/backup/backup_repository_logs.csv"
)
capacity = pd.read_csv(capacity_path)

capacity["timestamp"] = pd.to_datetime(
    capacity["timestamp"], errors="coerce"
)

# Keep only the latest observation for each repository
latest_capacity = (
    capacity.sort_values("timestamp")
    .groupby("repository_id")
    .tail(1)
    .copy()
)

# Load backup costs
cost_path = (
    ROOT / "data/infrastructure_logs/backup/backup_cost_records.csv"
)
costs = pd.read_csv(cost_path)

costs["billing_month"] = pd.to_datetime(
    costs["billing_month"], errors="coerce"
)

latest_month = costs["billing_month"].max()
latest_costs = costs[costs["billing_month"] == latest_month]

# Sum all cost categories for each repository
repository_costs = (
    latest_costs.groupby("repository_id")["amount"]
    .sum()
    .reset_index(name="monthly_cost_inr")
)

# Combine capacity and cost
result = latest_capacity.merge(
    repository_costs,
    on="repository_id",
    how="left"
)

result["unused_capacity_gb"] = (
    result["total_capacity_gb"] - result["used_capacity_gb"]
)

print("\nLATEST CAPACITY OBSERVATION:")
print(result["timestamp"].max())

print("\nREPOSITORY CAPACITY AND COST ANALYSIS:")
columns = [
    "repository_id",
    "total_capacity_gb",
    "used_capacity_gb",
    "free_capacity_gb",
    "utilization_pct",
    "incoming_backup_gb",
    "monthly_cost_inr",
    "unused_capacity_gb"
]

print(
    result[columns]
    .sort_values("utilization_pct", ascending=False)
    .round(2)
    .to_string(index=False)
)

print("\nUTILIZATION SUMMARY:")
print(result["utilization_pct"].describe().round(2))

print("\nTOTAL LATEST MONTH COST:")
print(f"INR {result['monthly_cost_inr'].sum():,.2f}")
