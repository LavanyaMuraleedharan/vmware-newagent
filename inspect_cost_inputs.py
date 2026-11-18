
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent

FILES = {
    "VMware": [
        "data/processed/vmware/vmware_utilization_analysis.csv"
    ],
    "Storage": [
        "data/infrastructure_logs/storage/storage_capacity_metrics.csv"
    ],
    "Backup": [
        "data/infrastructure_logs/backup/backup_cost_records.csv",
        "data/infrastructure_logs/backup/backup_repository_logs.csv"
    ],
    "Compute/GPU": [
        "data/infrastructure_logs/compute_gpu/gpu_utilization_metrics.csv",
        "data/processed/compute_gpu/compute_gpu_server_metrics.csv"
    ],
    "Database": [
        "data/infrastructure_logs/database/database_infrastructure_metrics.csv",
        "data/raw_query_timings.csv"
    ],
    "Licensing": [
        "data/processed/licensing/licensing_feature_metrics.csv"
    ]
}

COST_KEYWORDS = [
    "cost", "price", "rate", "currency",
    "license_fee", "monthly", "annual"
]

for domain, paths in FILES.items():

    print("\n" + "=" * 65)
    print(f"DOMAIN: {domain}")
    print("=" * 65)

    for relative_path in paths:

        file_path = ROOT / relative_path

        print(f"\nFile: {relative_path}")

        if not file_path.exists():
            print("File not found.")
            continue

        try:
            with open(
                file_path,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as file:

                reader = csv.DictReader(file)
                columns = reader.fieldnames or []

                print("Columns:")
                print(columns)

                cost_columns = [
                    col for col in columns
                    if any(
                        keyword in col.lower()
                        for keyword in COST_KEYWORDS
                    )
                ]

                print("\nCost-related columns:")
                print(cost_columns if cost_columns else "None")

                if cost_columns:
                    print("\nSample cost records:")

                    for index, row in enumerate(reader):
                        print({
                            col: row.get(col)
                            for col in cost_columns
                        })

                        if index >= 2:
                            break

        except Exception as error:
            print(f"Error reading file: {error}")

print("\nCost input inspection completed.")
