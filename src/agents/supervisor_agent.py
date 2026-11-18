
import asyncio
import json
import tempfile
import importlib.util
import inspect
from pathlib import Path
from datetime import datetime


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

TEMP_ROOT = Path(tempfile.gettempdir())

COST_AGENT_REPORT = (
    TEMP_ROOT
    / "cost_agent_reports"
    / "cost_agent_report.json"
)

FINOPS_AGENT_REPORT = (
    TEMP_ROOT
    / "finops_agent_reports"
    / "finops_agent_report.json"
)

OUTPUT_DIR = TEMP_ROOT / "supervisor_agent_reports"

OUTPUT_JSON = OUTPUT_DIR / "supervisor_agent_report.json"
OUTPUT_MD = OUTPUT_DIR / "supervisor_agent_report.md"


# ============================================================
# 2. DOMAIN CONFIGURATION
# ============================================================

DOMAIN_ORDER = [
    "VMware",
    "Storage",
    "Backup",
    "Compute/GPU",
    "Database",
    "Licensing"
]

# Supervisor priority is independent of FinOps operational risk.

DOMAIN_PRIORITY = {
    "VMware": "High",
    "Storage": "Medium",
    "Backup": "Low",
    "Compute/GPU": "High",
    "Database": "Medium",
    "Licensing": "High"
}

DOMAIN_DECISIONS = {

    "VMware": (
        "Recommend VM rightsizing after reviewing "
        "utilization history and workload requirements."
    ),

    "Storage": (
        "Recommend reclaiming eligible unused capacity "
        "after storage dependency, performance and "
        "redundancy validation."
    ),

    "Backup": (
        "Hold optimization until backup retention, "
        "recovery readiness and compliance requirements "
        "are checked."
    ),

    "Compute/GPU": (
        "Recommend reviewing idle GPU allocation after "
        "collecting actual GPU utilization and workload metrics."
    ),

    "Database": (
        "Recommend database rightsizing after validating "
        "query performance and workload requirements."
    ),

    "Licensing": (
        "Recommend reclaiming verified unused licenses "
        "after checking entitlements and contract terms."
    )
}


# ============================================================
# 3. GENERAL HELPERS
# ============================================================

def load_json(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Report not found: {path}"
        )

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False,
            default=str
        )


def money(value):

    if value is None:
        return "Not established"

    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not established"


def load_agent_module(module_name, script_path):

    if not script_path.exists():
        raise FileNotFoundError(
            f"{module_name} script not found: {script_path}"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        script_path
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load {module_name}"
        )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module


# ============================================================
# 4. ASYNCHRONOUS AGENT INVOCATION
# ============================================================

async def invoke_agent(
    module,
    agent_name,
    function_names,
    available_arguments,
    required_arguments
):
    """
    Invokes synchronous or asynchronous agent functions.

    The Supervisor waits for asynchronous agents to finish
    before processing their returned reports.
    """

    agent_function = None

    for function_name in function_names:

        candidate = getattr(
            module,
            function_name,
            None
        )

        if callable(candidate):
            agent_function = candidate
            break

    if agent_function is None:

        raise AttributeError(
            f"{agent_name} does not expose a supported function. "
            f"Expected one of: {function_names}"
        )

    signature = inspect.signature(agent_function)

    parameters = signature.parameters

    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )

    if accepts_kwargs:

        kwargs = available_arguments.copy()

    else:

        kwargs = {
            name: value
            for name, value in available_arguments.items()
            if name in parameters
        }

    missing = [
        argument
        for argument in required_arguments
        if argument not in kwargs
    ]

    if missing:

        raise TypeError(
            f"{agent_name} cannot receive the required inputs: "
            f"{missing}. Update its function signature."
        )

    print(
        f"\nInvoking {agent_name}: "
        f"{agent_function.__name__}()"
    )

    result = agent_function(**kwargs)

    # Support both async and normal Python functions.
    if inspect.isawaitable(result):
        result = await result

    return result


# ============================================================
# 5. COST AGENT
# ============================================================

