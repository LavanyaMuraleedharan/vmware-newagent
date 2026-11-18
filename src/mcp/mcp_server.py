
from pathlib import Path
import json
import pandas as pd
import os
import hmac
import uvicorn

from mcp.server.fastmcp import FastMCP
class BearerAuthMiddleware:

    def __init__(self, app, expected_token):
        self.app = app
        self.expected_token = expected_token

    async def __call__(self, scope, receive, send):

        if (
            scope["type"] == "http"
            and scope["path"].rstrip("/") == "/mcp"
        ):

            headers = dict(scope.get("headers", []))

            authorization = headers.get(
                b"authorization", b""
            ).decode()

            scheme, _, supplied_token = authorization.partition(" ")

            valid = (
                scheme.lower() == "bearer"
                and hmac.compare_digest(
                    supplied_token,
                    self.expected_token
                )
            )

            if not valid:

                body = b'{"error":"Unauthorized"}'

                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                })

                await send({
                    "type": "http.response.body",
                    "body": body,
                })

                return

        await self.app(scope, receive, send)

# ============================================================
# PROJECT CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

PROCESSED = ROOT / "data" / "processed"
COST_AGENT_DIR = PROCESSED / "cost_agent"
ANALYSIS_FILE = COST_AGENT_DIR / "domain_analysis.json"

import os

mcp = FastMCP(
    "Infrastructure FinOps MCP Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000"))
)


# ============================================================
# COMMON HELPERS
# ============================================================

def remove_origin_fields(data):
    """Remove provenance fields recursively from MCP output."""

    if isinstance(data, dict):
        return {
            key: remove_origin_fields(value)
            for key, value in data.items()
            if key not in ("data_origin", "source_dataset")
        }

    if isinstance(data, list):
        return [remove_origin_fields(item) for item in data]

    return data


def response(payload):
    cleaned = remove_origin_fields(payload)

    return json.dumps(
        cleaned,
        indent=2,
        default=str,
        allow_nan=False
    )


