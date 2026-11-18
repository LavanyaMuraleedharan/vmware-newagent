import tempfile
import json
from pathlib import Path
from datetime import datetime


# ============================================================
# 1. CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

TEMP_ROOT = Path(tempfile.gettempdir())

INPUT_JSON = (
    TEMP_ROOT
    / "cost_agent_reports"
    / "cost_agent_report.json"
)

OUTPUT_DIR = TEMP_ROOT / "finops_agent_reports"

OUTPUT_JSON = OUTPUT_DIR / "finops_agent_report.json"
OUTPUT_MD = OUTPUT_DIR / "finops_agent_report.md"


# ============================================================
# 2. FINANCIAL SCENARIO ASSUMPTIONS
# ============================================================

# These are configurable demonstration assumptions.
# They are not verified company savings.
#
# These assumptions are retained as compatibility fallbacks
# for older Cost Agent reports that do not contain
# potential_monthly_savings.

ASSUMPTIONS = {
    "VMware": {
        "method": "fixed_demo_estimate",
        "monthly_savings": 25000
    },

    "Storage": {
        "method": "percentage_of_cost_exposure",
        "percentage": 0.20
    },

    "Backup": {
        "method": "percentage_of_monthly_cost_baseline",
        "percentage": 0.05
    },

    "Compute/GPU": {
        "method": "fixed_demo_estimate",
        "monthly_savings": 15000
    },

    "Database": {
        "method": "percentage_of_candidate_cost_exposure",
        "percentage": 0.05
    },

    "Licensing": {
        "method": "percentage_of_candidate_opportunity",
        "percentage": 0.25
    }
}

IMPLEMENTATION_COST_INR = 100000

DOMAIN_ORDER = [
    "VMware",
    "Storage",
    "Backup",
    "Compute/GPU",
    "Database",
    "Licensing"
]


# ============================================================
# 3. COMMON HELPERS
# ============================================================

