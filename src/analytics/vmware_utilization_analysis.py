
from pathlib import Path
import json
import pandas as pd

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "vmware"
    / "vmware_file_metrics.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "vmware"

OUTPUT_FILE = OUTPUT_DIR / "vmware_utilization_analysis.csv"
SUMMARY_FILE = OUTPUT_DIR / "vmware_utilization_summary.json"

# --------------------------------------------------
# CONFIGURABLE SCREENING THRESHOLDS
# --------------------------------------------------

CPU_LOW_AVG = 20
CPU_LOW_PEAK = 60

MEMORY_LOW_AVG = 30
MEMORY_LOW_PEAK = 70

CPU_HIGH_AVG = 80
MEMORY_HIGH_AVG = 80


def classify_resource(avg, peak, low_avg, low_peak, high_avg):
    if pd.isna(avg) or pd.isna(peak):
        return "insufficient_data"

    if avg >= high_avg or peak >= 90:
        return "high_utilization"

    if avg < low_avg and peak < low_peak:
        return "low_utilization_review"

    return "moderate_or_variable_utilization"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"VMware metrics file not found: {INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
        "source_file_id",
        "total_samples",
        "avg_cpu_usage_pct",
        "peak_cpu_usage_pct",
        "avg_memory_utilization_pct",
        "peak_memory_utilization_pct",
    ]

    missing = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    # Convert metrics to numeric.
    for column in required_columns[1:]:
        df[column] = pd.to_numeric(
            df[column], errors="coerce"
        )

    # CPU classification.
    df["cpu_status"] = df.apply(
        lambda row: classify_resource(
            row["avg_cpu_usage_pct"],
            row["peak_cpu_usage_pct"],
            CPU_LOW_AVG,
            CPU_LOW_PEAK,
            CPU_HIGH_AVG,
        ),
        axis=1,
    )

    # Memory classification.
    df["memory_status"] = df.apply(
        lambda row: classify_resource(
            row["avg_memory_utilization_pct"],
            row["peak_memory_utilization_pct"],
            MEMORY_LOW_AVG,
            MEMORY_LOW_PEAK,
            MEMORY_HIGH_AVG,
        ),
        axis=1,
    )

    # Combined screening result.
    df["optimization_review_status"] = "review_required"

    insufficient = (
        df["cpu_status"].eq("insufficient_data")
        | df["memory_status"].eq("insufficient_data")
    )

    low_both = (
        df["cpu_status"].eq("low_utilization_review")
        & df["memory_status"].eq("low_utilization_review")
    )

    high_either = (
        df["cpu_status"].eq("high_utilization")
        | df["memory_status"].eq("high_utilization")
    )

    df.loc[
        insufficient,
        "optimization_review_status"
    ] = "insufficient_data"

    df.loc[
        low_both,
        "optimization_review_status"
    ] = "low_utilization_candidate"

    df.loc[
        high_either,
        "optimization_review_status"
    ] = "performance_risk_review"

    # Preserve the distinction between a source file and a VM.
    df["entity_type"] = "source_file_timeseries"

    df["analysis_note"] = (
        "Historical benchmark screening only; "
        "not a confirmed VM identity or resizing instruction."
    )

    df["data_origin"] = "public_benchmark_dataset"

    # Save detailed results.
    df.to_csv(OUTPUT_FILE, index=False)

    # Build summary.
    summary = {
        "domain": "VMware",
        "source_file_count": int(len(df)),
        "total_samples": int(df["total_samples"].sum()),
        "cpu_status_counts": {
            str(key): int(value)
            for key, value in df["cpu_status"].value_counts(
                dropna=False
            ).items()
        },
        "memory_status_counts": {
            str(key): int(value)
            for key, value in df["memory_status"].value_counts(
                dropna=False
            ).items()
        },
        "optimization_review_counts": {
            str(key): int(value)
            for key, value in df[
                "optimization_review_status"
            ].value_counts(dropna=False).items()
        },
        "thresholds": {
            "cpu_low_average_pct": CPU_LOW_AVG,
            "cpu_low_peak_pct": CPU_LOW_PEAK,
            "memory_low_average_pct": MEMORY_LOW_AVG,
            "memory_low_peak_pct": MEMORY_LOW_PEAK,
            "cpu_high_average_pct": CPU_HIGH_AVG,
            "memory_high_average_pct": MEMORY_HIGH_AVG,
        },
        "limitations": [
            "Source files do not contain confirmed VM IDs.",
            "Historical benchmark data is not live infrastructure data.",
            "Low utilization flags are screening signals only.",
            "No financial costs or savings are calculated here.",
            "Resizing requires workload, service and capacity validation.",
        ],
        "output_file": str(OUTPUT_FILE),
    }

    with open(
        SUMMARY_FILE, "w", encoding="utf-8"
    ) as file:
        json.dump(summary, file, indent=4)

    print("\n========== VMWARE UTILIZATION ANALYSIS ==========")
    print(f"Source files analyzed: {len(df):,}")
    print(f"Samples represented: {df['total_samples'].sum():,}")

    print("\nCPU status:")
    print(df["cpu_status"].value_counts().to_string())

    print("\nMemory status:")
    print(df["memory_status"].value_counts().to_string())

    print("\nOptimization review status:")
    print(
        df["optimization_review_status"]
        .value_counts()
        .to_string()
    )

    print(f"\nDetailed results: {OUTPUT_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