def load_analysis():
    if not ANALYSIS_FILE.exists():
        raise FileNotFoundError(
            "Cost Agent analysis not found. "
            "Run python src/analytics/cost_opportunity_engine.py first."
        )

    with open(ANALYSIS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return remove_origin_fields(data)


def get_domain(domain):
    report = load_analysis()
    domains = report.get("domains", {})

    if domain not in domains:
        return {
            "domain": domain,
            "status": "unavailable",
            "reason": "Domain analysis not found."
        }

    return {
        "domain": domain,
        **domains[domain]
    }


def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    return pd.read_csv(path)


def clean_records(df, limit=10):
    if df is None or df.empty:
        return []

    result = df.head(limit).copy()

    result = result.drop(
        columns=["data_origin", "source_dataset"],
        errors="ignore"
    )

    result = result.astype(object).where(pd.notna(result), None)

    return result.to_dict(orient="records")


# ============================================================
# DATASET CATALOG
# ============================================================

@mcp.tool()
def get_dataset_catalog() -> str:
    """Return the available infrastructure dataset catalog."""

    candidates = [
        PROCESSED / "dataset_catalog.json",
        ROOT / "data" / "dataset_catalog.json"
    ]

    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return response(data)
            except Exception as exc:
                return response({
                    "status": "error",
                    "message": str(exc)
                })

    return response({
        "status": "unavailable",
        "message": "Dataset catalog file was not found."
    })


# ============================================================
# VMWARE
# ============================================================

@mcp.tool()
def get_vmware_metrics(top_n: int = 10) -> str:
    """Return VMware utilization and optimization findings."""

    result = get_domain("vmware")

    candidates = result.get("candidate_sample", [])

    return response({
        "domain": "vmware",
        "total_metric_records": result.get("total_records"),
        "total_recommendation_records": result.get(
            "recommendation_records"
        ),
        "low_utilization_candidates": result.get(
            "low_utilization_review_candidates"
        ),
        "utilization_summary": result.get("utilization_summary", {}),
        "candidate_records": candidates[:max(1, min(top_n, 50))],
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# STORAGE
# ============================================================

@mcp.tool()
def get_storage_metrics(top_n: int = 30) -> str:
    """Return storage performance and capacity findings."""

    result = get_domain("storage")

    capacity = result.get("capacity_analysis", {})
    performance = result.get("performance_summary", [])
    insights = result.get("optimization_insights", [])

    return response({
        "domain": "storage",
        "performance_group_count": result.get(
            "performance_group_count"
        ),
        "performance_summary": performance[:max(1, min(top_n, 100))],
        "optimization_insights": insights[:20],
        "capacity_analysis": capacity,
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


@mcp.tool()
def get_storage_domain_data() -> str:
    """Return detailed storage performance and capacity evidence."""

    return get_storage_metrics(top_n=50)


@mcp.tool()
def get_storage_recommendations(
    workload: str = "random_read",
    top_n: int = 5
) -> str:
    """Return storage recommendations for a selected workload."""

    path = (
        PROCESSED / "storage"
        / "storage_recommendations.csv"
    )

    try:
        df = load_csv(path)
    except FileNotFoundError as exc:
        return response({
            "domain": "storage",
            "status": "unavailable",
            "message": str(exc)
        })

    if "workload" not in df.columns:
        return response({
            "domain": "storage",
            "status": "insufficient_data",
            "message": "Workload column not found."
        })

    filtered = df[
        df["workload"].astype(str).str.lower()
        == workload.lower()
    ].copy()

    if filtered.empty:
        return response({
            "domain": "storage",
            "workload": workload,
            "recommendations": []
        })

    if "avg_iops" in filtered.columns:
        filtered = filtered.sort_values(
            "avg_iops",
            ascending=False
        )

    return response({
        "domain": "storage",
        "workload": workload,
        "recommendations": clean_records(
            filtered,
            max(1, min(top_n, 50))
        )
    })


# ============================================================
# BACKUP
# ============================================================

@mcp.tool()
def get_backup_metrics(top_n: int = 10) -> str:
    """Return backup repository, job, policy and cost findings."""

    result = get_domain("backup")

    return response({
        "domain": "backup",
        "asset_count": result.get("asset_count"),
        "repository_count": result.get("repository_count"),
        "repositories_above_90_percent_utilization": result.get(
            "repositories_above_90_percent_utilization"
        ),
        "latest_repository_metrics": result.get(
            "latest_repository_records", []
        )[:max(1, min(top_n, 50))],
        "backup_job_count": result.get("backup_job_count"),
        "job_status_counts": result.get("job_status_counts", {}),
        "failed_job_count": result.get("failed_job_count"),
        "failed_job_sample": result.get(
            "failed_job_sample", []
        )[:max(1, min(top_n, 50))],
        "retention_policy_sample": result.get(
            "retention_policy_sample", []
        ),
        "cost_summary": result.get("cost_summary", []),
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# COMPUTE / GPU
# ============================================================

@mcp.tool()
def get_compute_gpu_metrics(top_n: int = 10) -> str:
    """Return GPU inventory and utilization findings."""

    result = get_domain("compute_gpu")

    utilization = result.get(
        "gpu_utilization_analysis", {}
    )

    return response({
        "domain": "compute_gpu",
        "unique_server_records": result.get(
            "unique_server_records"
        ),
        "unique_cluster_ids": result.get("unique_cluster_ids"),
        "gpu_server_count_by_specification": result.get(
            "gpu_server_count_by_specification", {}
        ),
        "servers_with_gpu_inventory": result.get(
            "servers_with_gpu_inventory"
        ),
        "maximum_gpu_count_observed_per_server": result.get(
            "maximum_gpu_count_observed_per_server"
        ),
        "gpu_utilization_analysis": utilization,
        "server_sample": result.get(
            "server_sample", []
        )[:max(1, min(top_n, 50))],
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# DATABASE
# ============================================================

@mcp.tool()
def get_database_metrics(top_n: int = 10) -> str:
    """Return database query and infrastructure findings."""

    result = get_domain("database")

    return response({
        "domain": "database",
        "total_query_records": result.get("total_query_records"),
        "engine_record_counts": result.get(
            "engine_record_counts", {}
        ),
        "performance_summary": result.get(
            "performance_summary", {}
        ),
        "records_exceeding_baseline_p99_count": result.get(
            "records_exceeding_baseline_p99_count"
        ),
        "slow_query_sample": result.get(
            "slow_query_sample", []
        )[:max(1, min(top_n, 50))],
        "query_performance_ranking": result.get(
            "query_performance_ranking", []
        ),
        "infrastructure_analysis": result.get(
            "infrastructure_analysis", {}
        ),
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# LICENSING
# ============================================================

@mcp.tool()
def get_licensing_metrics(top_n: int = 10) -> str:
    """Return software license utilization and reclamation findings."""

    result = get_domain("licensing")

    return response({
        "domain": "licensing",
        "feature_count": result.get("feature_count"),
        "reclaim_candidate_count": result.get(
            "reclaim_candidate_count"
        ),
        "potential_reclaim_candidate_quantity": result.get(
            "potential_reclaim_candidate_quantity"
        ),
        "currency_distribution": result.get(
            "currency_distribution", {}
        ),
        "analytics_summary": result.get(
            "analytics_summary", {}
        ),
        "reclaim_candidate_sample": result.get(
            "reclaim_candidate_sample", []
        )[:max(1, min(top_n, 50))],
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# CONSOLIDATED COST AGENT ANALYSIS
# ============================================================

@mcp.tool()
def get_cost_agent_analysis() -> str:
    """Return the latest consolidated six-domain analysis."""

    return response(load_analysis())


# ============================================================
# SERVER STARTUP
# ============================================================

if __name__ == "__main__":
    import os

    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = int(os.getenv("PORT", "8000"))

    print("Starting Infrastructure FinOps MCP Server...")
    mcp.run(transport="streamable-http")



# ============================================================
# COMMON HELPERS
# ============================================================

def remove_origin_fields(data):
    """Remove provenance fields recursively from MCP output."""

    if isinstance(data, dict):
        return {
            key: remove_origin_fields(value)
            for key, value in data.items()
            if key not in ("data_origin", "source_dataset")
        }

    if isinstance(data, list):
        return [remove_origin_fields(item) for item in data]

    return data


def response(payload):
    cleaned = remove_origin_fields(payload)

    return json.dumps(
        cleaned,
        indent=2,
        default=str,
        allow_nan=False
    )


def load_analysis():
    if not ANALYSIS_FILE.exists():
        raise FileNotFoundError(
            "Cost Agent analysis not found. "
            "Run python src/analytics/cost_opportunity_engine.py first."
        )

    with open(ANALYSIS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return remove_origin_fields(data)


def get_domain(domain):
    report = load_analysis()
    domains = report.get("domains", {})

    if domain not in domains:
        return {
            "domain": domain,
            "status": "unavailable",
            "reason": "Domain analysis not found."
        }

    return {
        "domain": domain,
        **domains[domain]
    }


def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    return pd.read_csv(path)


def clean_records(df, limit=10):
    if df is None or df.empty:
        return []

    result = df.head(limit).copy()

    result = result.drop(
        columns=["data_origin", "source_dataset"],
        errors="ignore"
    )

    result = result.astype(object).where(pd.notna(result), None)

    return result.to_dict(orient="records")


# ============================================================
# DATASET CATALOG
# ============================================================

@mcp.tool()
def get_dataset_catalog() -> str:
    """Return the available infrastructure dataset catalog."""

    candidates = [
        PROCESSED / "dataset_catalog.json",
        ROOT / "data" / "dataset_catalog.json"
    ]

    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return response(data)
            except Exception as exc:
                return response({
                    "status": "error",
                    "message": str(exc)
                })

    return response({
        "status": "unavailable",
        "message": "Dataset catalog file was not found."
    })


# ============================================================
# VMWARE
# ============================================================

@mcp.tool()
def get_vmware_metrics(top_n: int = 10) -> str:
    """Return VMware utilization and optimization findings."""

    result = get_domain("vmware")

    candidates = result.get("candidate_sample", [])

    return response({
        "domain": "vmware",
        "total_metric_records": result.get("total_records"),
        "total_recommendation_records": result.get(
            "recommendation_records"
        ),
        "low_utilization_candidates": result.get(
            "low_utilization_review_candidates"
        ),
        "utilization_summary": result.get("utilization_summary", {}),
        "candidate_records": candidates[:max(1, min(top_n, 50))],
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# STORAGE
# ============================================================

@mcp.tool()
def get_storage_metrics(top_n: int = 30) -> str:
    """Return storage performance and capacity findings."""

    result = get_domain("storage")

    capacity = result.get("capacity_analysis", {})
    performance = result.get("performance_summary", [])
    insights = result.get("optimization_insights", [])

    return response({
        "domain": "storage",
        "performance_group_count": result.get(
            "performance_group_count"
        ),
        "performance_summary": performance[:max(1, min(top_n, 100))],
        "optimization_insights": insights[:20],
        "capacity_analysis": capacity,
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


@mcp.tool()
def get_storage_domain_data() -> str:
    """Return detailed storage performance and capacity evidence."""

    return get_storage_metrics(top_n=50)


@mcp.tool()
def get_storage_recommendations(
    workload: str = "random_read",
    top_n: int = 5
) -> str:
    """Return storage recommendations for a selected workload."""

    path = (
        PROCESSED / "storage"
        / "storage_recommendations.csv"
    )

    try:
        df = load_csv(path)
    except FileNotFoundError as exc:
        return response({
            "domain": "storage",
            "status": "unavailable",
            "message": str(exc)
        })

    if "workload" not in df.columns:
        return response({
            "domain": "storage",
            "status": "insufficient_data",
            "message": "Workload column not found."
        })

    filtered = df[
        df["workload"].astype(str).str.lower()
        == workload.lower()
    ].copy()

    if filtered.empty:
        return response({
            "domain": "storage",
            "workload": workload,
            "recommendations": []
        })

    if "avg_iops" in filtered.columns:
        filtered = filtered.sort_values(
            "avg_iops",
            ascending=False
        )

    return response({
        "domain": "storage",
        "workload": workload,
        "recommendations": clean_records(
            filtered,
            max(1, min(top_n, 50))
        )
    })


# ============================================================
# BACKUP
# ============================================================

@mcp.tool()
def get_backup_metrics(top_n: int = 10) -> str:
    """Return backup repository, job, policy and cost findings."""

    result = get_domain("backup")

    return response({
        "domain": "backup",
        "asset_count": result.get("asset_count"),
        "repository_count": result.get("repository_count"),
        "repositories_above_90_percent_utilization": result.get(
            "repositories_above_90_percent_utilization"
        ),
        "latest_repository_metrics": result.get(
            "latest_repository_records", []
        )[:max(1, min(top_n, 50))],
        "backup_job_count": result.get("backup_job_count"),
        "job_status_counts": result.get("job_status_counts", {}),
        "failed_job_count": result.get("failed_job_count"),
        "failed_job_sample": result.get(
            "failed_job_sample", []
        )[:max(1, min(top_n, 50))],
        "retention_policy_sample": result.get(
            "retention_policy_sample", []
        ),
        "cost_summary": result.get("cost_summary", []),
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# COMPUTE / GPU
# ============================================================

@mcp.tool()
def get_compute_gpu_metrics(top_n: int = 10) -> str:
    """Return GPU inventory and utilization findings."""

    result = get_domain("compute_gpu")

    utilization = result.get(
        "gpu_utilization_analysis", {}
    )

    return response({
        "domain": "compute_gpu",
        "unique_server_records": result.get(
            "unique_server_records"
        ),
        "unique_cluster_ids": result.get("unique_cluster_ids"),
        "gpu_server_count_by_specification": result.get(
            "gpu_server_count_by_specification", {}
        ),
        "servers_with_gpu_inventory": result.get(
            "servers_with_gpu_inventory"
        ),
        "maximum_gpu_count_observed_per_server": result.get(
            "maximum_gpu_count_observed_per_server"
        ),
        "gpu_utilization_analysis": utilization,
        "server_sample": result.get(
            "server_sample", []
        )[:max(1, min(top_n, 50))],
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# DATABASE
# ============================================================

@mcp.tool()
def get_database_metrics(top_n: int = 10) -> str:
    """Return database query and infrastructure findings."""

    result = get_domain("database")

    return response({
        "domain": "database",
        "total_query_records": result.get("total_query_records"),
        "engine_record_counts": result.get(
            "engine_record_counts", {}
        ),
        "performance_summary": result.get(
            "performance_summary", {}
        ),
        "records_exceeding_baseline_p99_count": result.get(
            "records_exceeding_baseline_p99_count"
        ),
        "slow_query_sample": result.get(
            "slow_query_sample", []
        )[:max(1, min(top_n, 50))],
        "query_performance_ranking": result.get(
            "query_performance_ranking", []
        ),
        "infrastructure_analysis": result.get(
            "infrastructure_analysis", {}
        ),
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# LICENSING
# ============================================================

@mcp.tool()
def get_licensing_metrics(top_n: int = 10) -> str:
    """Return software license utilization and reclamation findings."""

    result = get_domain("licensing")

    return response({
        "domain": "licensing",
        "feature_count": result.get("feature_count"),
        "reclaim_candidate_count": result.get(
            "reclaim_candidate_count"
        ),
        "potential_reclaim_candidate_quantity": result.get(
            "potential_reclaim_candidate_quantity"
        ),
        "currency_distribution": result.get(
            "currency_distribution", {}
        ),
        "analytics_summary": result.get(
            "analytics_summary", {}
        ),
        "reclaim_candidate_sample": result.get(
            "reclaim_candidate_sample", []
        )[:max(1, min(top_n, 50))],
        "financial_status": result.get("financial_status"),
        "limitations": result.get("limitations", [])
    })


# ============================================================
# CONSOLIDATED COST AGENT ANALYSIS
# ============================================================

@mcp.tool()
def get_cost_agent_analysis() -> str:
    """Return the latest consolidated six-domain analysis."""

    return response(load_analysis())


# ============================================================
# SERVER STARTUP
# ============================================================

if __name__ == "__main__":

    mcp_token = os.getenv("MCP_AUTH_TOKEN")

    if not mcp_token:
        raise RuntimeError(
            "MCP_AUTH_TOKEN is not configured"
        )

    app = BearerAuthMiddleware(
        mcp.streamable_http_app(),
        mcp_token
    )

    print(
        "Starting authenticated Infrastructure FinOps MCP Server..."
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000"))
    )