def load_json(path):

    if not path.exists():

        raise FileNotFoundError(
            f"Cost Agent report not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


def money(value):

    if value is None:
        return "N/A"

    return f"₹{float(value):,.2f}"


def get_number(data, keys):

    for key in keys:

        value = data.get(key)

        if value is None:
            continue

        try:
            return float(value)

        except (TypeError, ValueError):
            continue

    return None


def get_findings(cost_report):

    sections = cost_report.get("sections", {})

    findings = sections.get(
        "detected_cost_inefficiencies",
        []
    )

    if not isinstance(findings, list):

        raise ValueError(
            "Cost Agent report does not contain a valid "
            "detected_cost_inefficiencies list."
        )

    return findings


# ============================================================
# 4. EXTRACT FINANCIAL VALUES
# ============================================================

def extract_financial_values(finding):

    domain = finding.get("domain", "Unknown")

    reported_savings = get_number(
        finding,
        [
            "potential_monthly_savings_inr",
            "potential_monthly_savings"
        ]
    )

    storage_exposure = get_number(
        finding,
        [
            "estimated_monthly_cost_exposure_inr",
            "cost_exposure_inr",
            "cost_exposure"
        ]
    )

    database_exposure = get_number(
        finding,
        [
            "candidate_monthly_cost_exposure_inr",
            "candidate_cost_exposure",
            "cost_exposure"
        ]
    )

    monthly_baseline = get_number(
        finding,
        [
            "monthly_cost_baseline_inr",
            "monthly_cost_baseline",
            "monthly_cost_inr",
            "monthly_cost"
        ]
    )

    return {
        "domain": domain,

        "detected_issue": finding.get(
            "detected_issue",
            "No issue description available"
        ),

        "reported_monthly_savings": reported_savings,

        "storage_exposure": storage_exposure,

        "database_exposure": database_exposure,

        "monthly_baseline": monthly_baseline,

        "original_status": finding.get(
            "status",
            "Not specified"
        ),

        "savings_type": finding.get(
            "savings_type",
            "Scenario estimate"
        ),

        "original_calculation_method": finding.get(
            "calculation_method"
        ),

        "recovery_assumption_pct": get_number(
            finding,
            ["recovery_assumption_pct"]
        )
    }


# ============================================================
# 5. DOMAIN RISK EVALUATION
# ============================================================

def assess_domain(domain):

    risk_details = {

        "VMware": {
            "risk": "Low",

            "reason": (
                "Underutilized VM candidates require "
                "workload and application-owner validation."
            ),

            "recommendation": (
                "Review VM utilization, workload criticality, "
                "and application-owner approval before "
                "resizing or consolidating virtual machines."
            )
        },

        "Storage": {
            "risk": "Medium",

            "reason": (
                "Storage consolidation may affect application "
                "performance, availability, or redundancy."
            ),

            "recommendation": (
                "Validate storage dependencies, performance, "
                "redundancy, and capacity requirements before "
                "reallocating unused capacity."
            )
        },

        "Backup": {
            "risk": "High",

            "reason": (
                "High repository utilization and failed backup "
                "jobs may affect backup completion and "
                "recovery readiness."
            ),

            "recommendation": (
                "Investigate failed backup jobs, verify "
                "recovery points, and check retention policies "
                "before changing backup configurations."
            )
        },

        "Compute/GPU": {
            "risk": "Medium",

            "reason": (
                "Server and GPU capacity information is "
                "available, but actual GPU utilization "
                "is not established."
            ),

            "recommendation": (
                "Collect actual GPU utilization and workload "
                "metrics before identifying optimization "
                "opportunities."
            )
        },

        "Database": {
            "risk": "Medium",

            "reason": (
                "Queries exceeding the performance baseline "
                "may affect application response times "
                "and resource consumption."
            ),

            "recommendation": (
                "Review query execution plans, performance, "
                "workload peaks, and database resource "
                "requirements before making changes."
            )
        },

        "Licensing": {
            "risk": "Low",

            "reason": (
                "License candidates require usage, entitlement, "
                "and contract verification before reclamation."
            ),

            "recommendation": (
                "Verify actual license usage, contract terms, "
                "and entitlement rules before reclaiming "
                "license units."
            )
        }
    }

    return risk_details.get(
        domain,
        {
            "risk": "Unknown",

            "reason": (
                "Insufficient information to assess risk."
            ),

            "recommendation": (
                "Collect additional domain-specific information."
            )
        }
    )


# ============================================================
# 6. CALCULATE DOMAIN FINANCIAL ESTIMATES
# ============================================================

def calculate_domain_estimate(values):

    domain = values["domain"]

    assumption = ASSUMPTIONS.get(domain)

    if not assumption:

        return {
            "monthly_savings": 0.0,
            "calculation_method": "No configured assumption",
            "calculation_basis": None
        }

    method = assumption["method"]

    # --------------------------------------------------------
    # PREFERRED METHOD: USE COST AGENT SAVINGS DIRECTLY
    # --------------------------------------------------------
    # The updated Cost Agent already calculates the estimated
    # monthly savings for all six infrastructure domains.
    #
    # Therefore, FinOps must reuse the reported amount directly.
    #
    # This prevents double application of assumptions:
    #
    # Storage: 20% must not be applied again.
    # Backup: 5% must not be applied again.
    # Database: 5% must not be applied again.
    # Licensing: 25% must not be applied again.
    #
    # VMware and Compute/GPU estimates must also be consumed
    # directly rather than replaced with fixed values.
    #
    # The domain-specific calculations below are retained only
    # for compatibility with older Cost Agent reports.
    # --------------------------------------------------------

    reported_savings = values["reported_monthly_savings"]

    if reported_savings is not None:

        return {
            "monthly_savings": reported_savings,

            "calculation_method": (
                "cost_agent_reported_savings"
            ),

            "calculation_basis": {

                "cost_agent_reported_monthly_savings_inr": (
                    reported_savings
                ),

                "savings_type": values.get(
                    "savings_type",
                    "Scenario estimate"
                ),

                "cost_agent_calculation_method": (
                    values.get("original_calculation_method")
                ),

                "recovery_assumption_pct": (
                    values.get("recovery_assumption_pct")
                ),

                "note": (
                    "Used the Cost Agent estimate directly. "
                    "No additional recovery percentage was applied."
                )
            }
        }

    # --------------------------------------------------------
    # COMPATIBILITY FALLBACK: VMware and Compute/GPU
    # --------------------------------------------------------

    if method == "fixed_demo_estimate":

        monthly_savings = float(
            assumption["monthly_savings"]
        )

        return {
            "monthly_savings": monthly_savings,

            "calculation_method": method,

            "calculation_basis": (
                "Configured fixed demonstration estimate"
            )
        }

    # --------------------------------------------------------
    # COMPATIBILITY FALLBACK: STORAGE
    # --------------------------------------------------------

    if method == "percentage_of_cost_exposure":

        exposure = values["storage_exposure"] or 0.0

        percentage = assumption["percentage"]

        monthly_savings = exposure * percentage

        return {
            "monthly_savings": monthly_savings,

            "calculation_method": (
                "percentage_of_cost_exposure_fallback"
            ),

            "calculation_basis": {
                "cost_exposure_inr": exposure,
                "scenario_percentage": percentage
            }
        }

    # --------------------------------------------------------
    # COMPATIBILITY FALLBACK: BACKUP
    # --------------------------------------------------------

    if method == "percentage_of_monthly_cost_baseline":

        baseline = values["monthly_baseline"] or 0.0

        percentage = assumption["percentage"]

        monthly_savings = baseline * percentage

        return {
            "monthly_savings": monthly_savings,

            "calculation_method": method,

            "calculation_basis": {
                "monthly_cost_baseline_inr": baseline,
                "scenario_percentage": percentage
            }
        }

    # --------------------------------------------------------
    # COMPATIBILITY FALLBACK: DATABASE
    # --------------------------------------------------------

    if method == "percentage_of_candidate_cost_exposure":

        exposure = values["database_exposure"] or 0.0

        percentage = assumption["percentage"]

        monthly_savings = exposure * percentage

        return {
            "monthly_savings": monthly_savings,

            "calculation_method": method,

            "calculation_basis": {
                "candidate_cost_exposure_inr": exposure,
                "scenario_percentage": percentage
            }
        }

    # --------------------------------------------------------
    # COMPATIBILITY FALLBACK: LICENSING
    # --------------------------------------------------------

    if method == "percentage_of_candidate_opportunity":

        opportunity = (
            values["reported_monthly_savings"] or 0.0
        )

        percentage = assumption["percentage"]

        monthly_savings = opportunity * percentage

        return {
            "monthly_savings": monthly_savings,

            "calculation_method": method,

            "calculation_basis": {
                "reported_candidate_opportunity_inr": opportunity,
                "scenario_percentage": percentage
            }
        }

    return {
        "monthly_savings": 0.0,
        "calculation_method": "Unknown",
        "calculation_basis": None
    }


# ============================================================
# 7. EVALUATE EACH DOMAIN
# ============================================================

def evaluate_domain(finding):

    values = extract_financial_values(finding)

    domain = values["domain"]

    risk_info = assess_domain(domain)

    estimate = calculate_domain_estimate(values)

    monthly_savings = estimate["monthly_savings"]

    return {
        "domain": domain,

        "detected_issue": values["detected_issue"],

        "monthly_savings_inr": monthly_savings,

        "monthly_savings_display": (
            f"{money(monthly_savings)} (estimated)"
        ),

        "financial_status": (
            "Scenario estimate - validation required"
        ),

        "risk": risk_info["risk"],

        "risk_reason": risk_info["reason"],

        "priority": "P2",

        "recommendation": risk_info["recommendation"],

        "calculation_method": estimate["calculation_method"],

        "calculation_basis": estimate["calculation_basis"],

        "reported_monthly_savings_inr": (
            values["reported_monthly_savings"]
        ),

        "cost_exposure_inr": (
            values["storage_exposure"]
            if domain == "Storage"
            else values["database_exposure"]
            if domain == "Database"
            else None
        ),

        "monthly_cost_baseline_inr": (
            values["monthly_baseline"]
        )
    }


# ============================================================
# 8. PRIORITIZE RECOMMENDATIONS
# ============================================================

def prioritize(evaluations):

    priority_order = {
        "Backup": "P1",
        "Storage": "P2",
        "Licensing": "P2",
        "VMware": "P2",
        "Database": "P2",
        "Compute/GPU": "P3"
    }

    for item in evaluations:

        item["priority"] = priority_order.get(
            item["domain"],
            "P3"
        )

    return evaluations


# ============================================================
# 9. FINANCIAL METRICS
# ============================================================

def calculate_financial_metrics(evaluations):

    total_monthly_savings = sum(
        item["monthly_savings_inr"]
        for item in evaluations
    )

    estimated_annual_savings = (
        total_monthly_savings * 12
    )

    implementation_cost = float(
        IMPLEMENTATION_COST_INR
    )

    if total_monthly_savings > 0:

        payback_months = (
            implementation_cost / total_monthly_savings
        )

        payback_period = (
            f"{payback_months:.2f} months"
        )

    else:

        payback_months = None

        payback_period = "Not calculable"

    if implementation_cost > 0:

        roi = (
            (
                estimated_annual_savings
                - implementation_cost
            )
            / implementation_cost
        ) * 100

        roi_display = f"{roi:.2f}%"

    else:

        roi = None

        roi_display = "Not calculable"

    return {
        "estimated_monthly_savings_inr": (
            total_monthly_savings
        ),

        "estimated_annual_savings_inr": (
            estimated_annual_savings
        ),

        "implementation_cost_inr": (
            implementation_cost
        ),

        "implementation_cost_status": (
            "Illustrative scenario assumption"
        ),

        "payback_months": payback_months,

        "payback_period": payback_period,

        "first_year_roi_percentage": roi,

        "roi": roi_display,

        "calculation_note": (
            "All financial figures are scenario estimates "
            "based on Cost Agent findings and configurable "
            "assumptions. They are not verified or guaranteed "
            "savings. Actual savings, implementation costs, "
            "and operational impact must be validated before "
            "approval."
        )
    }


# ============================================================
# 10. BUILD RISK GROUPS
# ============================================================

def build_risk_groups(evaluations):

    risk_groups = {
        "Low": [],
        "Medium": [],
        "High": [],
        "Unknown": []
    }

    for item in evaluations:

        risk = item["risk"]

        risk_groups.setdefault(
            risk,
            []
        ).append(item["domain"])

    return risk_groups


# ============================================================
# 11. BUILD RECOMMENDATIONS
# ============================================================

def build_recommendations(evaluations):

    recommendations = []

    for item in evaluations:

        recommendations.append({

            "domain": item["domain"],

            "priority": item["priority"],

            "risk": item["risk"],

            "action": item["recommendation"]

        })

    priority_order = {
        "P1": 1,
        "P2": 2,
        "P3": 3
    }

    recommendations.sort(
        key=lambda item: priority_order.get(
            item["priority"],
            4
        )
    )

    return recommendations


# ============================================================
# 12. BUILD FINAL FINOPS REPORT
# ============================================================

def build_finops_report(cost_report, user_request=None):

    findings = get_findings(cost_report)

    if not findings:

        raise ValueError(
            "Cost Agent did not return any domain findings."
        )

    # Evaluate only the domains selected by Cost Agent.
    evaluations = []

    for domain in DOMAIN_ORDER:

        matching_findings = [
            item for item in findings
            if item.get("domain") == domain
        ]

        for finding in matching_findings:

            evaluations.append(
                evaluate_domain(finding)
            )

    # Include any additional domains not in DOMAIN_ORDER.
    for finding in findings:

        domain = finding.get("domain")

        if domain not in DOMAIN_ORDER:

            evaluations.append(
                evaluate_domain(finding)
            )

    if not evaluations:

        raise ValueError(
            "No valid domains were available for FinOps evaluation."
        )

    evaluations = prioritize(evaluations)

    metrics = calculate_financial_metrics(
        evaluations
    )

    risk_groups = build_risk_groups(
        evaluations
    )

    recommendations = build_recommendations(
        evaluations
    )

    selected_domains = [
        item["domain"] for item in evaluations
    ]

    request = (
        user_request
        or cost_report.get("user_request")
        or "Not provided"
    )

    conclusion = (
        f"The FinOps Agent evaluated {len(evaluations)} "
        f"requested infrastructure domain(s): "
        f"{', '.join(selected_domains)}. "
        f"It calculated estimated monthly savings of "
        f"{money(metrics['estimated_monthly_savings_inr'])}, "
        f"estimated annual savings of "
        f"{money(metrics['estimated_annual_savings_inr'])}, "
        f"an implementation cost assumption of "
        f"{money(metrics['implementation_cost_inr'])}, "
        f"a payback period of {metrics['payback_period']}, "
        f"and first-year ROI of {metrics['roi']}. "
        "These figures are illustrative estimates and require "
        "financial and operational validation. The report is "
        "forwarded to the Supervisor Agent for review and "
        "human approval."
    )

    return {
        "report_title": "FinOps Agent Evaluation Report",

        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),

        "currency": "INR",

        "user_request": request,

        "requested_domains": selected_domains,

        "source_report": str(INPUT_JSON),

        "evaluation_status": "Completed",

        "domains_evaluated": len(evaluations),

        "financial_evaluation": evaluations,

        "financial_metrics": metrics,

        "risk_evaluation": risk_groups,

        "recommendations": recommendations,

        "assumptions": ASSUMPTIONS,

        "implementation_cost_assumption_inr": (
            IMPLEMENTATION_COST_INR
        ),

        "final_finops_agent_response": conclusion,

        "supervisor_handoff": {

            "status": "ready_for_supervisor_review",

            "human_approval_required": True,

            "automatic_remediation_allowed": False,

            "message": (
                "The Supervisor Agent should review the "
                "financial estimates, domain risks, and "
                "recommendations. No infrastructure changes "
                "should occur without validation and explicit "
                "human approval."
            )
        }
    }


