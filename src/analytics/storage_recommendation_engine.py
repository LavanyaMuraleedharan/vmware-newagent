
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
    / "storage_recommendations.csv"
)


def generate_recommendations():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Storage analytics file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
        "device_type",
        "load_type",
        "io_type",
        "raid",
        "avg_iops",
        "avg_latency",
        "total_records",
        "source_dataset",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    df = df.dropna(
        subset=["avg_iops", "avg_latency", "device_type", "raid"]
    )

    df = df[
        (df["avg_iops"] >= 0)
        & (df["avg_latency"] >= 0)
    ].copy()

    recommendations = []

    # Analyze each workload independently
    for (load_type, io_type), group in df.groupby(
        ["load_type", "io_type"]
    ):

        if group.empty:
            continue

        # Workload baseline:
        # Average performance across available benchmark configurations
        baseline_iops = group["avg_iops"].mean()
        baseline_latency = group["avg_latency"].mean()

        # Highest IOPS configuration
        best_iops = group.loc[
            group["avg_iops"].idxmax()
        ]

        # Lowest latency configuration
        best_latency = group.loc[
            group["avg_latency"].idxmin()
        ]

        # Rank configurations
        ranked_group = group.sort_values(
            by="avg_iops",
            ascending=False
        )

        for rank, (_, row) in enumerate(
            ranked_group.iterrows(),
            start=1
        ):

            iops_improvement = (
                ((row["avg_iops"] - baseline_iops)
                 / baseline_iops) * 100
                if baseline_iops > 0 else 0
            )

            latency_reduction = (
                ((baseline_latency - row["avg_latency"])
                 / baseline_latency) * 100
                if baseline_latency > 0 else 0
            )

            recommendations.append({

                "workload": f"{load_type}_{io_type}",

                "configuration_rank": rank,

                "device_type": row["device_type"],

                "raid": row["raid"],

                "n_disks": row.get("avg_n_disks"),

                "avg_iops": round(row["avg_iops"], 2),

                "avg_latency": round(row["avg_latency"], 2),

                "baseline_iops": round(baseline_iops, 2),

                "baseline_latency": round(baseline_latency, 2),

                "iops_improvement_pct": round(
                    iops_improvement, 2
                ),

                "latency_reduction_pct": round(
                    latency_reduction, 2
                ),

                "best_iops_configuration": (
                    row["avg_iops"] == best_iops["avg_iops"]
                ),

                "best_latency_configuration": (
                    row["avg_latency"] == best_latency["avg_latency"]
                ),

                "benchmark_records": row["total_records"],

                "source_dataset": row["source_dataset"],

                "recommendation": (
                    f"Evaluate {row['device_type']} RAID "
                    f"{row['raid']} for {load_type} {io_type}. "
                    f"Measured average IOPS: {row['avg_iops']:.2f}; "
                    f"latency: {row['avg_latency']:.2f}."
                ),

                "evidence": (
                    "Recommendation based on storage benchmark "
                    "performance comparisons."
                ),

                "financial_savings": "Not calculated",

                "limitations": (
                    "Benchmark results do not establish actual "
                    "enterprise storage cost savings, capacity "
                    "utilization, or production suitability."
                )
            })

    result = pd.DataFrame(recommendations)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n" + "=" * 60)
    print("STORAGE RECOMMENDATION ENGINE COMPLETED")
    print("=" * 60)

    print(f"Total recommendations: {len(result)}")

    print("\nBest IOPS configurations:")

    best_iops_results = result[
        result["best_iops_configuration"]
    ]

    print(
        best_iops_results[
            [
                "workload",
                "device_type",
                "raid",
                "avg_iops",
                "iops_improvement_pct",
            ]
        ].to_string(index=False)
    )

    print("\nBest latency configurations:")

    best_latency_results = result[
        result["best_latency_configuration"]
    ]

    print(
        best_latency_results[
            [
                "workload",
                "device_type",
                "raid",
                "avg_latency",
                "latency_reduction_pct",
            ]
        ].to_string(index=False)
    )

    print(f"\nSaved recommendations: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_recommendations()