async def run_cost_agent(user_request):

    print("\n" + "=" * 60)
    print("COST AGENT EXECUTION")
    print("=" * 60)

    module = load_agent_module(
        "cost_agent_module",
        COST_AGENT_SCRIPT
    )

    result = await invoke_agent(

        module=module,

        agent_name="Cost Agent",

        function_names=[
            "run_cost_agent"
        ],

        available_arguments={
            "user_request": user_request,
            "request": user_request
        },

        required_arguments=[
            "user_request"
        ]
    )

    if isinstance(result, dict):

        save_json(
            COST_AGENT_REPORT,
            result
        )

        cost_report = result

    else:

        # If the agent saves its report internally,
        # load the generated report.
        cost_report = load_json(
            COST_AGENT_REPORT
        )

    if not isinstance(cost_report, dict):
        raise ValueError(
            "Cost Agent did not return a valid report dictionary."
        )

    print("\nCost Agent execution completed.")

    return cost_report


# ============================================================
# 6. EXTRACT COST AGENT FINDINGS
# ============================================================

def extract_cost_findings(cost_report):

    sections = cost_report.get(
        "sections",
        {}
    )

    findings = sections.get(
        "detected_cost_inefficiencies",
        []
    )

    if not findings:

        findings = cost_report.get(
            "findings",
            cost_report.get("domains", [])
        )

    if isinstance(findings, dict):

        findings = list(
            findings.values()
        )

    if not isinstance(findings, list):

        raise ValueError(
            "Cost Agent findings must be a list."
        )

    return findings


# ============================================================
# 7. FINOPS AGENT
# ============================================================

async def run_finops_agent(
    user_request,
    cost_findings,
    cost_report
):

    print("\n" + "=" * 60)
    print("FINOPS AGENT EXECUTION")
    print("=" * 60)

    module = load_agent_module(
        "finops_agent_module",
        FINOPS_AGENT_SCRIPT
    )

    result = await invoke_agent(

        module=module,

        agent_name="FinOps Agent",

        function_names=[
            "run_finops_agent"
        ],

        available_arguments={

            "user_request": user_request,

            "request": user_request,

            "cost_findings": cost_findings,

            "findings": cost_findings,

            "cost_report": cost_report,

            "cost_agent_report": cost_report

        },

        required_arguments=[
            "user_request",
            "cost_findings"
        ]
    )

    if isinstance(result, dict):

        save_json(
            FINOPS_AGENT_REPORT,
            result
        )

        finops_report = result

    else:

        finops_report = load_json(
            FINOPS_AGENT_REPORT
        )

    if not isinstance(finops_report, dict):
        raise ValueError(
            "FinOps Agent did not return a valid report dictionary."
        )

    print("\nFinOps Agent execution completed.")

    return finops_report


# ============================================================
# 8. EXTRACT FINOPS RESULTS
# ============================================================

def extract_finops_findings(finops_report):

    findings = finops_report.get(
        "financial_evaluation",
        []
    )

    # Support the financial evaluation being nested
    # inside a sections dictionary.
    if not findings:

        sections = finops_report.get(
            "sections",
            {}
        )

        findings = sections.get(
            "financial_evaluation",
            []
        )

    if isinstance(findings, dict):

        findings = list(
            findings.values()
        )

    if not isinstance(findings, list):

        raise ValueError(
            "FinOps financial evaluation must be a list. "
            "Check the FinOps Agent JSON report structure."
        )

    return findings


# ============================================================
# 9. CONSOLIDATE DOMAIN RESULTS
# ============================================================

