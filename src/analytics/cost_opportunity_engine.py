
from pathlib import Path
import json
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

PROCESSED = ROOT / "data" / "processed"
BACKUP_DIR = ROOT / "data" / "infrastructure_logs" / "backup"
STORAGE_LOG_DIR = ROOT / "data" / "infrastructure_logs" / "storage"
GPU_LOG_DIR = ROOT / "data" / "infrastructure_logs" / "compute_gpu"
DATABASE_LOG_DIR = ROOT / "data" / "infrastructure_logs" / "database"

OUTPUT_DIR = PROCESSED / "cost_agent"
OUTPUT_FILE = OUTPUT_DIR / "domain_analysis.json"


# ============================================================
# COMMON HELPERS
# ============================================================

def read_csv(path):
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return None


def read_json(path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return None


def clean_records(df, limit=10):
    if df is None or df.empty:
        return []

    result = df.head(limit).copy()
    result = result.astype(object).where(pd.notna(result), None)

    # Exclude provenance columns from displayed records.
    result = result.drop(
        columns=["data_origin", "source_dataset"],
        errors="ignore"
    )

    return result.to_dict(orient="records")


def numeric_summary(df, columns):
    result = {}

    if df is None or df.empty:
        return result

    for column in columns:
        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column], errors="coerce"
        ).dropna()

        if not values.empty:
            result[column] = {
                "average": round(float(values.mean()), 2),
                "median": round(float(values.median()), 2),
                "maximum": round(float(values.max()), 2)
            }

    return result


def remove_origin_fields(data):
    """Remove provenance fields recursively from report output."""

    if isinstance(data, dict):
        return {
            key: remove_origin_fields(value)
            for key, value in data.items()
            if key not in ("data_origin", "source_dataset")
        }

    if isinstance(data, list):
        return [remove_origin_fields(item) for item in data]

    return data


# ============================================================
# VMWARE
# ============================================================

def analyze_vmware():
    metrics = read_csv(
        PROCESSED / "vmware" / "vmware_utilization_analysis.csv"
    )

    recommendations = read_csv(
        PROCESSED / "vmware" / "vmware_optimization_recommendations.csv"
    )

    if metrics is None or recommendations is None:
        return {
            "status": "insufficient_data",
            "reason": "VMware input files are missing."
        }

    candidates = recommendations.copy()

    if "optimization_review_status" in candidates.columns:
        candidates = candidates[
            candidates["optimization_review_status"]
            .astype(str).str.lower()
            == "low_utilization_candidate"
        ]

    if "avg_cpu_usage_pct" in candidates.columns:
        candidates = candidates.sort_values(
            "avg_cpu_usage_pct",
            ascending=True
        )

    return {
        "status": "analyzed",
        "total_records": len(metrics),
        "recommendation_records": len(recommendations),
        "low_utilization_review_candidates": len(candidates),
        "utilization_summary": numeric_summary(
            metrics,
            [
                "avg_cpu_usage_pct",
                "peak_cpu_usage_pct",
                "avg_memory_utilization_pct",
                "peak_memory_utilization_pct"
            ]
        ),
        "candidate_sample": clean_records(candidates, 10),
        "financial_status": "insufficient_data",
        "limitations": [
            "Source-file identifiers are not confirmed VM identities.",
            "Historical observations do not establish current production utilization.",
            "Actual server and VM costs are unavailable.",
            "Peak workload and application dependencies require validation.",
            "No financial savings are calculated without validated cost inputs."
        ]
    }


# ============================================================
# STORAGE
# ============================================================

