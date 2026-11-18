
import asyncio
import json
import traceback
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# ============================================================
# 1. CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm.llm_service import generate_response

MCP_URL = "http://127.0.0.1:8000/mcp"

OUTPUT_DIR = ROOT / "data/processed/cost_agent"
OUTPUT_JSON = OUTPUT_DIR / "cost_agent_report.json"
OUTPUT_MD = OUTPUT_DIR / "cost_agent_report.md"

STORAGE_FILE = (
    ROOT / "data/infrastructure_logs/storage/"
    "storage_capacity_metrics.csv"
)

BACKUP_COST_FILE = (
    ROOT / "data/infrastructure_logs/backup/"
    "backup_cost_records.csv"
)

BACKUP_REPO_FILE = (
    ROOT / "data/infrastructure_logs/backup/"
    "backup_repository_logs.csv"
)

DATABASE_FILE = (
    ROOT / "data/infrastructure_logs/database/"
    "database_infrastructure_metrics.csv"
)

LICENSING_FILE = (
    ROOT / "data/processed/licensing/"
    "licensing_feature_metrics.csv"
)

COMPUTE_SUMMARY_FILE = (
    ROOT / "data/processed/compute_gpu/"
    "compute_gpu_summary.json"
)

STORAGE_THRESHOLD = 30

# Demonstration assumptions.
# Replace these with validated financial values when available.

STORAGE_RECOVERY_PERCENTAGE = 0.20

VMWARE_MONTHLY_SAVINGS_INR = 25000.00

BACKUP_RECOVERY_PERCENTAGE = 0.05

COMPUTE_GPU_MONTHLY_SAVINGS_INR = 15000.00

DATABASE_RECOVERY_PERCENTAGE = 0.05

LICENSING_RECOVERY_PERCENTAGE = 0.25

load_dotenv(ROOT / ".env")


# ============================================================
# 2. INFRASTRUCTURE DOMAIN CONFIGURATION
# ============================================================

ALL_DOMAINS = [
    "VMware",
    "Storage",
    "Backup",
    "Compute/GPU",
    "Database",
    "Licensing"
]

DOMAIN_KEYWORDS = {
    "VMware": [
        "vmware", "virtual machine", "virtualization",
        "hypervisor", "vcenter", "vm rightsizing",
        "virtual machines"
    ],
    "Storage": [
        "storage", "capacity", "disk",
        "unused capacity", "storage utilization",
        "storage device", "storage devices"
    ],
    "Backup": [
        "backup", "repository", "backup failure",
        "backup job", "retention", "recovery"
    ],
    "Compute/GPU": [
        "compute", "gpu", "server", "cpu",
        "ram", "memory", "processor"
    ],
    "Database": [
        "database", "databases", "sql",
        "query", "queries", "db",
        "database performance"
    ],
    "Licensing": [
        "license", "licensing", "unused license",
        "software license", "entitlement"
    ]
}


def identify_requested_domains(user_request):

    request = user_request.lower()

    all_domain_phrases = [
        "all domains",
        "all six",
        "all infrastructure",
        "entire infrastructure",
        "complete infrastructure",
        "overall infrastructure",
        "everything"
    ]

    if any(phrase in request for phrase in all_domain_phrases):
        return ALL_DOMAINS.copy()

    selected = []

    for domain, keywords in DOMAIN_KEYWORDS.items():

        for keyword in keywords:

            if keyword in request:
                selected.append(domain)
                break

    if not selected:
        return ALL_DOMAINS.copy()

    return selected


# ============================================================
# 3. COMMON HELPER FUNCTIONS
# ============================================================

def number(value):

    try:

        if value is None or pd.isna(value):
            return None

        return float(value)

    except (ValueError, TypeError):
        return None


def format_number(value, decimals=2):

    value = number(value)

    if value is None:
        return "—"

    return f"{value:,.{decimals}f}"


def format_inr(value):

    value = number(value)

    if value is None:
        return "Not quantified"

    return f"₹{value:,.2f}"


def read_csv(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {path}"
        )

    return pd.read_csv(path)


def safe_sum(series):

    return number(
        pd.to_numeric(series, errors="coerce").sum()
    ) or 0.0


# ============================================================
# 4. MCP FUNCTIONS
# ============================================================