def consolidate_domains(
    cost_findings,
    finops_findings
):

    cost_by_domain = {
        item.get("domain"): item
        for item in cost_findings
        if isinstance(item, dict) and item.get("domain")
    }

    finops_by_domain = {
        item.get("domain"): item
        for item in finops_findings
        if isinstance(item, dict) and item.get("domain")
    }

    # Include domains returned by either agent.
    domains = list(DOMAIN_ORDER)

    for item in cost_findings + finops_findings:

        if not isinstance(item, dict):
            continue

        domain = item.get("domain")

        if domain and domain not in domains:
            domains.append(domain)

    results = []

    for domain in domains:

        cost = cost_by_domain.get(
            domain,
            {}
        )

        finops = finops_by_domain.get(
            domain,
            {}
        )

        if not cost and not finops:
            continue

        monthly_savings = finops.get(
            "monthly_savings_inr"
        )

        savings_display = finops.get(
            "monthly_savings_display"
        )

        if savings_display is None:
            savings_display = money(monthly_savings)

        results.append({

            "domain": domain,

            "detected_issue": cost.get(
                "detected_issue",
                "No Cost Agent finding received."
            ),

            "cost_agent_status": cost.get(
                "status",
                "Not specified"
            ),

            "monthly_savings_inr": monthly_savings,

            "monthly_savings_display": savings_display,

            "risk": finops.get(
                "risk",
                "Unknown"
            ),

            # Supervisor priority is independently assigned.
            "priority": DOMAIN_PRIORITY.get(
                domain,
                "Medium"
            ),

            "finops_recommendation": finops.get(
                "recommendation",
                "Further investigation required."
            ),

            "supervisor_decision": DOMAIN_DECISIONS.get(
                domain,
                "Further investigation and validation required."
            ),

            "financial_status": finops.get(
                "financial_status",
                "Not established"
            ),

            "approval_status": "Pending",

            "rpa_execution_status": "Not executed"

        })

    return results


# ============================================================
# 10. CALCULATE TOTAL SAVINGS
# ============================================================

def calculate_total_savings(
    domain_results,
    finops_report
):

    metrics = finops_report.get(
        "financial_metrics",
        {}
    )

    # Prefer the authoritative total from FinOps.
    total = metrics.get(
        "estimated_monthly_savings_inr"
    )

    if total is not None:

        return float(total)

    # Otherwise calculate from domain values.
    return sum(
        float(item["monthly_savings_inr"] or 0)
        for item in domain_results
    )


# ============================================================
# 11. AGENT EXECUTION SUMMARY
# ============================================================

def build_execution_summary(
    cost_findings,
    finops_findings
):

    return [

        {
            "agent": "Cost Agent",

            "status": "Completed",

            "result": (
                f"Analyzed the requested infrastructure scope "
                f"and identified {len(cost_findings)} findings."
            )
        },

        {
            "agent": "FinOps Agent",

            "status": "Completed",

            "result": (
                "Evaluated Cost Agent findings for potential "
                "savings, financial impact, ROI and operational risks."
            )
        },

        {
            "agent": "Supervisor Agent",

            "status": "Completed",

            "result": (
                "Consolidated agent outputs, checked domain "
                "recommendations and assigned optimization priorities."
            )
        },

        {
            "agent": "RPA Agent",

            "status": "Awaiting human approval",

            "result": (
                "Remediation actions are pending approval. "
                "No infrastructure changes have been executed."
            )
        }

    ]


# ============================================================
# 12. SUPERVISOR DECISIONS
# ============================================================

def build_supervisor_decisions(domain_results):

    decisions = []

    for item in domain_results:

        decisions.append({

            "domain": item["domain"],

            "risk": item["risk"],

            "priority": item["priority"],

            "decision": item["supervisor_decision"],

            "approval_required": True,

            "approval_status": "Pending"

        })

    return decisions


# ============================================================
# 13. FINAL SUPERVISOR RESPONSE
# ============================================================

def build_final_response(
    user_request,
    domain_results,
    total_monthly_savings
):

    analyzed_domains = [
        item["domain"]
        for item in domain_results
    ]

    high_priority = [
        item["domain"]
        for item in domain_results
        if item["priority"] == "High"
    ]

    high_risk = [
        item["domain"]
        for item in domain_results
        if item["risk"] == "High"
    ]

    response = (

        f"Your request was: '{user_request}'. "

        f"The Cost Agent and FinOps Agent analyzed "
        f"{len(analyzed_domains)} domain(s): "
        f"{', '.join(analyzed_domains)}. "

        "The combined estimated monthly savings are "
        f"{money(total_monthly_savings)}. "

    )

    if high_priority:

        response += (

            "High-priority optimization areas include "
            f"{', '.join(high_priority)}. "

        )

    if high_risk:

        response += (

            "High operational risk was identified in "
            f"{', '.join(high_risk)}. "
            "These recommendations require additional "
            "validation before implementation. "

        )

    response += (

        "The recommendations are ready for human review "
        "and approval. Approved actions can be forwarded "
        "to the RPA Agent for simulated execution. "
        "No infrastructure changes have been executed."

    )

    return response


