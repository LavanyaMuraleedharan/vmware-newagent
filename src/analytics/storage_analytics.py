
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "dataset" / "dataset"

OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "storage"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# Use full datasets, not separate train/test subsets
FILES = {
    "cache": DATA_PATH / "cache" / "cache.csv",
    "hdd_sequential": DATA_PATH / "pools" / "hdd_sequential.csv",
    "ssd_random": DATA_PATH / "pools" / "ssd_random.csv",
    "ssd_sequential": DATA_PATH / "pools" / "ssd_sequential.csv",
}


def analyze_storage(file_name, file_path):
    print(f"\nAnalyzing: {file_name}")

    df = pd.read_csv(file_path)

    # Convert numerical columns
    numeric_columns = [
        "iops",
        "lat",
        "block_size",
        "n_jobs",
        "iodepth",
        "read_fraction",
        "n_disks",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # Remove invalid metric rows
    df = df.dropna(subset=["iops", "lat"])
    df = df[(df["iops"] >= 0) & (df["lat"] >= 0)]

    # Performance summary
    summary = (
        df.groupby(
            ["device_type", "load_type", "io_type", "raid"],
            dropna=False
        )
        .agg(
            total_records=("iops", "count"),
            avg_iops=("iops", "mean"),
            median_iops=("iops", "median"),
            avg_latency=("lat", "mean"),
            median_latency=("lat", "median"),
            p95_latency=("lat", lambda x: x.quantile(0.95)),
            avg_block_size=("block_size", "mean"),
            avg_iodepth=("iodepth", "mean"),
            avg_n_disks=("n_disks", "mean"),
        )
        .reset_index()
    )

    summary["source_dataset"] = file_name

    output_file = OUTPUT_PATH / f"{file_name}_analytics.csv"
    summary.to_csv(output_file, index=False)

    print(f"Valid records: {len(df)}")
    print(f"Summary groups: {len(summary)}")
    print(f"Saved: {output_file}")

    return summary


def run_storage_analytics():
    all_summaries = []

    for name, file_path in FILES.items():
        if not file_path.exists():
            print(f"Missing dataset: {file_path}")
            continue

        summary = analyze_storage(name, file_path)
        all_summaries.append(summary)

    if all_summaries:
        final_summary = pd.concat(all_summaries, ignore_index=True)

        final_file = OUTPUT_PATH / "storage_performance_summary.csv"
        final_summary.to_csv(final_file, index=False)

        print("\n" + "=" * 50)
        print("STORAGE ANALYTICS COMPLETED")
        print("=" * 50)
        print(final_summary.head(10).to_string(index=False))
        print(f"\nFinal report: {final_file}")


if __name__ == "__main__":
    run_storage_analytics()