def parse_mcp_result(result):

    if result.isError:
        raise RuntimeError("MCP tool returned an error.")

    for content in result.content:

        if hasattr(content, "text"):

            try:
                return json.loads(content.text)

            except json.JSONDecodeError:
                continue

    raise ValueError("MCP returned no valid JSON.")


async def call_mcp(session, tool_name):

    print(f"Calling MCP tool: {tool_name}")

    result = await session.call_tool(
        tool_name,
        {}
    )

    return parse_mcp_result(result)


def find_numeric_value(data, key_fragments):

    if isinstance(data, dict):

        for key, value in data.items():

            key_lower = str(key).lower()

            if any(
                fragment in key_lower
                for fragment in key_fragments
            ):

                result = number(value)

                if result is not None:
                    return result

                if isinstance(value, list):
                    return len(value)

        for value in data.values():

            result = find_numeric_value(
                value,
                key_fragments
            )

            if result is not None:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_numeric_value(
                item,
                key_fragments
            )

            if result is not None:
                return result

    return None


# ============================================================
# 5. STORAGE ANALYSIS
# ============================================================

def analyze_storage():

    df = read_csv(STORAGE_FILE)

    required = [
        "timestamp",
        "storage_id",
        "total_capacity_tb",
        "used_capacity_tb",
        "free_capacity_tb",
        "utilization_pct",
        "monthly_cost_inr"
    ]

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Storage dataset is missing columns: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    latest = (
        df.sort_values("timestamp")
        .groupby("storage_id")
        .tail(1)
        .copy()
    )

    numeric_columns = [
        "total_capacity_tb",
        "used_capacity_tb",
        "free_capacity_tb",
        "utilization_pct",
        "monthly_cost_inr"
    ]

    for column in numeric_columns:

        latest[column] = pd.to_numeric(
            latest[column],
            errors="coerce"
        )

    latest = latest[
        (latest["total_capacity_tb"] > 0)
        & (latest["monthly_cost_inr"] >= 0)
    ].copy()

    candidates = latest[
        latest["utilization_pct"] < STORAGE_THRESHOLD
    ].copy()

    candidates["cost_exposure"] = (
        candidates["monthly_cost_inr"]
        * candidates["free_capacity_tb"]
        / candidates["total_capacity_tb"]
    )

    total_exposure = safe_sum(
        candidates["cost_exposure"]
    )

    estimated_savings = (
        total_exposure * STORAGE_RECOVERY_PERCENTAGE
    )

    detail = None

    if not candidates.empty:

        device = candidates.sort_values(
            "utilization_pct"
        ).iloc[0]

        detail = {
            "asset_id": str(device["storage_id"]),

            "device_type": str(
                device.get("device_type", "Not available")
            ),

            "total_capacity_tb": number(
                device["total_capacity_tb"]
            ),

            "used_capacity_tb": number(
                device["used_capacity_tb"]
            ),

            "unused_capacity_tb": number(
                device["free_capacity_tb"]
            ),

            "utilization_pct": number(
                device["utilization_pct"]
            ),

            "monthly_cost_inr": number(
                device["monthly_cost_inr"]
            ),

            "cost_exposure_inr": number(
                device["cost_exposure"]
            )
        }

    return {
        "device_count": len(latest),

        "underutilized_count": len(candidates),

        "average_utilization": number(
            latest["utilization_pct"].mean()
        ),

        "total_unused_capacity_tb": number(
            candidates["free_capacity_tb"].sum()
        ),

        "total_cost_exposure_inr": total_exposure,

        "estimated_monthly_savings_inr": round(
            estimated_savings, 2
        ),

        "recovery_assumption_pct": (
            STORAGE_RECOVERY_PERCENTAGE * 100
        ),

        "detail": detail
    }


# ============================================================
# 6. BACKUP ANALYSIS
# ============================================================

