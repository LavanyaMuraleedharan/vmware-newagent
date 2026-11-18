
from pathlib import Path
from datetime import datetime, timedelta
import csv
import random

# Reproducible simulated data
random.seed(42)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "infrastructure_logs" / "backup"
OUTPUT.mkdir(parents=True, exist_ok=True)

END_DATE = datetime(2026, 11, 16)
START_DATE = END_DATE - timedelta(days=89)


def write_csv(filename, rows):
    if not rows:
        return

    path = OUTPUT / filename

    # Exclude record_source from every exported CSV
    fieldnames = [
        column for column in rows[0].keys()
        if column != "record_source"
    ]

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                column: row[column]
                for column in fieldnames
            })

    print(f"Created {path.name}: {len(rows)} records")



# --------------------------------------------------
# 1. BACKUP REPOSITORIES
# --------------------------------------------------

repositories = []

for i in range(1, 11):
    repositories.append({
        "repository_id": f"REP-{i:03}",
        "repository_name": f"Backup-Repository-{i:03}",
        "repository_type": random.choice(
            ["Disk", "Deduplicated Disk", "Object Storage"]
        ),
        "total_capacity_gb": random.choice(
            [20000, 30000, 40000, 50000]
        ),
        "data_center": f"DC-{random.randint(1, 3)}",
        "record_source": "synthetic"
    })

# --------------------------------------------------
# 2. BACKUP ASSET INVENTORY
# --------------------------------------------------

assets = []
policies = []

for i in range(1, 21):
    policies.append({
        "policy_id": f"POL-{i:03}",
        "policy_name": f"Enterprise-Backup-Policy-{i:03}",
        "backup_frequency": random.choice(
            ["Daily", "Daily", "Weekly"]
        ),
        "retention_days": random.choice([30, 45, 60, 90]),
        "full_backup_day": "Sunday",
        "record_source": "synthetic"
    })

for i in range(1, 101):
    assets.append({
        "asset_id": f"SRV-{i:04}",
        "asset_name": f"Enterprise-Server-{i:04}",
        "application_id": f"APP-{((i - 1) % 30) + 1:03}",
        "environment": random.choice(
            ["Production", "Development", "Testing"]
        ),
        "server_type": random.choice(
            ["Physical", "Virtual"]
        ),
        "repository_id": f"REP-{((i - 1) % 10) + 1:03}",
        "policy_id": f"POL-{((i - 1) % 20) + 1:03}",
        "source_data_size_gb": random.randint(100, 2000),
        "record_source": "synthetic"
    })

# --------------------------------------------------
# 3. BACKUP JOB LOGS
# --------------------------------------------------

jobs = []
daily_repository_ingestion = {}

for day_number in range(90):
    current_date = START_DATE + timedelta(days=day_number)

    for asset in assets:
        asset_id = asset["asset_id"]
        repo_id = asset["repository_id"]
        policy_id = asset["policy_id"]

        source_size = asset["source_data_size_gb"]

        # Weekly full backup; incremental on other days
        if current_date.weekday() == 6:
            backup_type = "Full"
            backup_size = round(source_size * random.uniform(0.75, 1.0), 2)
        else:
            backup_type = "Incremental"
            backup_size = round(source_size * random.uniform(0.01, 0.08), 2)

        start_time = current_date.replace(
            hour=random.randint(0, 5),
            minute=random.randint(0, 59),
            second=0
        )

        # Duration depends partly on backup size
        duration = max(
            5,
            int(backup_size / random.uniform(3, 8))
        )

        status = random.choices(
            ["Success", "Warning", "Failed"],
            weights=[94, 4, 2],
            k=1
        )[0]

        retry_count = (
            random.randint(1, 3) if status == "Failed"
            else random.randint(0, 1) if status == "Warning"
            else 0
        )

        end_time = start_time + timedelta(minutes=duration)

        stored_size = (
            backup_size * random.uniform(0.55, 0.90)
            if status != "Failed" else 0
        )

        job_id = f"JOB-{day_number + 1:03}-{asset_id}"

        jobs.append({
            "job_id": job_id,
            "asset_id": asset_id,
            "application_id": asset["application_id"],
            "repository_id": repo_id,
            "policy_id": policy_id,
            "backup_type": backup_type,
            "start_time": start_time.isoformat(sep=" "),
            "end_time": end_time.isoformat(sep=" "),
            "source_size_gb": source_size,
            "backup_size_gb": round(backup_size, 2),
            "stored_size_gb": round(stored_size, 2),
            "duration_minutes": duration,
            "status": status,
            "retry_count": retry_count,
            "record_source": "synthetic"
        })

        key = (current_date.strftime("%Y-%m-%d"), repo_id)
        daily_repository_ingestion[key] = (
            daily_repository_ingestion.get(key, 0)
            + stored_size
        )