# ============================================================
# 14. BUILD SUPERVISOR REPORT
# ============================================================

def build_supervisor_report(
    user_request,
    cost_report,
    finops_report
):

    cost_findings = extract_cost_findings(
        cost_report
    )

    finops_findings = extract_finops_findings(
        finops_report
    )

    domain_results = consolidate_domains(
        cost_findings,
        finops_findings
    )

    total_monthly_savings = calculate_total_savings(
        domain_results,
        finops_report
    )

    execution_summary = build_execution_summary(
        cost_findings,
        finops_findings
    )

    decisions = build_supervisor_decisions(
        domain_results
    )

    final_response = build_final_response(
        user_request,
        domain_results,
        total_monthly_savings
    )

    return {

        "report_title": "Supervisor Agent Final Report",

        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),

        "evaluation_status": "Completed",

        "user_request": user_request,

        "agent_execution_summary": execution_summary,

        "consolidated_optimization_report": {

            "domains": domain_results,

            "total_monthly_savings_inr": (
                total_monthly_savings
            ),

            "total_monthly_savings_display": (
                money(total_monthly_savings)
            )

        },

        "supervisor_decisions": decisions,

        "financial_metrics": finops_report.get(
            "financial_metrics",
            {}
        ),

        "final_supervisor_agent_response": final_response,

        "human_approval": {

            "required": True,

            "status": "Pending",

            "approved_actions": [],

            "rejected_actions": []

        },

        "rpa_handoff": {

            "status": "Awaiting human approval",

            "automation_allowed": False,

            "execution_completed": False

        },

        "financial_note": (

            "Financial values are scenario estimates based on "
            "the configured FinOps assumptions. They are not "
            "verified or guaranteed savings."

        )

    }


# ============================================================
# 15. CREATE MARKDOWN REPORT
# ============================================================

def create_markdown_report(report):

    consolidated = report[
        "consolidated_optimization_report"
    ]

    lines = [

        "# Supervisor Agent – Final Report",

        "",

        f"**Generated at:** {report['generated_at']}",

        "",

        "## 1. User Request",

        "",

        f'"{report["user_request"]}"',

        "",

        "## 2. Agent Execution Summary",

        "",

        "| Agent | Status | Result |",

        "|---|---|---|"

    ]

    for item in report["agent_execution_summary"]:

        lines.append(

            f"| {item['agent']} "
            f"| {item['status']} "
            f"| {item['result']} |"

        )

    lines += [

        "",

        "## 3. Consolidated Optimization Report",

        "",

        "| Domain | Monthly savings | Risk | Priority |",

        "|---|---:|---|---|"

    ]

    for item in consolidated["domains"]:

        lines.append(

            f"| {item['domain']} "
            f"| {item['monthly_savings_display']} "
            f"| {item['risk']} "
            f"| {item['priority']} |"

        )

    lines += [

        "",

        (
            f"| **Total** "
            f"| **{consolidated['total_monthly_savings_display']}** "
            f"| — | — |"
        ),

        "",

        f"*{report['financial_note']}*",

        "",

        "## 4. Supervisor Decisions",

        ""

    ]

    for item in report["supervisor_decisions"]:

        lines.append(

            f"- **{item['domain']}** "
            f"(Risk: {item['risk']}, "
            f"Priority: {item['priority']}): "
            f"{item['decision']}"

        )

    lines += [

        "",

        "## 5. Final Supervisor Agent Response",

        "",

        f'"{report["final_supervisor_agent_response"]}"',

        "",

        "**Human approval required:** Yes",

        "**Approval status:** Pending",

        "**RPA Agent:** Awaiting human approval",

        "**Automatic infrastructure changes:** Disabled",

        "",

        "### Financial Metrics",

        ""

    ]

    metrics = report["financial_metrics"]

    lines += [

        (
            "**Estimated monthly savings:** "
            f"{money(metrics.get('estimated_monthly_savings_inr'))}"
        ),

        "",

        (
            "**Estimated annual savings:** "
            f"{money(metrics.get('estimated_annual_savings_inr'))}"
        ),

        "",

        (
            "**Assumed implementation cost:** "
            f"{money(metrics.get('implementation_cost_inr'))}"
        ),

        "",

        (
            "**Estimated payback period:** "
            f"{metrics.get('payback_period', 'Not established')}"
        ),

        "",

        (
            "**Estimated first-year ROI:** "
            f"{metrics.get('roi', 'Not established')}"
        ),

        ""

    ]

    return "\n".join(lines)


