
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "storage"
    / "storage_performance_summary.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "storage"
    / "storage_optimization_insights.csv"
)


def generate_insights():

    df = pd.read_csv(INPUT_FILE)
    insights = []

    # Analyze each workload independently
    for workload, group in df.groupby(
        ["load_type", "io_type"],
        dropna=False
    ):

        group = group.dropna(subset=["avg_iops", "avg_latency"])

        if group.empty:
            continue

        best_iops = group.loc[group["avg_iops"].idxmax()]
        lowest_latency = group.loc[group["avg_latency"].idxmin()]
        highest_latency = group.loc[group["avg_latency"].idxmax()]

        insights.append({
            "workload": f"{workload[0]}_{workload[1]}",
            "best_iops_device": best_iops["device_type"],
            "best_iops_raid": best_iops["raid"],
            "best_iops": best_iops["avg_iops"],
            "lowest_latency_device": lowest_latency["device_type"],
            "lowest_latency_raid": lowest_latency["raid"],
            "lowest_latency": lowest_latency["avg_latency"],
            "highest_latency_device": highest_latency["device_type"],
            "highest_latency_raid": highest_latency["raid"],
            "highest_latency": highest_latency["avg_latency"],
        })

    result = pd.DataFrame(insights)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_FILE, index=False)

    print("\nSTORAGE INSIGHTS GENERATED")
    print(result.to_string(index=False))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_insights()
