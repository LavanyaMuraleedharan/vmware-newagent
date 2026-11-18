
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# =====================================================
# 1. CONFIGURATION
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "data" / "infrastructure_logs" / "licensing"
OUTPUT_DIR = ROOT / "data" / "processed" / "licensing"

EVENTS_FILE = INPUT_DIR / "license_events_template.csv"
INVENTORY_FILE = INPUT_DIR / "license_inventory_template.csv"
COST_FILE = INPUT_DIR / "license_cost_reference_template.csv"
GENERATION_SUMMARY_FILE = OUTPUT_DIR / "synthetic_generation_summary.json"

SESSION_OUTPUT = OUTPUT_DIR / "licensing_session_metrics.csv"
FEATURE_OUTPUT = OUTPUT_DIR / "licensing_feature_metrics.csv"
RECOMMENDATION_OUTPUT = OUTPUT_DIR / "licensing_optimization_recommendations.csv"
INVALID_OUTPUT = OUTPUT_DIR / "licensing_invalid_sessions.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "licensing_analytics_summary.json"

LOW_PEAK_UTILIZATION_THRESHOLD = 70.0
LOW_AVERAGE_UTILIZATION_THRESHOLD = 60.0

DATA_ORIGIN = "simulated"


# =====================================================
# 2. FILE UTILITIES
# =====================================================

def read_csv(path):

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fields):

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)


def parse_timestamp(value):
    return datetime.fromisoformat(value)