def analyze_storage():
    summary = read_csv(
        PROCESSED / "storage" / "storage_performance_summary.csv"
    )

    insights = read_csv(
        PROCESSED / "storage" / "storage_optimization_insights.csv"
    )

    capacity = read_csv(
        STORAGE_LOG_DIR / "storage_capacity_metrics.csv"
    )

    if summary is None:
        return {
            "status": "insufficient_data",
            "reason": "Storage performance data is missing."
        }

    capacity_analysis = {
        "status": "unavailable",
        "reason": "Storage capacity metrics file is missing.",
        "device_count": 0,
        "underutilized_device_count": 0,
        "average_utilization_pct": None,
        "total_capacity_tb": None,
        "total_used_capacity_tb": None,
        "total_free_capacity_tb": None,
        "underutilized_device_sample": []
    }

    if capacity is not None and not capacity.empty:
        required = {
            "storage_id", "timestamp", "total_capacity_tb",
            "used_capacity_tb", "free_capacity_tb", "utilization_pct"
        }

        missing = sorted(required - set(capacity.columns))

        if not missing:
            capacity["timestamp"] = pd.to_datetime(
                capacity["timestamp"], errors="coerce"
            )

            for col in [
                "total_capacity_tb",
                "used_capacity_tb",
                "free_capacity_tb",
                "utilization_pct"
            ]:
                capacity[col] = pd.to_numeric(
                    capacity[col], errors="coerce"
                )

            # Select latest observation for each storage device.
            latest = (
                capacity.dropna(subset=["timestamp"])
                .sort_values("timestamp")
                .groupby("storage_id", as_index=False)
                .tail(1)
                .copy()
            )

            underutilized = latest[
                latest["utilization_pct"] < 30
            ].copy()

            capacity_analysis = {
                "status": "analyzed",
                "device_count": int(latest["storage_id"].nunique()),
                "underutilized_device_count": int(
                    underutilized["storage_id"].nunique()
                ),
                "average_utilization_pct": (
                    round(float(latest["utilization_pct"].mean()), 2)
                    if latest["utilization_pct"].notna().any()
                    else None
                ),
                "total_capacity_tb": round(
                    float(latest["total_capacity_tb"].sum()), 2
                ),
                "total_used_capacity_tb": round(
                    float(latest["used_capacity_tb"].sum()), 2
                ),
                "total_free_capacity_tb": round(
                    float(latest["free_capacity_tb"].sum()), 2
                ),
                "underutilized_device_sample": clean_records(
                    underutilized.sort_values("utilization_pct"), 10
                ),
                "latest_device_records": clean_records(
                    latest.sort_values("utilization_pct"), 20
                ),
                "currency": (
                    sorted(
                        capacity["currency"].dropna().astype(str).unique()
                    )
                    if "currency" in capacity.columns else []
                )
            }
        else:
            capacity_analysis["reason"] = (
                "Capacity dataset is missing required columns: "
                + str(missing)
            )

    return {
        "status": "analyzed",
        "performance_group_count": len(summary),
        "performance_summary": clean_records(summary, 30),
        "optimization_insights": clean_records(insights, 20),
        "capacity_analysis": capacity_analysis,
        "financial_status": (
            "cost_inputs_require_validation"
            if capacity_analysis["status"] == "analyzed"
            else "insufficient_data"
        ),
        "limitations": [
            "Capacity measurements require validation against storage inventory.",
            "Low utilization is a review candidate, not proof that capacity can be removed.",
            "Monthly cost inputs are not verified enterprise bills.",
            "Performance metrics do not automatically translate into financial savings.",
            "Latency units must be verified before threshold-based conclusions."
        ]
    }


# ============================================================
# BACKUP
# ============================================================

def analyze_backup():
    inventory = read_csv(BACKUP_DIR / "backup_asset_inventory.csv")
    jobs = read_csv(BACKUP_DIR / "backup_job_logs.csv")
    policies = read_csv(BACKUP_DIR / "backup_policy_logs.csv")
    repositories = read_csv(BACKUP_DIR / "backup_repository_logs.csv")
    costs = read_csv(BACKUP_DIR / "backup_cost_records.csv")

    if any(x is None for x in [
        inventory, jobs, policies, repositories, costs
    ]):
        return {
            "status": "insufficient_data",
            "reason": "One or more backup input files are missing."
        }

    repositories["timestamp"] = pd.to_datetime(
        repositories["timestamp"], errors="coerce"
    )

    latest = (
        repositories.dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .groupby("repository_id")
        .tail(1)
        .copy()
    )

    utilization = pd.to_numeric(
        latest.get("utilization_pct", pd.Series(dtype=float)),
        errors="coerce"
    )

    high_utilization = latest[utilization >= 90]

    if "status" in jobs.columns:
        job_status = jobs["status"].value_counts().to_dict()
        failed_jobs = jobs[
            jobs["status"].astype(str).str.lower() == "failed"
        ]
    else:
        job_status = {}
        failed_jobs = jobs.iloc[0:0]

    cost_summary = (
        costs.groupby(
            ["billing_month", "currency", "cost_category"],
            dropna=False
        )["amount"].sum().reset_index()
    )

    return {
        "status": "analyzed",
        "asset_count": len(inventory),
        "repository_count": len(latest),
        "repositories_above_90_percent_utilization": len(high_utilization),
        "latest_repository_records": clean_records(
            latest.sort_values(
                "utilization_pct", ascending=False
            ) if "utilization_pct" in latest.columns else latest,
            20
        ),
        "backup_job_count": len(jobs),
        "job_status_counts": {
            str(k): int(v) for k, v in job_status.items()
        },
        "failed_job_count": len(failed_jobs),
        "failed_job_sample": clean_records(failed_jobs, 10),
        "retention_policy_sample": clean_records(policies, 20),
        "cost_summary": clean_records(cost_summary, 50),
        "financial_status": "cost_inputs_require_validation",
        "limitations": [
            "Repository utilization indicates capacity pressure, not unused capacity.",
            "Retention changes require recovery and compliance validation.",
            "Cost amounts must retain their source currency.",
            "Cost records require validation against actual bills and contracts.",
            "Failed backups indicate reliability issues, not automatically savings."
        ]
    }