# ============================================================
# 16. SAVE SUPERVISOR REPORT
# ============================================================

def save_supervisor_report(report):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    save_json(
        OUTPUT_JSON,
        report
    )

    markdown = create_markdown_report(
        report
    )

    with open(
        OUTPUT_MD,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(markdown)

    print("\nSupervisor reports saved:")

    print(f"JSON: {OUTPUT_JSON}")

    print(f"Markdown: {OUTPUT_MD}")


# ============================================================
# 17. MAIN ORCHESTRATION WORKFLOW
# ============================================================

async def run_supervisor_agent(user_request: str) -> dict:
    """
    Azure-callable workflow:
      User request -> Cost Agent -> FinOps Agent -> Supervisor report.

    No interactive input() is used here. The complete result is returned
    to the Azure Foundry Responses handler.
    """
    user_request = (user_request or "").strip()
    if not user_request:
        raise ValueError("Please provide a valid infrastructure optimization request.")

    print("\n" + "=" * 65)
    print("VMWARE MULTI-AGENT OPTIMIZATION WORKFLOW")
    print("=" * 65)
    print(f"User request: {user_request}")

    try:
        # 1. Run the existing Cost Agent.
        cost_report = await run_cost_agent(user_request)
        cost_findings = extract_cost_findings(cost_report)

        if not cost_findings:
            raise ValueError(
                "Cost Agent returned no findings. Check its report structure "
                "and whether the infrastructure data source is reachable."
            )

        print(f"Cost Agent findings received: {len(cost_findings)}")

        # 2. Run the existing FinOps Agent.
        finops_report = await run_finops_agent(
            user_request=user_request,
            cost_findings=cost_findings,
            cost_report=cost_report,
        )

        # 3. Consolidate the outputs.
        supervisor_report = build_supervisor_report(
            user_request=user_request,
            cost_report=cost_report,
            finops_report=finops_report,
        )

        # 4. Save the report and return it to the caller.
        save_supervisor_report(supervisor_report)
        markdown_report = create_markdown_report(supervisor_report)

        print("\n" + "=" * 65)
        print("SUPERVISOR AGENT COMPLETED")
        print("=" * 65)
        print(markdown_report)
        print("\nHuman approval is required before any RPA execution.")

        return {
            "status": "completed",
            "final_response": supervisor_report["final_supervisor_agent_response"],
            "report": supervisor_report,
            "markdown_report": markdown_report,
        }

    except Exception as error:
        print("\n" + "=" * 65)
        print("MULTI-AGENT WORKFLOW FAILED")
        print("=" * 65)
        print(f"{type(error).__name__}: {error}")
        # Propagate the error so the Azure handler can return a useful
        # failure message instead of silently returning an empty response.
        raise


# ============================================================
# 18. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    request = input("Enter your VMware optimization request: ").strip()
    try:
        result = asyncio.run(run_supervisor_agent(request))
        print(result["markdown_report"])
    except Exception as exc:
        raise SystemExit(f"Workflow failed: {exc}")
