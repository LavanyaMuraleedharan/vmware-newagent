
import pandas as pd
import random
from pathlib import Path
from datetime import datetime, timedelta

random.seed(42)

# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "infrastructure_logs"
    / "database"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = (
    OUTPUT_DIR / "database_infrastructure_metrics.csv"
)

# --------------------------------------------------
# DATABASE SERVER INVENTORY
# --------------------------------------------------

database_servers = [
    ("DB001", "DB_SERVER001", "PostgreSQL", 32, 128, 2000, 80000),
    ("DB002", "DB_SERVER002", "PostgreSQL", 16, 64, 1000, 45000),
    ("DB003", "DB_SERVER003", "PostgreSQL", 64, 256, 4000, 150000),
    ("DB004", "DB_SERVER004", "MySQL", 32, 128, 2000, 75000),
    ("DB005", "DB_SERVER005", "MySQL", 16, 64, 1000, 42000),
    ("DB006", "DB_SERVER006", "MySQL", 64, 256, 4000, 145000),
    ("DB007", "DB_SERVER007", "Oracle", 64, 256, 5000, 180000),
    ("DB008", "DB_SERVER008", "Oracle", 32, 128, 3000, 110000),
    ("DB009", "DB_SERVER009", "Oracle", 16, 64, 1500, 65000),
    ("DB010", "DB_SERVER010", "SQL Server", 32, 128, 2000, 95000),
    ("DB011", "DB_SERVER011", "SQL Server", 16, 64, 1000, 55000),
    ("DB012", "DB_SERVER012", "SQL Server", 64, 256, 4000, 160000),
    ("DB013", "DB_SERVER013", "MongoDB", 32, 128, 2000, 85000),
    ("DB014", "DB_SERVER014", "MongoDB", 16, 64, 1000, 48000),
    ("DB015", "DB_SERVER015", "MongoDB", 64, 256, 4000, 140000),
    ("DB016", "DB_SERVER016", "MariaDB", 32, 128, 2000, 70000),
    ("DB017", "DB_SERVER017", "MariaDB", 16, 64, 1000, 40000),
    ("DB018", "DB_SERVER018", "MariaDB", 64, 256, 4000, 135000),
    ("DB019", "DB_SERVER019", "ClickHouse", 32, 128, 3000, 100000),
    ("DB020", "DB_SERVER020", "DuckDB", 16, 64, 1000, 38000),
]

# --------------------------------------------------
# UTILIZATION PROFILES
# --------------------------------------------------

profiles = {
    "low": {
        "cpu": (5, 25),
        "memory": (15, 40),
        "storage": (15, 45)
    },
    "moderate": {
        "cpu": (30, 60),
        "memory": (40, 70),
        "storage": (40, 75)
    },
    "high": {
        "cpu": (65, 90),
        "memory": (70, 95),
        "storage": (75, 95)
    }
}

records = []

start_date = datetime(2026, 8, 1)

# --------------------------------------------------
# GENERATE 90 DAYS OF METRICS
# --------------------------------------------------

for (
    database_id,
    server_id,
    database_engine,
    allocated_vcpu,
    allocated_memory_gb,
    allocated_storage_gb,
    monthly_cost_inr
) in database_servers:

    # Keep each server's utilization pattern consistent
    # across the observation period.
    profile_name = random.choice(
        ["low", "moderate", "high"]
    )

    profile = profiles[profile_name]

    for day in range(90):

        timestamp = start_date + timedelta(days=day)

        cpu_utilization = random.uniform(
            *profile["cpu"]
        )

        memory_utilization = random.uniform(
            *profile["memory"]
        )

        storage_utilization = random.uniform(
            *profile["storage"]
        )

        # Add small daily variation
        cpu_utilization += random.uniform(-3, 3)
        memory_utilization += random.uniform(-2, 2)
        storage_utilization += random.uniform(-1, 1)

        # Keep utilization within valid limits
        cpu_utilization = max(
            0, min(100, cpu_utilization)
        )

        memory_utilization = max(
            0, min(100, memory_utilization)
        )

        storage_utilization = max(
            0, min(100, storage_utilization)
        )

        used_memory_gb = round(
            allocated_memory_gb
            * memory_utilization / 100,
            2
        )

        used_storage_gb = round(
            allocated_storage_gb
            * storage_utilization / 100,
            2
        )

        records.append({
            "timestamp": timestamp.isoformat(),
            "database_id": database_id,
            "server_id": server_id,
            "database_engine": database_engine,
            "allocated_vcpu": allocated_vcpu,
            "used_cpu_pct": round(cpu_utilization, 2),
            "allocated_memory_gb": allocated_memory_gb,
            "used_memory_gb": used_memory_gb,
            "memory_utilization_pct": round(
                memory_utilization, 2
            ),
            "storage_allocated_gb": allocated_storage_gb,
            "storage_used_gb": used_storage_gb,
            "storage_utilization_pct": round(
                storage_utilization, 2
            ),
            "monthly_cost_inr": monthly_cost_inr,
            "currency": "INR"
        })

# --------------------------------------------------
# SAVE DATASET
# --------------------------------------------------

result = pd.DataFrame(records)

result.to_csv(OUTPUT_FILE, index=False)

# --------------------------------------------------
# DISPLAY SUMMARY
# --------------------------------------------------

print("\nDatabase infrastructure dataset generated successfully.")

print(f"Output file: {OUTPUT_FILE}")

print(f"Total records: {len(result)}")

print(
    "Unique database servers:",
    result["server_id"].nunique()
)

print(
    "Database engines:",
    result["database_engine"].nunique()
)

print("\nCPU utilization summary:")

print(
    result.groupby("server_id")["used_cpu_pct"]
    .mean()
    .describe()
)

print("\nSample records:")

print(result.head(10).to_string(index=False))