def safe_float(value, default=0.0):

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_observation_window():

    if not GENERATION_SUMMARY_FILE.exists():
        raise FileNotFoundError(
            "Generation summary not found. Run generate_licensing_data.py first."
        )

    with open(
        GENERATION_SUMMARY_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        summary = json.load(file)

    start = parse_timestamp(summary["simulation_start"])
    end = parse_timestamp(summary["simulation_end"])

    if end <= start:
        raise ValueError("Invalid licensing observation period.")

    return start, end


# =====================================================
# 3. LOAD INPUT DATA
# =====================================================

def load_data():

    events = read_csv(EVENTS_FILE)
    inventory = read_csv(INVENTORY_FILE)
    costs = read_csv(COST_FILE)

    window_start, window_end = load_observation_window()

    print("\nINPUT DATA LOADED")
    print("=" * 45)

    print(f"License events: {len(events)}")
    print(f"Inventory records: {len(inventory)}")
    print(f"Cost reference records: {len(costs)}")
    print(f"Observation start: {window_start}")
    print(f"Observation end: {window_end}")

    return (
        events,
        inventory,
        costs,
        window_start,
        window_end
    )


# =====================================================
# 4. BUILD LOOKUP TABLES
# =====================================================

def build_lookups(inventory, costs):

    inventory_lookup = {}
    cost_lookup = {}

    for record in inventory:

        key = (
            record["license_id"],
            record["software_feature"]
        )

        if key in inventory_lookup:
            raise ValueError(f"Duplicate inventory key: {key}")

        inventory_lookup[key] = record

    for record in costs:

        key = (
            record["software_product"],
            record["software_feature"]
        )

        if key in cost_lookup:
            raise ValueError(f"Duplicate cost reference: {key}")

        cost_lookup[key] = record

    return inventory_lookup, cost_lookup


# =====================================================
# 5. PAIR OUT AND IN EVENTS
# =====================================================

def pair_sessions(events):

    grouped = defaultdict(list)
    denied_events = []
    invalid_sessions = []

    for event in events:

        event_type = event["event_type"]

        if event_type == "DENIED":
            denied_events.append(event)
            continue

        if event_type not in ("OUT", "IN"):

            invalid_sessions.append({
                "session_id": event.get("session_id", ""),
                "issue": f"Unknown event type: {event_type}"
            })

            continue

        session_id = event.get("session_id", "").strip()

        if not session_id:

            invalid_sessions.append({
                "session_id": "",
                "issue": "Missing session ID"
            })

            continue

        grouped[session_id].append(event)

    valid_sessions = []

    identity_fields = [
        "license_id",
        "software_product",
        "software_feature",
        "username",
        "hostname",
        "license_quantity"
    ]

    for session_id, records in grouped.items():

        outs = [
            record for record in records
            if record["event_type"] == "OUT"
        ]

        ins = [
            record for record in records
            if record["event_type"] == "IN"
        ]

        if len(outs) != 1 or len(ins) != 1:

            invalid_sessions.append({
                "session_id": session_id,
                "issue": "Expected exactly one OUT and one IN"
            })

            continue

        out_event = outs[0]
        in_event = ins[0]

        if any(
            out_event.get(field) != in_event.get(field)
            for field in identity_fields
        ):

            invalid_sessions.append({
                "session_id": session_id,
                "issue": "OUT and IN details do not match"
            })

            continue

        try:

            start_time = parse_timestamp(
                out_event["event_timestamp"]
            )

            end_time = parse_timestamp(
                in_event["event_timestamp"]
            )

        except (ValueError, TypeError):

            invalid_sessions.append({
                "session_id": session_id,
                "issue": "Invalid timestamp"
            })

            continue

        quantity = safe_int(
            out_event["license_quantity"],
            -1
        )

        if quantity <= 0 or end_time <= start_time:

            invalid_sessions.append({
                "session_id": session_id,
                "issue": "Invalid quantity or session duration"
            })

            continue

        duration_minutes = (
            end_time - start_time
        ).total_seconds() / 60

        valid_sessions.append({

            "session_id": session_id,
            "license_id": out_event["license_id"],
            "software_product": out_event["software_product"],
            "software_feature": out_event["software_feature"],
            "username": out_event["username"],
            "hostname": out_event["hostname"],
            "license_quantity": quantity,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": round(duration_minutes, 2)

        })

    return valid_sessions, invalid_sessions, denied_events


# =====================================================
# 6. SESSION METRICS
# =====================================================

def build_session_metrics(sessions):

    rows = []

    for session in sessions:

        rows.append({

            "session_id": session["session_id"],
            "license_id": session["license_id"],
            "software_product": session["software_product"],
            "software_feature": session["software_feature"],
            "username": session["username"],
            "hostname": session["hostname"],
            "license_quantity": session["license_quantity"],
            "checkout_time": session["start_time"].isoformat(),
            "checkin_time": session["end_time"].isoformat(),
            "duration_minutes": session["duration_minutes"],
            "data_origin": DATA_ORIGIN

        })

    return rows


# =====================================================
# 7. CONCURRENT USAGE OVER THE FULL PERIOD
# =====================================================

def calculate_concurrency(
    feature_sessions,
    window_start,
    window_end
):

    total_window_seconds = (
        window_end - window_start
    ).total_seconds()

    if total_window_seconds <= 0:
        raise ValueError("Observation window must be positive.")

    boundaries = [
        (window_start, 0, 0),
        (window_end, 0, 0)
    ]

    for session in feature_sessions:

        # Clip sessions to the observation window.
        start_time = max(
            session["start_time"],
            window_start
        )

        end_time = min(
            session["end_time"],
            window_end
        )

        if end_time <= start_time:
            continue

        quantity = session["license_quantity"]

        # End events are processed before start events
        # when timestamps are identical.
        boundaries.append((
            end_time,
            0,
            -quantity
        ))

        boundaries.append((
            start_time,
            1,
            quantity
        ))

    boundaries.sort(
        key=lambda item: (item[0], item[1])
    )

    current_usage = 0
    peak_usage = 0
    weighted_usage_seconds = 0.0

    previous_time = window_start

    for timestamp, event_order, change in boundaries:

        elapsed_seconds = (
            timestamp - previous_time
        ).total_seconds()

        if elapsed_seconds > 0:

            weighted_usage_seconds += (
                current_usage * elapsed_seconds
            )

        current_usage += change

        if current_usage < 0:
            raise ValueError(
                "Concurrent usage became negative. Check session data."
            )

        peak_usage = max(
            peak_usage,
            current_usage
        )

        previous_time = timestamp

    average_usage = (
        weighted_usage_seconds / total_window_seconds
    )

    return {

        "peak_concurrent_usage": peak_usage,

        "average_concurrent_usage": round(
            average_usage,
            4
        )

    }


# =====================================================
# 8. FEATURE-LEVEL ANALYTICS
# =====================================================

def build_feature_metrics(
    sessions,
    inventory_lookup,
    cost_lookup,
    denied_events,
    window_start,
    window_end
):

    grouped_sessions = defaultdict(list)
    grouped_denials = defaultdict(int)

    for session in sessions:

        key = (
            session["license_id"],
            session["software_feature"]
        )

        grouped_sessions[key].append(session)

    for event in denied_events:

        key = (
            event["license_id"],
            event["software_feature"]
        )

        grouped_denials[key] += 1

    feature_rows = []

    for key, license_record in inventory_lookup.items():

        license_id, feature = key

        product = license_record["software_product"]

        entitlement = safe_int(
            license_record["entitled_quantity"]
        )

        metric = license_record["license_metric"]

        feature_sessions = grouped_sessions.get(
            key, []
        )

        denied_count = grouped_denials.get(
            key, 0
        )

        cost_record = cost_lookup.get(
            (product, feature)
        )

        if cost_record:

            annual_unit_cost = safe_float(
                cost_record["unit_cost"]
            )

            currency = cost_record["currency"]

            cost_status = cost_record["approval_status"]

        else:

            annual_unit_cost = None
            currency = ""
            cost_status = "missing_cost_reference"

        # -------------------------------------------------
        # Concurrent licenses
        # -------------------------------------------------

        if metric == "concurrent":

            concurrency = calculate_concurrency(
                feature_sessions,
                window_start,
                window_end
            )

            peak_usage = concurrency[
                "peak_concurrent_usage"
            ]

            average_usage = concurrency[
                "average_concurrent_usage"
            ]

            if entitlement > 0:

                peak_utilization = (
                    peak_usage / entitlement
                ) * 100

                average_utilization = (
                    average_usage / entitlement
                ) * 100

            else:

                peak_utilization = None
                average_utilization = None

            unused_at_peak = max(
                0,
                entitlement - peak_usage
            )

            # A reclaim candidate must have:
            # 1. Low peak utilization.
            # 2. Low full-window average utilization.
            # 3. No denied requests.
            reclaim_candidate = (
                entitlement > 0
                and peak_utilization is not None
                and average_utilization is not None
                and peak_utilization < LOW_PEAK_UTILIZATION_THRESHOLD
                and average_utilization < LOW_AVERAGE_UTILIZATION_THRESHOLD
                and denied_count == 0
            )

            if reclaim_candidate:

                reclaim_quantity = unused_at_peak

                if annual_unit_cost is not None:

                    estimated_impact = (
                        reclaim_quantity * annual_unit_cost
                    )

                else:

                    estimated_impact = None

                utilization_status = (
                    "low_utilization_reclaim_review"
                )

                recommendation = (
                    "Review entitlement reduction before renewal"
                )

                priority = "Medium"

            else:

                reclaim_quantity = 0
                estimated_impact = None

                if denied_count > 0:

                    utilization_status = (
                        "capacity_pressure_denied_requests"
                    )

                    recommendation = (
                        "Investigate denied requests and license capacity"
                    )

                    priority = "High"

                elif (
                    peak_utilization is not None
                    and peak_utilization >= 90
                ):

                    utilization_status = "high_utilization"

                    recommendation = (
                        "Retain capacity and monitor license demand"
                    )

                    priority = "High"

                elif (
                    peak_utilization is not None
                    and peak_utilization < LOW_PEAK_UTILIZATION_THRESHOLD
                ):

                    utilization_status = (
                        "low_peak_but_average_review_required"
                    )

                    recommendation = (
                        "Review usage pattern before considering entitlement changes"
                    )

                    priority = "Low"

                else:

                    utilization_status = "moderate_utilization"

                    recommendation = (
                        "Continue monitoring license usage"
                    )

                    priority = "Low"

        # -------------------------------------------------
        # Named-user licenses
        # -------------------------------------------------

        elif metric == "named_user":

            peak_usage = None
            average_usage = None
            peak_utilization = None
            average_utilization = None

            unused_at_peak = None
            reclaim_quantity = None
            estimated_impact = None

            utilization_status = (
                "named_user_activity_data_required"
            )

            recommendation = (
                "Review assigned users and actual user activity"
            )

            priority = "Undetermined"

        else:

            peak_usage = None
            average_usage = None
            peak_utilization = None
            average_utilization = None

            unused_at_peak = None
            reclaim_quantity = None
            estimated_impact = None

            utilization_status = "unsupported_license_metric"

            recommendation = (
                "Review license metric and usage measurement method"
            )

            priority = "Undetermined"

        total_session_minutes = sum(
            session["duration_minutes"]
            for session in feature_sessions
        )

        feature_rows.append({

            "license_id": license_id,
            "software_product": product,
            "software_feature": feature,
            "license_metric": metric,
            "entitled_quantity": entitlement,

            "total_checkout_sessions": len(feature_sessions),

            "total_session_duration_minutes": round(
                total_session_minutes,
                2
            ),

            "peak_concurrent_usage": peak_usage,

            "average_concurrent_usage_full_period": average_usage,

            "peak_utilization_pct": (
                round(peak_utilization, 2)
                if peak_utilization is not None
                else None
            ),

            "average_utilization_pct_full_period": (
                round(average_utilization, 2)
                if average_utilization is not None
                else None
            ),

            "denied_requests": denied_count,

            "unused_at_peak_quantity": unused_at_peak,

            "reclaim_candidate": (
                "Yes" if metric == "concurrent" and reclaim_candidate
                else "No" if metric == "concurrent"
                else "Not evaluated"
            ),

            "reclaim_candidate_quantity": reclaim_quantity,

            "annual_unit_cost": annual_unit_cost,

            "estimated_annual_financial_impact": (
                round(estimated_impact, 2)
                if estimated_impact is not None
                else None
            ),

            "currency": currency,

            "cost_assumption_status": cost_status,

            "utilization_status": utilization_status,

            "recommendation": recommendation,

            "priority": priority,

            "data_origin": DATA_ORIGIN

        })

    return feature_rows


# =====================================================
# 9. OPTIMIZATION RECOMMENDATIONS
# =====================================================

def build_recommendations(feature_rows):

    recommendations = []

    for row in feature_rows:

        recommendations.append({

            "license_id": row["license_id"],

            "software_product": row["software_product"],

            "software_feature": row["software_feature"],

            "license_metric": row["license_metric"],

            "entitled_quantity": row["entitled_quantity"],

            "peak_concurrent_usage": row["peak_concurrent_usage"],

            "peak_utilization_pct": row["peak_utilization_pct"],

            "average_utilization_pct_full_period": (
                row["average_utilization_pct_full_period"]
            ),

            "unused_at_peak_quantity": row["unused_at_peak_quantity"],

            "reclaim_candidate": row["reclaim_candidate"],

            "reclaim_candidate_quantity": (
                row["reclaim_candidate_quantity"]
            ),

            "estimated_annual_financial_impact": (
                row["estimated_annual_financial_impact"]
            ),

            "currency": row["currency"],

            "priority": row["priority"],

            "recommendation": row["recommendation"],

            "approval_required": "Yes",

            "execution_status": "Not executed",

            "data_origin": DATA_ORIGIN

        })

    return recommendations


# =====================================================
# 10. SUMMARY
# =====================================================

def build_summary(
    events,
    inventory,
    costs,
    sessions,
    invalid_sessions,
    denied_events,
    feature_rows,
    window_start,
    window_end
):

    event_counts = defaultdict(int)

    for event in events:
        event_counts[event["event_type"]] += 1

    concurrent_rows = [
        row for row in feature_rows
        if row["license_metric"] == "concurrent"
    ]

    named_user_rows = [
        row for row in feature_rows
        if row["license_metric"] == "named_user"
    ]

    candidate_rows = [
        row for row in concurrent_rows
        if row["reclaim_candidate"] == "Yes"
    ]

    high_utilization_count = sum(
        row["utilization_status"] in (
            "high_utilization",
            "capacity_pressure_denied_requests"
        )
        for row in concurrent_rows
    )

    total_reclaim_candidates = sum(
        row["reclaim_candidate_quantity"] or 0
        for row in candidate_rows
    )

    total_estimated_impact = sum(
        row["estimated_annual_financial_impact"] or 0
        for row in candidate_rows
    )

    summary = {

        "domain": "Licensing",

        "data_origin": DATA_ORIGIN,

        "observation_start": window_start.isoformat(),

        "observation_end": window_end.isoformat(),

        "observation_days": round(
            (window_end - window_start).total_seconds() / 86400,
            2
        ),

        "total_event_records": len(events),

        "inventory_records": len(inventory),

        "cost_reference_records": len(costs),

        "event_type_counts": dict(event_counts),

        "valid_sessions": len(sessions),

        "invalid_sessions": len(invalid_sessions),

        "denied_requests": len(denied_events),

        "software_features_analyzed": len(feature_rows),

        "concurrent_features_analyzed": len(concurrent_rows),

        "named_user_features_requiring_activity_review": len(
            named_user_rows
        ),

        "reclaim_candidate_features": len(candidate_rows),

        "high_utilization_or_capacity_pressure_features": (
            high_utilization_count
        ),

        "potential_reclaim_candidate_quantity": (
            total_reclaim_candidates
        ),

        "estimated_annual_financial_impact": round(
            total_estimated_impact,
            2
        ),

        "currency": "INR",

        "financial_estimate_note": (
            "Illustrative estimate based on simulated annual unit costs "
            "and qualifying low-utilization concurrent-license candidates. "
            "Not actual savings or a confirmed contractual reduction. "
            "Requires contract, business and procurement approval."
        ),

        "reclaim_eligibility": {
            "license_metric": "concurrent",
            "peak_utilization_below_pct": (
                LOW_PEAK_UTILIZATION_THRESHOLD
            ),
            "average_utilization_below_pct": (
                LOW_AVERAGE_UTILIZATION_THRESHOLD
            ),
            "denied_requests_required": 0
        },

        "named_user_note": (
            "Named-user utilization is not calculated from concurrent "
            "checkout events. Assignment and actual user activity data "
            "are required."
        )

    }

    return summary


# =====================================================
# 11. MAIN
# =====================================================

def main():

    print("\nLICENSING ANALYTICS STARTED")
    print("=" * 50)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    (
        events,
        inventory,
        costs,
        window_start,
        window_end
    ) = load_data()

    inventory_lookup, cost_lookup = build_lookups(
        inventory,
        costs
    )

    sessions, invalid_sessions, denied_events = pair_sessions(
        events
    )

    print("\nSESSION VALIDATION")
    print("=" * 45)

    print(f"Valid sessions: {len(sessions)}")
    print(f"Invalid sessions: {len(invalid_sessions)}")
    print(f"Denied requests: {len(denied_events)}")

    # Check that each session has a matching inventory record.
    unknown_sessions = [
        session for session in sessions
        if (
            session["license_id"],
            session["software_feature"]
        ) not in inventory_lookup
    ]

    if unknown_sessions:

        raise ValueError(
            f"{len(unknown_sessions)} sessions have no matching inventory record."
        )

    # Build session metrics.
    session_rows = build_session_metrics(sessions)

    # Build feature metrics.
    feature_rows = build_feature_metrics(
        sessions,
        inventory_lookup,
        cost_lookup,
        denied_events,
        window_start,
        window_end
    )

    # Build recommendations.
    recommendation_rows = build_recommendations(
        feature_rows
    )

    # Build summary.
    summary = build_summary(
        events,
        inventory,
        costs,
        sessions,
        invalid_sessions,
        denied_events,
        feature_rows,
        window_start,
        window_end
    )

    # Save session metrics.
    write_csv(
        SESSION_OUTPUT,
        session_rows,
        [
            "session_id",
            "license_id",
            "software_product",
            "software_feature",
            "username",
            "hostname",
            "license_quantity",
            "checkout_time",
            "checkin_time",
            "duration_minutes",
            "data_origin"
        ]
    )

    # Save feature metrics.
    if feature_rows:

        write_csv(
            FEATURE_OUTPUT,
            feature_rows,
            list(feature_rows[0].keys())
        )

    # Save recommendations.
    if recommendation_rows:

        write_csv(
            RECOMMENDATION_OUTPUT,
            recommendation_rows,
            list(recommendation_rows[0].keys())
        )

    # Save invalid sessions.
    write_csv(
        INVALID_OUTPUT,
        invalid_sessions,
        ["session_id", "issue"]
    )

    # Save summary.
    SUMMARY_OUTPUT.write_text(
        json.dumps(
            summary,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\nLICENSING ANALYTICS COMPLETED")
    print("=" * 50)

    print(f"Valid sessions: {len(sessions)}")
    print(f"Invalid sessions: {len(invalid_sessions)}")
    print(f"Denied requests: {len(denied_events)}")
    print(f"Features analyzed: {len(feature_rows)}")

    print(
        "Concurrent features:",
        summary["concurrent_features_analyzed"]
    )

    print(
        "Named-user features:",
        summary["named_user_features_requiring_activity_review"]
    )

    print(
        "Reclaim candidate features:",
        summary["reclaim_candidate_features"]
    )

    print(
        "Potential reclaim candidate quantity:",
        summary["potential_reclaim_candidate_quantity"]
    )

    print(
        "Estimated annual financial impact (INR):",
        summary["estimated_annual_financial_impact"]
    )

    print("\nGENERATED OUTPUT FILES")
    print("=" * 45)

    print(SESSION_OUTPUT)
    print(FEATURE_OUTPUT)
    print(RECOMMENDATION_OUTPUT)
    print(INVALID_OUTPUT)
    print(SUMMARY_OUTPUT)

    print("\nAll generated operational and cost records are simulated.")


if __name__ == "__main__":
    main()