# ============================================================
# COMPUTE / GPU
# ============================================================

def analyze_compute_gpu():
    servers = read_csv(
        PROCESSED / "compute_gpu" / "compute_gpu_server_metrics.csv"
    )

    clusters = read_csv(
        PROCESSED / "compute_gpu"
        / "compute_gpu_cluster_investigation.csv"
    )

    summary = read_json(
        PROCESSED / "compute_gpu" / "compute_gpu_summary.json"
    )

    utilization = read_csv(
        GPU_LOG_DIR / "gpu_utilization_metrics.csv"
    )

    if servers is None or clusters is None:
        return {
            "status": "insufficient_data",
            "reason": "Compute/GPU inventory files are missing."
        }

    distribution = {}

    if "gpu_specifications" in servers.columns:
        distribution = {
            str(k): int(v)
            for k, v in servers["gpu_specifications"]
            .fillna("Unknown").value_counts().items()
        }

    gpu_counts = pd.to_numeric(
        servers.get(
            "gpu_count_max_observed",
            pd.Series(dtype=float)
        ),
        errors="coerce"
    )

    cluster_count = None

    if summary and summary.get("unique_clusters") is not None:
        cluster_count = int(summary["unique_clusters"])
    elif "cluster_ids" in servers.columns:
        ids = set()
        for value in servers["cluster_ids"].dropna():
            ids.update(
                x.strip() for x in str(value).split(",") if x.strip()
            )
        cluster_count = len(ids)

    utilization_analysis = {
        "status": "unavailable",
        "reason": "GPU utilization metrics file is missing.",
        "server_count_with_metrics": 0,
        "low_utilization_server_count": 0,
        "average_gpu_utilization_pct": None,
        "by_gpu_model": {},
        "low_utilization_server_sample": []
    }

    if utilization is not None and not utilization.empty:
        required = {
            "server_id", "gpu_model",
            "gpu_utilization_pct", "timestamp"
        }

        missing = sorted(required - set(utilization.columns))

        if not missing:
            utilization["timestamp"] = pd.to_datetime(
                utilization["timestamp"], errors="coerce"
            )

            utilization["gpu_utilization_pct"] = pd.to_numeric(
                utilization["gpu_utilization_pct"], errors="coerce"
            )

            by_server = (
                utilization.dropna(
                    subset=["timestamp", "gpu_utilization_pct"]
                )
                .groupby(["server_id", "gpu_model"], as_index=False)
                .agg(
                    avg_gpu_utilization_pct=(
                        "gpu_utilization_pct", "mean"
                    ),
                    peak_gpu_utilization_pct=(
                        "gpu_utilization_pct", "max"
                    ),
                    observation_count=(
                        "gpu_utilization_pct", "count"
                    )
                )
            )

            low = by_server[
                by_server["avg_gpu_utilization_pct"] < 20
            ].copy()

            model_summary = (
                by_server.groupby("gpu_model")[
                    "avg_gpu_utilization_pct"
                ]
                .agg(["count", "mean", "max"])
                .round(2)
                .reset_index()
            )

            utilization_analysis = {
                "status": "analyzed",
                "server_count_with_metrics": int(
                    by_server["server_id"].nunique()
                ),
                "low_utilization_server_count": int(
                    low["server_id"].nunique()
                ),
                "average_gpu_utilization_pct": round(
                    float(by_server["avg_gpu_utilization_pct"].mean()),
                    2
                ),
                "by_gpu_model": clean_records(model_summary, 30),
                "low_utilization_server_sample": clean_records(
                    low.sort_values("avg_gpu_utilization_pct"), 20
                ),
                "measurement_level": (
                    "Server-level aggregate, not individual GPU telemetry."
                )
            }

    return {
        "status": "analyzed",
        "unique_server_records": len(servers),
        "unique_cluster_ids": cluster_count,
        "gpu_server_count_by_specification": distribution,
        "servers_with_gpu_inventory": int(
            (gpu_counts.fillna(0) > 0).sum()
        ),
        "maximum_gpu_count_observed_per_server": (
            float(gpu_counts.max())
            if not gpu_counts.dropna().empty else None
        ),
        "gpu_utilization_analysis": utilization_analysis,
        "server_sample": clean_records(servers, 10),
        "financial_status": (
            "cost_inputs_require_validation"
            if utilization_analysis["status"] == "analyzed"
            else "insufficient_data"
        ),
        "limitations": [
            "GPU utilization is server-level aggregate, not individual GPU telemetry.",
            "Some GPU model memory capacities are unavailable.",
            "Low average utilization is a review candidate, not proof that a GPU can be removed.",
            "Hardware, maintenance and electricity costs require validation."
        ]
    }