# ============================================================
# 13. CREATE MARKDOWN REPORT
# ============================================================

def create_markdown_report(report):

    metrics = report["financial_metrics"]

    lines = [

        "# FinOps Agent Evaluation Report",

        "",

        f"**User Request:** {report['user_request']}",

        "",

        "**Domains Evaluated:** "
        + ", ".join(report["requested_domains"]),

        "",

        f"**Generated at:** {report['generated_at']}",

        "",

        "## 1. Financial Evaluation",

        "",

        "| Domain | Monthly savings | Risk |",

        "|---|---:|---|"
    ]

    for item in report["financial_evaluation"]:

        lines.append(

            f"| {item['domain']} "
            f"| {item['monthly_savings_display']} "
            f"| {item['risk']} |"

        )

    lines += [

        "",

        "*All domain savings are scenario estimates based "
        "on Cost Agent findings and configurable assumptions. "
        "They are not verified or guaranteed savings.*",

        "",

        "## 2. Financial Metrics",

        "",

        (
            "**Estimated monthly savings:** "
            f"{money(metrics['estimated_monthly_savings_inr'])}"
        ),

        "",

        (
            "**Estimated annual savings:** "
            f"{money(metrics['estimated_annual_savings_inr'])}"
        ),

        "",

        (
            "**Assumed implementation cost:** "
            f"{money(metrics['implementation_cost_inr'])}"
        ),

        "",

        (
            "**Estimated payback period:** "
            f"{metrics['payback_period']}"
        ),

        "",

        (
            "**Estimated first-year ROI:** "
            f"{metrics['roi']}"
        ),

        "",

        metrics["calculation_note"],

        "",

        "## 3. Risk Evaluation",

        ""
    ]

    for risk_level in [
        "Low",
        "Medium",
        "High",
        "Unknown"
    ]:

        domains = report["risk_evaluation"].get(
            risk_level,
            []
        )

        if domains:

            lines.append(
                f"- **{risk_level} risk:** "
                f"{', '.join(domains)}."
            )

    lines += [

        "",

        "## 4. Recommendations",

        ""
    ]

    for recommendation in report["recommendations"]:

        lines.append(

            f"- **{recommendation['priority']} - "
            f"{recommendation['domain']}:** "
            f"{recommendation['action']}"

        )

    lines += [

        "",

        "## 5. Final FinOps Agent Response",

        "",

        report["final_finops_agent_response"],

        "",

        "**Supervisor handoff:**",

        report["supervisor_handoff"]["message"],

        "",

        "**Human approval required:** Yes",

        "**Automatic remediation allowed:** No"

    ]

    return "\n".join(lines)


