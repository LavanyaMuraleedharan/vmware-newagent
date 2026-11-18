
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent

files = {
    "BACKUP COSTS":
        "data/infrastructure_logs/backup/backup_cost_records.csv",

    "DATABASE COSTS":
        "data/infrastructure_logs/database/database_infrastructure_metrics.csv",

    "LICENSING COSTS":
        "data/processed/licensing/licensing_feature_metrics.csv"
}

for name, relative_path in files.items():

    path = ROOT / relative_path

    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)

    if not path.exists():
        print("File not found:", path)
        continue

    df = pd.read_csv(path)

    if name == "BACKUP COSTS":
        print("Records:", len(df))
        print("\nCost by category and currency:")
        print(
            df.groupby(
                ["cost_category", "currency"]
            )["amount"].agg(["count", "sum"])
        )

    elif name == "DATABASE COSTS":
        print("Records:", len(df))
        print("\nUnique databases:", df["database_id"].nunique())
        print("\nCost summary:")
        print(
            df.groupby("database_id").agg(
                monthly_cost=("monthly_cost_inr", "first"),
                avg_cpu=("used_cpu_pct", "mean"),
                avg_memory=("memory_utilization_pct", "mean"),
                avg_storage=("storage_utilization_pct", "mean")
            ).to_string()
        )

    elif name == "LICENSING COSTS":
        print("Records:", len(df))
        print("\nLicense summary:")
        print(
            df[[
                "software_feature",
                "license_metric",
                "reclaim_candidate_quantity",
                "annual_unit_cost",
                "currency",
                "cost_assumption_status"
            ]].to_string(index=False)
        )

print("\nInspection completed.")