# ============================================================
# DATABASE
# ============================================================

def analyze_database():
    query_data = read_csv(ROOT / "data" / "raw_query_timings.csv")

    infrastructure = read_csv(
        DATABASE_LOG_DIR / "database_infrastructure_metrics.csv"
    )

    if query_data is None:
        return {
            "status": "insufficient_data",
            "reason": "Database query timing file is missing."
        }

    summary = numeric_summary(
        query_data,
        [
            "duration_ms",
            "cpu_time_ms",
            "wait_time_ms",
            "io_time_ms",
            "memory_peak_mb",
            "bytes_scanned"
        ]
    )

    query_ranking = []

    if {"query_id", "duration_ms"}.issubset(query_data.columns):
        grouped = (
            query_data.groupby("query_id")
            .agg(
                record_count=("duration_ms", "count"),
                average_duration_ms=("duration_ms", "mean"),
                maximum_duration_ms=("duration_ms", "max")
            )
            .reset_index()
            .sort_values("average_duration_ms", ascending=False)
        )
        query_ranking = clean_records(grouped, 10)

    slow_count = None
    slow_sample = []

    if {"duration_ms", "baseline_p99_ms"}.issubset(query_data.columns):
        duration = pd.to_numeric(
            query_data["duration_ms"], errors="coerce"
        )
        baseline = pd.to_numeric(
            query_data["baseline_p99_ms"], errors="coerce"
        )

        valid = duration.notna() & baseline.notna() & (baseline > 0)
        exceeded = query_data[valid & (duration > baseline)].copy()

        slow_count = len(exceeded)
        slow_sample = clean_records(
            exceeded.sort_values("duration_ms", ascending=False), 10
        )

    infrastructure_analysis = {
        "status": "unavailable",
        "reason": "Database infrastructure metrics file is missing.",
        "server_count": 0,
        "potential_overallocation_candidate_count": 0,
        "server_summary": []
    }

    if infrastructure is not None and not infrastructure.empty:
        required = {
            "database_id", "server_id", "database_engine", "timestamp",
            "used_cpu_pct", "memory_utilization_pct",
            "storage_utilization_pct", "allocated_vcpu",
            "allocated_memory_gb", "storage_allocated_gb"
        }

        missing = sorted(required - set(infrastructure.columns))

        if not missing:
            infrastructure["timestamp"] = pd.to_datetime(
                infrastructure["timestamp"], errors="coerce"
            )

            for col in [
                "used_cpu_pct", "memory_utilization_pct",
                "storage_utilization_pct", "allocated_vcpu",
                "allocated_memory_gb", "storage_allocated_gb",
                "monthly_cost_inr"
            ]:
                if col in infrastructure.columns:
                    infrastructure[col] = pd.to_numeric(
                        infrastructure[col], errors="coerce"
                    )

            by_server = (
                infrastructure.dropna(subset=["timestamp"])
                .groupby(
                    ["database_id", "server_id", "database_engine"],
                    as_index=False
                )
                .agg(
                    avg_cpu_utilization_pct=("used_cpu_pct", "mean"),
                    avg_memory_utilization_pct=(
                        "memory_utilization_pct", "mean"
                    ),
                    avg_storage_utilization_pct=(
                        "storage_utilization_pct", "mean"
                    ),
                    allocated_vcpu=("allocated_vcpu", "max"),
                    allocated_memory_gb=("allocated_memory_gb", "max"),
                    storage_allocated_gb=("storage_allocated_gb", "max"),
                    monthly_cost_inr=("monthly_cost_inr", "max")
                )
            )

            candidates = by_server[
                (by_server["avg_cpu_utilization_pct"] < 20)
                & (by_server["avg_memory_utilization_pct"] < 40)
                & (by_server["avg_storage_utilization_pct"] < 50)
            ].copy()

            infrastructure_analysis = {
                "status": "analyzed",
                "server_count": int(by_server["server_id"].nunique()),
                "potential_overallocation_candidate_count": int(
                    candidates["server_id"].nunique()
                ),
                "candidate_rule": (
                    "Average CPU below 20%, memory below 40%, "
                    "and storage below 50% across the observation window."
                ),
                "server_summary": clean_records(
                    by_server.sort_values("avg_cpu_utilization_pct"), 30
                ),
                "candidate_sample": clean_records(
                    candidates.sort_values("avg_cpu_utilization_pct"), 20
                ),
                "currency": "INR"
            }
        else:
            infrastructure_analysis["reason"] = (
                "Missing required columns: " + str(missing)
            )

    engine_counts = {}

    if "engine" in query_data.columns:
        engine_counts = {
            str(k): int(v)
            for k, v in query_data["engine"].value_counts().items()
        }

    return {
        "status": "analyzed",
        "total_query_records": len(query_data),
        "engine_record_counts": engine_counts,
        "performance_summary": summary,
        "records_exceeding_baseline_p99_count": slow_count,
        "slow_query_sample": slow_sample,
        "query_performance_ranking": query_ranking,
        "infrastructure_analysis": infrastructure_analysis,
        "financial_status": (
            "cost_inputs_require_validation"
            if infrastructure_analysis["status"] == "analyzed"
            else "insufficient_data"
        ),
        "limitations": [
            "Database infrastructure measurements require operational validation.",
            "Low utilization is a screening signal, not proof of overprovisioning.",
            "Query timings are not directly joined to database servers.",
            "Monthly cost inputs require validation.",
            "Query performance does not automatically establish infrastructure savings."
        ]
    }