# ============================================================
# 14. SAVE REPORTS
# ============================================================

def save_report(report):

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

    print("\nFinOps reports saved successfully:")

    print(f"JSON: {OUTPUT_JSON}")

    print(f"Markdown: {OUTPUT_MD}")


# ============================================================
# 15. MAIN FINOPS WORKFLOW
# ============================================================

def run_finops_agent(
    user_request=None,
    cost_findings=None,
    cost_report=None,
    save_files=True
):

    print("\n" + "=" * 65)
    print("FINOPS AGENT STARTED")
    print("=" * 65)

    try:

        # ----------------------------------------------------
        # Receive the Cost Agent report from Supervisor.
        # ----------------------------------------------------

        if cost_report is None and cost_findings is not None:

            cost_report = {
                "user_request": user_request,

                "sections": {
                    "detected_cost_inefficiencies": (
                        cost_findings
                    )
                }
            }

        # ----------------------------------------------------
        # Standalone mode:
        # Load the latest Cost Agent JSON report.
        # ----------------------------------------------------

        if cost_report is None:

            print("\nReading Cost Agent report...")

            cost_report = load_json(
                INPUT_JSON
            )

            print("Cost Agent report loaded.")

        else:

            print(
                "\nCost Agent report received directly."
            )

        if not isinstance(cost_report, dict):

            raise ValueError(
                "Cost Agent report must be a dictionary."
            )

        if user_request is None:

            user_request = cost_report.get(
                "user_request"
            )

        print("\nEvaluating financial findings and risks...")

        report = build_finops_report(
            cost_report,
            user_request
        )

        if save_files:
            save_report(report)

        print("\n" + "=" * 65)

        print(
            create_markdown_report(report)
        )

        print("\n" + "=" * 65)
        print("FINOPS AGENT COMPLETED")
        print("=" * 65)

        # Return the report to the Supervisor Agent.
        return report

    except Exception as error:

        print("\nFINOPS AGENT ERROR")
        print(str(error))

        raise


# ============================================================
# 16. ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_finops_agent()