# --------------------------------------------------
# 4. BACKUP REPOSITORY MONITORING LOGS
# --------------------------------------------------

repository_logs = []
repository_usage = {
    repo["repository_id"]: repo["total_capacity_gb"] *
    random.uniform(0.35, 0.60)
    for repo in repositories
}

for day_number in range(90):
    current_date = START_DATE + timedelta(days=day_number)

    for repo in repositories:
        repo_id = repo["repository_id"]
        capacity = repo["total_capacity_gb"]

        incoming = daily_repository_ingestion.get(
            (current_date.strftime("%Y-%m-%d"), repo_id), 0
        )

        # Simulated retention/deletion and incoming backup data
        previous_usage = repository_usage[repo_id]
        deleted = previous_usage * random.uniform(0.001, 0.004)

        used = min(
            capacity * 0.95,
            max(0, previous_usage - deleted + incoming)
        )

        repository_usage[repo_id] = used

        free = capacity - used

        repository_logs.append({
            "timestamp": current_date.strftime("%Y-%m-%d"),
            "repository_id": repo_id,
            "total_capacity_gb": capacity,
            "used_capacity_gb": round(used, 2),
            "free_capacity_gb": round(free, 2),
            "utilization_pct": round((used / capacity) * 100, 2),
            "incoming_backup_gb": round(incoming, 2),
            "record_source": "synthetic"
        })

# --------------------------------------------------
# 5. BACKUP COST RECORDS
# --------------------------------------------------

cost_records = []

months = sorted({
    (START_DATE + timedelta(days=i)).strftime("%Y-%m")
    for i in range(90)
})

for repo in repositories:
    repo_id = repo["repository_id"]

    for month in months:
        cost_records.extend([
            {
                "cost_record_id": f"COST-{repo_id}-{month}-001",
                "repository_id": repo_id,
                "billing_month": month,
                "cost_category": "Storage",
                "amount": round(
                    repo["total_capacity_gb"] * random.uniform(1.5, 2.5),
                    2
                ),
                "currency": "INR",
                "record_source": "synthetic_assumption"
            },
            {
                "cost_record_id": f"COST-{repo_id}-{month}-002",
                "repository_id": repo_id,
                "billing_month": month,
                "cost_category": "Maintenance",
                "amount": round(random.uniform(5000, 15000), 2),
                "currency": "INR",
                "record_source": "synthetic_assumption"
            },
            {
                "cost_record_id": f"COST-{repo_id}-{month}-003",
                "repository_id": repo_id,
                "billing_month": month,
                "cost_category": "Power",
                "amount": round(random.uniform(1000, 5000), 2),
                "currency": "INR",
                "record_source": "synthetic_assumption"
            }
        ])

# --------------------------------------------------
# EXPORT ALL FIVE FILES
# --------------------------------------------------

write_csv("backup_asset_inventory.csv", assets)
write_csv("backup_policy_logs.csv", policies)
write_csv("backup_job_logs.csv", jobs)
write_csv("backup_repository_logs.csv", repository_logs)
write_csv("backup_cost_records.csv", cost_records)

print("\nBackup dataset generation completed.")
print(f"Output directory: {OUTPUT}")
