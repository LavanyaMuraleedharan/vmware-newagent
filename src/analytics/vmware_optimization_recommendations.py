
from pathlib import Path
import pandas as pd
import json

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "vmware"
    / "vmware_utilization_analysis.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "vmware"

RECOMMENDATION_FILE = (
    OUTPUT_DIR / "vmware_optimization_recommendations.csv"
)

SUMMARY_FILE = (
    OUTPUT_DIR / "vmware_recommendation_summary.json"
)


def generate_recommendation(row):

    cpu_status = row["cpu_status"]
    memory_status = row["memory_status"]

    avg_cpu = row["avg_cpu_usage_pct"]
    peak_cpu = row["peak_cpu_usage_pct"]

    avg_memory = row["avg_memory_utilization_pct"]
    peak_memory = row["peak_memory_utilization_pct"]

    # ----------------------------------------------
    # Insufficient data
    # ----------------------------------------------

    if (
        cpu_status == "insufficient_data"
        or memory_status == "insufficient_data"
    ):
        return pd.Series({
            "recommendation": "Collect additional monitoring data",
            "reason": "CPU or memory measurements are missing",
            "priority": "Undetermined",
            "risk_level": "Unknown",
            "confidence": "Low"
        })

    # ----------------------------------------------
    # High CPU and memory utilization
    # ----------------------------------------------

    if (
        cpu_status == "high_utilization"
        and memory_status == "high_utilization"
    ):
        return pd.Series({
            "recommendation": "Investigate CPU and memory capacity",
            "reason": "Both CPU and memory show high utilization",
            "priority": "High",
            "risk_level": "High",
            "confidence": "Medium"
        })

    # ----------------------------------------------
    # High CPU utilization
    # ----------------------------------------------

    if cpu_status == "high_utilization":
        return pd.Series({
            "recommendation": "Investigate CPU capacity and workload peaks",
            "reason": (
                f"Average CPU: {avg_cpu:.2f}%, "
                f"peak CPU: {peak_cpu:.2f}%"
            ),
            "priority": "High",
            "risk_level": "High",
            "confidence": "Medium"
        })

    # ----------------------------------------------
    # High memory utilization
    # ----------------------------------------------

    if memory_status == "high_utilization":
        return pd.Series({
            "recommendation": "Investigate memory capacity and pressure",
            "reason": (
                f"Average memory: {avg_memory:.2f}%, "
                f"peak memory: {peak_memory:.2f}%"
            ),
            "priority": "High",
            "risk_level": "High",
            "confidence": "Medium"
        })

    # ----------------------------------------------
    # Low average and peak CPU and memory
    # ----------------------------------------------

    if (
        cpu_status == "low_utilization_review"
        and memory_status == "low_utilization_review"
    ):
        return pd.Series({
            "recommendation": "Review resource right-sizing opportunity",
            "reason": (
                "Both CPU and memory have low average and peak "
                "utilization according to configured thresholds"
            ),
            "priority": "Medium",
            "risk_level": "Medium",
            "confidence": "Medium"
        })

    # ----------------------------------------------
    # Low average but variable/peak usage
    # ----------------------------------------------

    if (
        cpu_status == "low_utilization_review"
        or memory_status == "low_utilization_review"
    ):
        return pd.Series({
            "recommendation": "Review individual resource allocation",
            "reason": (
                "One resource shows low utilization while another "
                "has moderate, variable or elevated utilization"
            ),
            "priority": "Medium",
            "risk_level": "Medium",
            "confidence": "Medium"
        })

    # ----------------------------------------------
    # Moderate or variable utilization
    # ----------------------------------------------

    return pd.Series({
        "recommendation": "Continue monitoring workload patterns",
        "reason": "Utilization is moderate or variable",
        "priority": "Low",
        "risk_level": "Low",
        "confidence": "Medium"
    })


def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_FILE)

    print(f"Input records: {len(df):,}")

    # Generate recommendations.
    recommendation_columns = df.apply(
        generate_recommendation,
        axis=1
    )

    df = pd.concat(
        [df, recommendation_columns],
        axis=1
    )

    # Financial impact is deliberately not calculated here.
    df["estimated_monthly_cost_inr"] = None
    df["potential_monthly_savings_inr"] = None

    df["financial_status"] = "pending_common_cost_model"

    df["data_origin"] = "public_benchmark_dataset"

    df["recommendation_scope"] = (
        "Source-file time-series review; not confirmed VM identity"
    )

    # Save detailed recommendations.
    df.to_csv(RECOMMENDATION_FILE, index=False)

    # Summary.
    summary = {
        "domain": "VMware",
        "records_analyzed": int(len(df)),
        "recommendation_counts": {
            str(key): int(value)
            for key, value in df[
                "recommendation"
            ].value_counts().items()
        },
        "priority_counts": {
            str(key): int(value)
            for key, value in df[
                "priority"
            ].value_counts().items()
        },
        "risk_counts": {
            str(key): int(value)
            for key, value in df[
                "risk_level"
            ].value_counts().items()
        },
        "financial_calculation": (
            "Pending common Cost Agent cost model"
        ),
        "limitations": [
            "No confirmed VM identifiers in source dataset",
            "Historical benchmark measurements, not live infrastructure",
            "Recommendations require operational validation",
            "No actual financial cost or savings calculated"
        ],
        "output_file": str(RECOMMENDATION_FILE)
    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(summary, file, indent=4)

    print("\n========== VMWARE RECOMMENDATIONS ==========")

    print(f"Records analyzed: {len(df):,}")

    print("\nRecommendation counts:")
    print(
        df["recommendation"]
        .value_counts()
        .to_string()
    )

    print("\nPriority counts:")
    print(
        df["priority"]
        .value_counts()
        .to_string()
    )

    print("\nRisk counts:")
    print(
        df["risk_level"]
        .value_counts()
        .to_string()
    )

    print(f"\nRecommendations: {RECOMMENDATION_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