def analyze_backup():

    costs = read_csv(BACKUP_COST_FILE)

    repositories = read_csv(BACKUP_REPO_FILE)

    required_cost_columns = [
        "billing_month",
        "amount"
    ]

    required_repo_columns = [
        "timestamp",
        "repository_id",
        "utilization_pct",
        "free_capacity_gb"
    ]

    for column in required_cost_columns:

        if column not in costs.columns:
            raise ValueError(
                f"Backup cost dataset missing column: {column}"
            )

    for column in required_repo_columns:

        if column not in repositories.columns:
            raise ValueError(
                f"Backup repository dataset missing column: {column}"
            )

    costs["billing_month"] = pd.to_datetime(
        costs["billing_month"],
        errors="coerce"
    )

    latest_month = costs["billing_month"].max()

    if pd.isna(latest_month):
        raise ValueError(
            "No valid Backup billing month found."
        )

    latest_costs = costs[
        costs["billing_month"] == latest_month
    ].copy()

    latest_costs["amount"] = pd.to_numeric(
        latest_costs["amount"],
        errors="coerce"
    )

    monthly_cost = safe_sum(
        latest_costs["amount"]
    )

    repositories["timestamp"] = pd.to_datetime(
        repositories["timestamp"],
        errors="coerce"
    )

    latest_repositories = (
        repositories.sort_values("timestamp")
        .groupby("repository_id")
        .tail(1)
    )

    utilization = pd.to_numeric(
        latest_repositories["utilization_pct"],
        errors="coerce"
    )

    high_utilization = utilization >= 90

    return {
        "billing_month": latest_month.strftime("%Y-%m"),

        "monthly_cost_inr": monthly_cost,

        "repository_count": len(latest_repositories),

        "high_utilization_count": int(
            high_utilization.sum()
        ),

        "average_utilization": number(
            utilization.mean()
        ),

        "free_capacity_gb": number(
            pd.to_numeric(
                latest_repositories["free_capacity_gb"],
                errors="coerce"
            ).sum()
        )
    }


# ============================================================
# 7. DATABASE ANALYSIS
# ============================================================