# ============================================================
# LICENSING
# ============================================================

def analyze_licensing():
    features = read_csv(
        PROCESSED / "licensing" / "licensing_feature_metrics.csv"
    )

    summary = read_json(
        PROCESSED / "licensing" / "licensing_analytics_summary.json"
    )

    if features is None:
        return {
            "status": "insufficient_data",
            "reason": "Licensing feature metrics are missing."
        }

    reclaim = features.copy()

    if "reclaim_candidate" in reclaim.columns:
        reclaim = reclaim[
            reclaim["reclaim_candidate"]
            .astype(str).str.lower().isin(["true", "yes"])
        ]

    quantity = None

    if "reclaim_candidate_quantity" in reclaim.columns:
        quantity = int(
            pd.to_numeric(
                reclaim["reclaim_candidate_quantity"],
                errors="coerce"
            ).fillna(0).sum()
        )

    currency_counts = {}

    if "currency" in features.columns:
        currency_counts = {
            str(k): int(v)
            for k, v in features["currency"].value_counts().items()
        }

    return {
        "status": "analyzed",
        "feature_count": len(features),
        "reclaim_candidate_count": len(reclaim),
        "potential_reclaim_candidate_quantity": quantity,
        "currency_distribution": currency_counts,
        "analytics_summary": remove_origin_fields(summary or {}),
        "reclaim_candidate_sample": clean_records(reclaim, 20),
        "financial_status": "cost_assumptions_require_validation",
        "limitations": [
            "License costs require validation against contracts.",
            "Currency must remain as recorded in the source.",
            "Named-user reclamation requires assignment and activity data.",
            "Concurrent license reclamation requires contract validation.",
            "Potential financial impact is not confirmed savings."
        ]
    }


# ============================================================
# RUN ALL SIX DOMAINS
# ============================================================

def run_all_analyses():
    print("\nStarting six-domain cost opportunity analysis...")

    analyses = {
        "vmware": analyze_vmware(),
        "storage": analyze_storage(),
        "backup": analyze_backup(),
        "compute_gpu": analyze_compute_gpu(),
        "database": analyze_database(),
        "licensing": analyze_licensing()
    }

    # Final recursive cleanup of provenance fields.
    analyses = remove_origin_fields(analyses)

    successful = sum(
        1 for item in analyses.values()
        if item.get("status") == "analyzed"
    )

    report = {
        "report_name": "Infrastructure Cost Opportunity Analysis",
        "report_type": "six_domain_analysis",
        "domain_count": 6,
        "successfully_analyzed_domains": successful,
        "financial_policy": (
            "Do not report confirmed savings without validated "
            "cost inputs, quantities and assumptions."
        ),
        "domains": analyses
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=2,
            default=str,
            allow_nan=False
        )

    print("\n========== ANALYSIS SUMMARY ==========")

    for domain, result in analyses.items():
        print(f"{domain}: {result.get('status', 'unknown')}")

    print(f"\nSuccessfully analyzed: {successful}/6")
    print(f"\nReport saved:\n{OUTPUT_FILE}")

    return report


if __name__ == "__main__":
    run_all_analyses()
