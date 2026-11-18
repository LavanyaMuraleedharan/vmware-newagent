from pathlib import Path
import pandas as pd

ROOT = Path("data/asi_opensource_server_hourly/asi_opensource_server_hourly")

# Load the aggregated server metrics
metrics_path = Path(
    "data/processed/compute_gpu/compute_gpu_server_metrics.csv"
)
metrics = pd.read_csv(metrics_path)

# Find servers associated with multiple clusters
multiple = metrics[
    metrics["cluster_ids"].fillna("").apply(
        lambda value: len([
            item for item in str(value).split(",")
            if item.strip()
        ]) > 1
    )
]

print("Servers with multiple clusters:", len(multiple))

if multiple.empty:
    print("No multiple-cluster servers found.")
    raise SystemExit

# Select up to 5 examples
sample_ids = multiple["server_id"].head(5).tolist()

print("\nSelected server IDs:")
for server_id in sample_ids:
    print(server_id)

# Inspect original records
results = []

for file_path in ROOT.rglob("*.parquet"):
    try:
        df = pd.read_parquet(
            file_path,
            columns=[
                "server_id",
                "cluster_id",
                "gpu_spec_public",
                "gpu_count",
                "cpu_capacity_cores",
            ],
        )

        matched = df[df["server_id"].astype(str).isin(sample_ids)]

        if not matched.empty:
            matched = matched.copy()
            matched["source_file"] = str(file_path)
            results.append(matched)

    except Exception as error:
        print(f"Could not inspect {file_path}: {error}")

if results:
    output = pd.concat(results, ignore_index=True)

    output_path = Path(
        "data/processed/compute_gpu/"
        "compute_gpu_cluster_investigation.csv"
    )

    output.to_csv(output_path, index=False)

    print("\nOriginal records found:")
    print(output.to_string(index=False))

    print("\nSaved investigation file:")
    print(output_path)
else:
    print("No matching original records found.")