def analyze_database():

    df = read_csv(DATABASE_FILE)

    required = [
        "database_id",
        "monthly_cost_inr",
        "used_cpu_pct",
        "memory_utilization_pct",
        "storage_utilization_pct"
    ]

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Database dataset missing columns: {missing}"
        )

    numeric_columns = [
        "monthly_cost_inr",
        "used_cpu_pct",
        "memory_utilization_pct",
        "storage_utilization_pct"
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    databases = (
        df.groupby("database_id")
        .agg(
            monthly_cost=("monthly_cost_inr", "first"),
            avg_cpu=("used_cpu_pct", "mean"),
            avg_memory=("memory_utilization_pct", "mean"),
            avg_storage=("storage_utilization_pct", "mean")
        )
        .reset_index()
    )

    candidates = databases[
        (databases["avg_cpu"] < 30)
        & (databases["avg_memory"] < 40)
        & (databases["avg_storage"] < 40)
    ]

    return {
        "database_count": len(databases),

        "candidate_count": len(candidates),

        "candidate_cost_exposure_inr": safe_sum(
            candidates["monthly_cost"]
        )
    }


# ============================================================
# 8. LICENSING ANALYSIS
# ============================================================

def analyze_licensing():

    df = read_csv(LICENSING_FILE)

    required = [
        "reclaim_candidate_quantity",
        "annual_unit_cost"
    ]

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Licensing dataset missing columns: {missing}"
        )

    df["reclaim_candidate_quantity"] = pd.to_numeric(
        df["reclaim_candidate_quantity"],
        errors="coerce"
    )

    df["annual_unit_cost"] = pd.to_numeric(
        df["annual_unit_cost"],
        errors="coerce"
    )

    candidates = df[
        (df["reclaim_candidate_quantity"] > 0)
        & (df["annual_unit_cost"].notna())
    ].copy()

    candidates["annual_opportunity"] = (
        candidates["reclaim_candidate_quantity"]
        * candidates["annual_unit_cost"]
    )

    annual = safe_sum(
        candidates["annual_opportunity"]
    )

    return {
        "feature_count": len(df),

        "candidate_feature_count": len(candidates),

        "candidate_quantity": number(
            candidates["reclaim_candidate_quantity"].sum()
        ),

        "annual_opportunity_inr": annual,

        "monthly_opportunity_inr": round(
            annual / 12, 2
        ),

        "assumption_status": (
            df["cost_assumption_status"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
            if "cost_assumption_status" in df.columns
            else []
        )
    }


# ============================================================
# 9. COMPUTE/GPU ANALYSIS
# ============================================================

def analyze_compute_gpu():

    if not COMPUTE_SUMMARY_FILE.exists():

        return {
            "unique_servers": None,
            "status": "Compute summary file unavailable"
        }

    with open(
        COMPUTE_SUMMARY_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# 10. BUILD DOMAIN FINDINGS
# ============================================================

def build_findings(
    analysis,
    storage,
    backup,
    database,
    licensing,
    compute_data,
    selected_domains
):

    domains = analysis.get("domains", {})

    findings = []

    # --------------------------------------------------------
    # VMware
    # --------------------------------------------------------

    if "VMware" in selected_domains:

        vmware = domains.get("vmware", {})

        vm_count = find_numeric_value(
            vmware,
            [
                "low_utilization_review_candidates",
                "low_utilization_candidate_count"
            ]
        )

        findings.append({
            "domain": "VMware",

            "detected_issue": (
                f"{int(vm_count):,} underutilized VMs"
                if vm_count is not None
                else "VMware utilization requires review"
            ),

            "potential_monthly_savings": (
                VMWARE_MONTHLY_SAVINGS_INR
            ),

            "savings_type": "Illustrative fixed estimate",

            "calculation_method": (
                "Configured VMware monthly demonstration estimate"
            ),

            "assumption_status": (
                "Not derived from verified VM-level costs"
            ),

            "cost_exposure": None,

            "status": (
                "Illustrative estimate; validate VM costs "
                "and utilization before action"
            )
        })

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    if "Storage" in selected_domains:

        findings.append({
            "domain": "Storage",

            "detected_issue": (
                f"{storage['underutilized_count']} underutilized "
                f"storage devices; "
                f"{format_number(storage['total_unused_capacity_tb'])} "
                "TB unused capacity"
            ),

            "cost_exposure": (
                storage["total_cost_exposure_inr"]
            ),

            "potential_monthly_savings": (
                storage["estimated_monthly_savings_inr"]
            ),

            "savings_type": "Illustrative estimate",

            "calculation_method": (
                "Cost exposure × configured recovery percentage"
            ),

            "recovery_assumption_pct": (
                storage["recovery_assumption_pct"]
            ),

            "status": (
                "Estimated opportunity; validate before action"
            )
        })

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    if "Backup" in selected_domains:

        backup_domain = domains.get("backup", {})

        failed_jobs = find_numeric_value(
            backup_domain,
            ["failed_job_count", "failed_jobs"]
        )

        backup_issue = (
            f"{backup['high_utilization_count']} repositories "
            "operating at high utilization"
        )

        if failed_jobs is not None:

            backup_issue += (
                f"; {int(failed_jobs):,} failed backup jobs"
            )

        backup_monthly_cost = number(
            backup.get("monthly_cost_inr")
        )

        backup_estimated_savings = (
            backup_monthly_cost * BACKUP_RECOVERY_PERCENTAGE
            if backup_monthly_cost is not None
            else None
        )

        findings.append({
            "domain": "Backup",

            "detected_issue": backup_issue,

            "potential_monthly_savings": (
                round(backup_estimated_savings, 2)
                if backup_estimated_savings is not None
                else None
            ),

            "monthly_cost_baseline": backup_monthly_cost,

            "savings_type": "Illustrative estimate",

            "calculation_method": (
                "Monthly backup cost × configured recovery percentage"
            ),

            "recovery_assumption_pct": (
                BACKUP_RECOVERY_PERCENTAGE * 100
            ),

            "cost_exposure": None,

            "status": (
                "Estimated opportunity; validate retention, "
                "recovery, and contract requirements"
                if backup_estimated_savings is not None
                else "Not quantified; monthly backup cost baseline unavailable"
            )
        })

    # --------------------------------------------------------
    # Compute/GPU
    # --------------------------------------------------------

    if "Compute/GPU" in selected_domains:

        server_count = number(
            compute_data.get("unique_servers")
        )

        if server_count is not None:

            compute_issue = (
                f"{int(server_count):,} servers inventoried; "
                "actual GPU utilization needs validation"
            )

        else:

            compute_issue = (
                "GPU/server inventory available, but "
                "utilization data is unavailable"
            )

        findings.append({
            "domain": "Compute/GPU",

            "detected_issue": compute_issue,

            "potential_monthly_savings": (
                COMPUTE_GPU_MONTHLY_SAVINGS_INR
            ),

            "savings_type": "Illustrative fixed estimate",

            "calculation_method": (
                "Configured Compute/GPU monthly demonstration estimate"
            ),

            "assumption_status": (
                "Not derived from verified server or GPU-level costs"
            ),

            "cost_exposure": None,

            "status": (
                "Illustrative estimate; validate actual CPU/GPU "
                "utilization and costs before action"
            )
        })

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    if "Database" in selected_domains:

        database_domain = domains.get("database", {})

        query_count = find_numeric_value(
            database_domain,
            [
                "records_exceeding_baseline_p99_count",
                "exceeding_baseline_count"
            ]
        )

        if query_count is not None:

            database_issue = (
                f"{int(query_count):,} query records exceed "
                "the performance baseline"
            )

        else:

            database_issue = (
                f"{database['candidate_count']} databases need "
                "resource-right-sizing review"
            )

        database_exposure = number(
            database.get("candidate_cost_exposure_inr")
        )

        database_estimated_savings = (
            database_exposure * DATABASE_RECOVERY_PERCENTAGE
            if database_exposure is not None
            else None
        )

        findings.append({
            "domain": "Database",

            "detected_issue": database_issue,

            "potential_monthly_savings": (
                round(database_estimated_savings, 2)
                if database_estimated_savings is not None
                else None
            ),

            "cost_exposure": database_exposure,

            "savings_type": "Illustrative estimate",

            "calculation_method": (
                "Candidate database cost exposure × configured "
                "recovery percentage"
            ),

            "recovery_assumption_pct": (
                DATABASE_RECOVERY_PERCENTAGE * 100
            ),

            "status": (
                "Estimated opportunity; validate workload, "
                "dependencies, and resource requirements"
                if database_estimated_savings is not None
                else "Not quantified; candidate database cost exposure unavailable"
            )
        })

    # --------------------------------------------------------
    # Licensing
    # --------------------------------------------------------

    if "Licensing" in selected_domains:

        licensing_opportunity = number(
            licensing.get("monthly_opportunity_inr")
        )

        licensing_estimated_savings = (
            licensing_opportunity * LICENSING_RECOVERY_PERCENTAGE
            if licensing_opportunity is not None
            else None
        )

        findings.append({
            "domain": "Licensing",

            "detected_issue": (
                f"{licensing['candidate_quantity']:,.0f} unused "
                "license candidate units"
            ),

            "potential_monthly_savings": (
                round(licensing_estimated_savings, 2)
                if licensing_estimated_savings is not None
                else None
            ),

            "savings_type": "Illustrative estimate",

            "calculation_method": (
                "Monthly license opportunity × configured "
                "recovery percentage"
            ),

            "recovery_assumption_pct": (
                LICENSING_RECOVERY_PERCENTAGE * 100
            ),

            "cost_exposure": None,

            "status": (
                "Estimated opportunity; validate license "
                "entitlement, usage, and contract terms"
            )
        })

    return findings


# ============================================================
# 11. DETAILED STORAGE EXAMPLE
# ============================================================

def build_storage_detail(storage):

    detail = storage.get("detail")

    if detail is None:
        return None

    return {
        "asset_id": detail["asset_id"],

        "total_capacity_tb": detail["total_capacity_tb"],

        "used_capacity_tb": detail["used_capacity_tb"],

        "unused_capacity_tb": detail["unused_capacity_tb"],

        "utilization_pct": detail["utilization_pct"],

        "monthly_cost_inr": detail["monthly_cost_inr"],

        "cost_exposure_inr": detail["cost_exposure_inr"],

        "estimated_monthly_savings_inr": round(
            detail["cost_exposure_inr"]
            * STORAGE_RECOVERY_PERCENTAGE,
            2
        ),

        "recovery_assumption_pct": (
            STORAGE_RECOVERY_PERCENTAGE * 100
        ),

        "calculation": (
            f"{detail['monthly_cost_inr']:.2f} × "
            f"{detail['unused_capacity_tb']:.2f} / "
            f"{detail['total_capacity_tb']:.2f}"
        ),

        "savings_calculation": (
            f"{detail['cost_exposure_inr']:.2f} × "
            f"{STORAGE_RECOVERY_PERCENTAGE:.2f}"
        ),

        "recommendation": (
            "Review whether unused capacity can be consolidated "
            "or reallocated without affecting applications, "
            "performance, redundancy or future requirements."
        )
    }


# ============================================================
# 12. AI-GENERATED COST AGENT SUMMARY
# ============================================================

def generate_summary(
    user_request,
    selected_domains,
    findings
):
    """Generate a manager-friendly summary using Azure AI Foundry.

    The LLM explains the findings only. Dataset analysis, financial
    calculations, assumptions, and report fields remain controlled
    by the existing Python logic.
    """

    prompt = f"""
You are the Cost Agent of an enterprise infrastructure FinOps platform.

USER REQUEST:
{user_request}

DOMAINS ANALYZED:
{json.dumps(selected_domains, indent=2, ensure_ascii=False)}

COST AGENT FINDINGS:
{json.dumps(findings, indent=2, ensure_ascii=False)}

INSTRUCTIONS:
1. Explain the identified technical inefficiencies domain by domain.
2. Use simple, professional language suitable for infrastructure and finance managers.
3. Mention monthly opportunity values only when present in the findings.
4. Never invent, recalculate, round, or modify any financial value.
5. Do not describe cost exposure or estimated opportunity as confirmed savings.
6. Clearly state that estimates are illustrative and depend on the assumptions in the findings.
7. Explain when financial, workload, operational, entitlement, or contract validation is required.
8. VMware: utilization and workload peaks must be validated.
9. Storage: check application dependencies, performance, redundancy, and future demand before reclaiming capacity.
10. Backup: validate retention, recovery, and compliance requirements.
11. Compute/GPU: validate actual CPU/GPU utilization and server costs.
12. Database: validate workload, query performance, dependencies, and resource requirements.
13. Licensing: validate license usage, entitlement, and contract terms.
14. State that findings are forwarded to the FinOps Agent for financial evaluation, savings assessment, ROI, payback, and risk analysis.
15. Do not claim that any infrastructure change has been executed or approved.
16. Keep the summary concise, approximately 150-200 words.
17. Return only the Cost Agent summary, without a title or separate report table.
"""

    try:
        result = generate_response(
            prompt=prompt,
            system_message=(
                "You are an enterprise infrastructure FinOps Cost Agent. "
                "Be accurate, concise, evidence-based, and conservative. "
                "Treat supplied findings as the only source of project facts "
                "and financial values. Never invent data."
            )
        )

        if result and result.strip():
            return result.strip()

        print(
            "AI summary generation returned an empty response. "
            "Using deterministic summary."
        )

    except Exception as error:
        print(
            "AI summary generation failed. "
            "Using deterministic summary."
        )
        print(error)

    # Deterministic fallback if Azure AI Foundry is unavailable.
    lines = [
        f"User request: {user_request}",
        "",
        "The Cost Agent completed the requested analysis.",
        "",
        "Domains analyzed: " + ", ".join(selected_domains) + "."
    ]

    for item in findings:
        domain = item["domain"]
        lines.append(f"{domain}: {item['detected_issue']}.")

        savings = item.get("potential_monthly_savings")
        if savings is not None:
            lines.append(
                "Estimated monthly opportunity: "
                f"{format_inr(savings)}. This is illustrative, not confirmed savings."
            )
        else:
            lines.append(
                "Monthly savings could not be quantified "
                "because a financial baseline is unavailable."
            )

        status = item.get("status")
        if status:
            lines.append(f"Validation required: {status}.")

    lines.extend([
        "",
        "The findings are forwarded to the FinOps Agent "
        "for financial evaluation, savings assessment, "
        "ROI, payback and risk analysis.",
        "",
        "All estimated opportunities must be validated before "
        "being treated as realized savings. No infrastructure "
        "changes have been executed or approved."
    ])

    return "\n".join(lines)


# ============================================================
# 13. BUILD FINAL REPORT
# ============================================================

def build_report(
    user_request,
    selected_domains,
    analysis,
    storage,
    backup,
    database,
    licensing,
    compute_data
):

    findings = build_findings(
        analysis,
        storage,
        backup,
        database,
        licensing,
        compute_data,
        selected_domains
    )

    storage_detail = (
        build_storage_detail(storage)
        if "Storage" in selected_domains
        else None
    )

    summary = generate_summary(
        user_request,
        selected_domains,
        findings
    )

    total_estimated = sum(
        item["potential_monthly_savings"]
        for item in findings
        if item.get("potential_monthly_savings") is not None
    )

    quantified_domains = sum(
        1 for item in findings
        if item.get("potential_monthly_savings") is not None
    )

    return {
        "report_title": "Cost Agent Analysis",

        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),

        "currency": "INR",

        "user_request": user_request,

        "requested_domains": selected_domains,

        "sections": {
            "detected_cost_inefficiencies": findings,

            "detailed_example": storage_detail,

            "final_cost_agent_response": summary
        },

        "total_opportunities": len(findings),

        "quantified_domains": quantified_domains,

        "unquantified_domains": (
            len(findings) - quantified_domains
        ),

        "total_estimated_monthly_opportunity_inr": round(
            total_estimated, 2
        ),

        "total_is_confirmed_savings": False,

        "finops_handoff": {
            "status": "ready_for_review",

            "user_request": user_request,

            "requested_domains": selected_domains,

            "findings": findings,

            "tasks": [
                "Evaluate estimated savings",
                "Validate financial assumptions",
                "Calculate ROI and payback period",
                "Assess operational risks",
                "Prioritize optimization opportunities"
            ]
        }
    }


# ============================================================
# 14. CREATE MARKDOWN REPORT
# ============================================================

def create_markdown_report(report):

    findings = report["sections"][
        "detected_cost_inefficiencies"
    ]

    detail = report["sections"]["detailed_example"]

    summary = report["sections"][
        "final_cost_agent_response"
    ]

    lines = [
        "# Cost Agent Analysis",
        "",
        f"**User Request:** {report['user_request']}",
        "",
        "**Domains Analyzed:** "
        + ", ".join(report["requested_domains"]),
        "",
        "## 1. Detected cost inefficiencies",
        "",
        "| Domain | Detected issue | Potential monthly savings |",
        "|---|---|---:|"
    ]

    for item in findings:

        savings = item.get("potential_monthly_savings")

        savings_text = format_inr(savings)

        lines.append(
            f"| {item['domain']} "
            f"| {item['detected_issue']} "
            f"| {savings_text} |"
        )

    total = report[
        "total_estimated_monthly_opportunity_inr"
    ]

    lines.extend([
        "",
        f"| **Total** | **{len(findings)} domains reviewed; "
        f"{report['quantified_domains']} quantified** "
        f"| **{format_inr(total)}** |",
        "",
        "*The displayed amounts are illustrative opportunities "
        "where assumptions are applied. They are not verified "
        "or realized savings.*",
        "",
        "### Financial calculation assumptions",
        "",
        f"- VMware: Fixed estimate of {format_inr(VMWARE_MONTHLY_SAVINGS_INR)} per month.",
        f"- Storage: {STORAGE_RECOVERY_PERCENTAGE:.0%} of cost exposure.",
        f"- Backup: {BACKUP_RECOVERY_PERCENTAGE:.0%} of monthly backup cost.",
        f"- Compute/GPU: Fixed estimate of {format_inr(COMPUTE_GPU_MONTHLY_SAVINGS_INR)} per month.",
        f"- Database: {DATABASE_RECOVERY_PERCENTAGE:.0%} of candidate cost exposure.",
        f"- Licensing: {LICENSING_RECOVERY_PERCENTAGE:.0%} of monthly license opportunity.",
        ""
    ])

    if detail:

        lines.extend([
            "## 2. Detailed storage example",
            "",
            f"**Asset:** {detail['asset_id']}",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Total capacity | "
            f"{format_number(detail['total_capacity_tb'])} TB |",
            f"| Used capacity | "
            f"{format_number(detail['used_capacity_tb'])} TB |",
            f"| Unused capacity | "
            f"{format_number(detail['unused_capacity_tb'])} TB |",
            f"| Utilization | "
            f"{format_number(detail['utilization_pct'])}% |",
            f"| Monthly cost | "
            f"{format_inr(detail['monthly_cost_inr'])} |",
            f"| Cost exposure | "
            f"{format_inr(detail['cost_exposure_inr'])} |",
            f"| Estimated monthly savings | "
            f"**{format_inr(detail['estimated_monthly_savings_inr'])}** |",
            "",
            f"**Cost exposure calculation:** "
            f"{detail['calculation']}",
            "",
            f"**Savings calculation:** "
            f"{detail['savings_calculation']} "
            f"({detail['recovery_assumption_pct']:.0f}% assumption)",
            "",
            f"**Recommendation:** {detail['recommendation']}",
            "",
            "*The recovery percentage is a demonstration assumption. "
            "Actual savings depend on successful capacity reclamation "
            "and a reduction in expenditure.*",
            ""
        ])

    lines.extend([
        "## 3. Final Cost Agent response",
        "",
        summary,
        ""
    ])

    return "\n".join(lines)


# ============================================================
# 15. SAVE REPORTS
# ============================================================

def save_report(report):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )

    markdown = create_markdown_report(report)

    with open(
        OUTPUT_MD,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(markdown)

    print("\nReports saved successfully:")

    print(f"JSON: {OUTPUT_JSON}")

    print(f"Markdown: {OUTPUT_MD}")


# ============================================================
# 16. MAIN COST AGENT WORKFLOW
# ============================================================

async def run_cost_agent(user_request):

    print("\n" + "=" * 65)
    print("COST AGENT STARTED")
    print("=" * 65)

    print(f"\nUser request received: {user_request}")

    selected_domains = identify_requested_domains(
        user_request
    )

    print("\nSelected infrastructure domains:")

    for domain in selected_domains:
        print(f"- {domain}")

    storage = {}
    backup = {}
    database = {}
    licensing = {}
    compute_data = {}
    analysis = {"domains": {}}

    try:

        # ----------------------------------------------------
        # Run requested local dataset analyses.
        # ----------------------------------------------------

        if "Storage" in selected_domains:

            print("\nRunning Storage analysis...")
            storage = analyze_storage()

        if "Backup" in selected_domains:

            print("\nRunning Backup analysis...")
            backup = analyze_backup()

        if "Database" in selected_domains:

            print("\nRunning Database analysis...")
            database = analyze_database()

        if "Licensing" in selected_domains:

            print("\nRunning Licensing analysis...")
            licensing = analyze_licensing()

        if "Compute/GPU" in selected_domains:

            print("\nRunning Compute/GPU analysis...")
            compute_data = analyze_compute_gpu()

        # ----------------------------------------------------
        # Call MCP only when a requested domain needs it.
        # ----------------------------------------------------

        mcp_domains = {
            "VMware",
            "Backup",
            "Database",
            "Compute/GPU"
        }

        if any(
            domain in mcp_domains
            for domain in selected_domains
        ):

            print("\nConnecting to MCP server...")

            async with streamablehttp_client(MCP_URL) as (
                read,
                write,
                _
            ):

                async with ClientSession(read, write) as session:

                    await session.initialize()

                    print("Connected to MCP server.")

                    if any(
                        domain in selected_domains
                        for domain in [
                            "VMware", "Backup", "Database"
                        ]
                    ):

                        analysis = await call_mcp(
                            session,
                            "get_cost_agent_analysis"
                        )

                    if "Compute/GPU" in selected_domains:

                        mcp_compute = await call_mcp(
                            session,
                            "get_compute_gpu_metrics"
                        )

                        compute_data = {
                            **compute_data,
                            "mcp_metrics": mcp_compute
                        }

                        if not compute_data.get("unique_servers"):

                            server_count = find_numeric_value(
                                mcp_compute,
                                [
                                    "unique_servers",
                                    "server_count",
                                    "total_servers"
                                ]
                            )

                            if server_count is not None:
                                compute_data["unique_servers"] = (
                                    server_count
                                )

        print("\nBuilding Cost Agent findings...")

        report = build_report(
            user_request,
            selected_domains,
            analysis,
            storage,
            backup,
            database,
            licensing,
            compute_data
        )

        save_report(report)

        print("\n" + "=" * 65)

        print(create_markdown_report(report))

        print("\n" + "=" * 65)
        print("COST AGENT COMPLETED")
        print("=" * 65)

        return report

    except BaseException as exc:
        import traceback

        print("\nCOST AGENT ERROR")
        print("\nDetailed error information:")

        traceback.print_exception(
            type(exc),
            exc,
            exc.__traceback__
        )

        if isinstance(exc, BaseExceptionGroup):
            print("\nNested exceptions:")

            for index, sub_error in enumerate(exc.exceptions, 1):
                print(f"\nException {index}:")

                traceback.print_exception(
                    type(sub_error),
                    sub_error,
                    sub_error.__traceback__
                )

        raise


# ============================================================
# 17. STANDALONE ENTRY POINT
# ============================================================

if __name__ == "__main__":

    request = input(
        "\nEnter your FinOps request: "
    ).strip()

    if not request:

        print("Please enter a valid request.")

    else:

        asyncio.run(
            run_cost_agent(request)
        )
