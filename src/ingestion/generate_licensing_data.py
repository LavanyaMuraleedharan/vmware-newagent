
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# =====================================================
# 1. CONFIGURATION
# =====================================================

SEED = 42
DAYS = 90

END_DATE = datetime(2026, 11, 16, 23, 59, 0)

START_DATE = (
    END_DATE.replace(hour=0, minute=0, second=0)
    - timedelta(days=DAYS - 1)
)

ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "data" / "infrastructure_logs" / "licensing"
SUMMARY_DIR = ROOT / "data" / "processed" / "licensing"

INVENTORY_FILE = OUTPUT_DIR / "license_inventory_template.csv"
EVENTS_FILE = OUTPUT_DIR / "license_events_template.csv"
COST_FILE = OUTPUT_DIR / "license_cost_reference_template.csv"
SUMMARY_FILE = SUMMARY_DIR / "synthetic_generation_summary.json"

rng = random.Random(SEED)

# =====================================================
# 2. SYNTHETIC SOFTWARE FEATURES
# =====================================================

PRODUCTS = [
    ("CAD_Pro", "DesignSuite", "Publisher-A", "named_user", 40, "low"),
    ("CAD_Render", "DesignSuite", "Publisher-A", "concurrent", 25, "moderate"),
    ("SIM_Core", "SimuWorks", "Publisher-B", "concurrent", 30, "high"),
    ("SIM_Advanced", "SimuWorks", "Publisher-B", "concurrent", 18, "high"),
    ("MATLAB_Base", "NumeriLab", "Publisher-C", "concurrent", 50, "low"),
    ("MATLAB_Toolbox", "NumeriLab", "Publisher-C", "concurrent", 35, "moderate"),
    ("CAE_Solver", "EngiSoft", "Publisher-D", "concurrent", 22, "high"),
    ("CAE_PrePost", "EngiSoft", "Publisher-D", "concurrent", 28, "moderate"),
    ("PCB_Design", "CircuitPro", "Publisher-E", "concurrent", 20, "moderate"),
    ("PCB_Sim", "CircuitPro", "Publisher-E", "concurrent", 16, "high"),
    ("DataViz_Pro", "VizWorks", "Publisher-F", "named_user", 35, "low"),
    ("DataViz_Advanced", "VizWorks", "Publisher-F", "concurrent", 15, "moderate"),
    ("Dev_IDE", "CodeForge", "Publisher-G", "named_user", 60, "low"),
    ("Dev_Test", "CodeForge", "Publisher-G", "concurrent", 24, "high"),
    ("GIS_Desktop", "GeoSuite", "Publisher-H", "concurrent", 18, "low"),
    ("GIS_Analysis", "GeoSuite", "Publisher-H", "concurrent", 12, "moderate"),
    ("Media_Edit", "MediaLab", "Publisher-I", "named_user", 25, "low"),
    ("Media_Render", "MediaLab", "Publisher-I", "concurrent", 14, "high"),
    ("DB_Admin", "DataAdmin", "Publisher-J", "concurrent", 32, "moderate"),
    ("DB_Performance", "DataAdmin", "Publisher-J", "concurrent", 20, "high"),
]

DEPARTMENTS = [
    "Engineering",
    "Product",
    "Research",
    "IT Operations",
    "Data"
]

USERS = [f"user_{i:03d}" for i in range(1, 151)]
HOSTS = [f"workstation_{i:03d}" for i in range(1, 101)]

DAEMONS = [
    f"daemon_{c.lower()}" for c in "ABCDEFGHIJ"
]

# =====================================================
# 3. CSV WRITER
# =====================================================

def write_csv(path, fields, rows):

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


# =====================================================
# 4. INVENTORY AND COST GENERATION
# =====================================================

def build_inventory_and_costs():

    inventory = []
    costs = []
    feature_info = {}

    for index, item in enumerate(PRODUCTS, start=1):

        (
            feature,
            product,
            publisher,
            metric,
            entitlement,
            profile
        ) = item

        license_id = f"SIM-LIC-{index:03d}"

        assigned = max(
            1,
            int(entitlement * rng.uniform(0.70, 0.95))
        )

        installed = rng.randint(
            assigned,
            entitlement + 5
        )

        annual_unit_cost = round(
            rng.uniform(5000, 50000),
            2
        )

        contract_start = (
            START_DATE - timedelta(days=365)
        ).date()

        contract_end = (
            END_DATE + timedelta(days=180)
        ).date()

        renewal_date = (
            END_DATE + timedelta(days=rng.randint(30, 180))
        ).date()

        inventory.append({
            "license_id": license_id,
            "software_feature": feature,
            "software_product": product,
            "publisher": publisher,
            "version": f"{rng.randint(1, 5)}.{rng.randint(0, 9)}",
            "license_metric": metric,
            "entitled_quantity": entitlement,
            "installed_quantity": installed,
            "assigned_quantity": assigned,
            "contract_start_date": contract_start.isoformat(),
            "contract_end_date": contract_end.isoformat(),
            "renewal_date": renewal_date.isoformat(),
            "support_maintenance_cost": round(
                annual_unit_cost * entitlement * 0.18,
                2
            ),
            "currency": "INR",
            "cost_period": "annual",
            "business_owner": f"owner_{index:02d}",
            "department": rng.choice(DEPARTMENTS),
            "source_system": "synthetic_license_inventory",
            "record_timestamp": END_DATE.isoformat()
        })

        costs.append({
            "software_feature": feature,
            "software_product": product,
            "publisher": publisher,
            "license_metric": metric,
            "unit_cost": annual_unit_cost,
            "currency": "INR",
            "cost_period": "annual",
            "effective_from": contract_start.isoformat(),
            "effective_to": contract_end.isoformat(),
            "cost_source": "synthetic_demonstration_assumption",
            "approval_status": "unverified_demo_assumption"
        })

        feature_info[feature] = {
            "license_id": license_id,
            "product": product,
            "publisher": publisher,
            "metric": metric,
            "entitlement": entitlement,
            "profile": profile,
            "daemon": DAEMONS[(index - 1) // 2]
        }

    return inventory, costs, feature_info


# =====================================================
# 5. LICENSE EVENT GENERATION
# =====================================================

def build_events(feature_info):

    events = []
    event_counter = 0

    for feature, info in feature_info.items():

        entitlement = info["entitlement"]
        profile = info["profile"]

        if profile == "low":
            requests_per_day = (3, 8)
        elif profile == "moderate":
            requests_per_day = (10, 18)
        else:
            requests_per_day = (18, 30)

        active_sessions = []

        for day_offset in range(DAYS):

            day_start = START_DATE + timedelta(
                days=day_offset
            )

            request_count = rng.randint(*requests_per_day)

            request_times = sorted([
                day_start.replace(
                    hour=rng.randint(7, 19),
                    minute=rng.randint(0, 59),
                    second=rng.randint(0, 59)
                )
                for _ in range(request_count)
            ])

            for request_time in request_times:

                # Close expired sessions and create IN events.

                remaining_sessions = []

                for end_time, qty, user, host, session_id in active_sessions:

                    if end_time <= request_time:

                        event_counter += 1

                        events.append({
                            "_sort_time": end_time,
                            "event_id": f"SIM-EVT-{event_counter:08d}",
                            "session_id": session_id,
                            "event_timestamp": end_time.isoformat(),
                            "event_type": "IN",
                            "license_id": info["license_id"],
                            "software_product": info["product"],
                            "software_feature": feature,
                            "username": user,
                            "hostname": host,
                            "license_quantity": qty,
                            "vendor_daemon": info["daemon"],
                            "server_name": f"license_server_{info['daemon']}",
                            "denial_reason": "",
                            "source_log_file": f"synthetic_{info['daemon']}.log"
                        })

                    else:
                        remaining_sessions.append(
                            (end_time, qty, user, host, session_id)
                        )

                active_sessions = remaining_sessions

                requested_qty = (
                    1 if rng.random() < 0.94 else 2
                )

                current_usage = sum(
                    session[1]
                    for session in active_sessions
                )

                user = rng.choice(USERS)
                host = rng.choice(HOSTS)

                common_fields = {
                    "license_id": info["license_id"],
                    "software_product": info["product"],
                    "software_feature": feature,
                    "username": user,
                    "hostname": host,
                    "license_quantity": requested_qty,
                    "vendor_daemon": info["daemon"],
                    "server_name": f"license_server_{info['daemon']}",
                    "source_log_file": f"synthetic_{info['daemon']}.log"
                }

                if current_usage + requested_qty <= entitlement:

                    duration = rng.randint(15, 360)

                    end_time = request_time + timedelta(
                        minutes=duration
                    )

                    # Create a unique session ID for this checkout.
                    session_id = f"SIM-SES-{event_counter + 1:08d}"

                    active_sessions.append((
                        end_time,
                        requested_qty,
                        user,
                        host,
                        session_id
                    ))

                    event_counter += 1

                    events.append({
                        "_sort_time": request_time,
                        "event_id": f"SIM-EVT-{event_counter:08d}",
                        "session_id": session_id,
                        "event_timestamp": request_time.isoformat(),
                        "event_type": "OUT",
                        **common_fields,
                        "denial_reason": ""
                    })

                else:

                    event_counter += 1

                    events.append({
                        "_sort_time": request_time,
                        "event_id": f"SIM-EVT-{event_counter:08d}",
                        "session_id": "",
                        "event_timestamp": request_time.isoformat(),
                        "event_type": "DENIED",
                        **common_fields,
                        "denial_reason": "No licenses available"
                    })

        # Close remaining sessions at the simulation end.

        for end_time, qty, user, host, session_id in active_sessions:

            end_time = min(end_time, END_DATE)

            event_counter += 1

            events.append({
                "_sort_time": end_time,
                "event_id": f"SIM-EVT-{event_counter:08d}",
                "session_id": session_id,
                "event_timestamp": end_time.isoformat(),
                "event_type": "IN",
                "license_id": info["license_id"],
                "software_product": info["product"],
                "software_feature": feature,
                "username": user,
                "hostname": host,
                "license_quantity": qty,
                "vendor_daemon": info["daemon"],
                "server_name": f"license_server_{info['daemon']}",
                "denial_reason": "",
                "source_log_file": f"synthetic_{info['daemon']}.log"
            })

    events.sort(key=lambda row: row["_sort_time"])

    for event in events:
        event.pop("_sort_time", None)

    return events


# =====================================================
# 6. MAIN
# =====================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    SUMMARY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    inventory, costs, feature_info = (
        build_inventory_and_costs()
    )

    events = build_events(feature_info)

    inventory_fields = [
        "license_id",
        "software_feature",
        "software_product",
        "publisher",
        "version",
        "license_metric",
        "entitled_quantity",
        "installed_quantity",
        "assigned_quantity",
        "contract_start_date",
        "contract_end_date",
        "renewal_date",
        "support_maintenance_cost",
        "currency",
        "cost_period",
        "business_owner",
        "department",
        "source_system",
        "record_timestamp"
    ]

    event_fields = [
        "event_id",
        "session_id",
        "event_timestamp",
        "event_type",
        "license_id",
        "software_product",
        "software_feature",
        "username",
        "hostname",
        "license_quantity",
        "vendor_daemon",
        "server_name",
        "denial_reason",
        "source_log_file"
    ]

    cost_fields = [
        "software_feature",
        "software_product",
        "publisher",
        "license_metric",
        "unit_cost",
        "currency",
        "cost_period",
        "effective_from",
        "effective_to",
        "cost_source",
        "approval_status"
    ]

    write_csv(
        INVENTORY_FILE,
        inventory_fields,
        inventory
    )

    write_csv(
        EVENTS_FILE,
        event_fields,
        events
    )

    write_csv(
        COST_FILE,
        cost_fields,
        costs
    )

    event_counts = {}

    for event in events:

        event_type = event["event_type"]

        event_counts[event_type] = (
            event_counts.get(event_type, 0) + 1
        )

    summary = {
        "domain": "Licensing",
        "data_origin": "simulated",
        "description": (
            "Synthetic demonstration records. They do not represent "
            "actual enterprise users, contracts, license server logs, "
            "prices or realized savings."
        ),
        "random_seed": SEED,
        "simulation_days": DAYS,
        "simulation_start": START_DATE.isoformat(),
        "simulation_end": END_DATE.isoformat(),
        "software_features": len(PRODUCTS),
        "inventory_records": len(inventory),
        "event_records": len(events),
        "event_type_counts": event_counts,
        "cost_reference_records": len(costs),
        "currency": "INR",
        "cost_assumption": (
            "Illustrative annual unit costs; not actual vendor quotes."
        )
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\nLICENSING DATA GENERATION COMPLETED")
    print("=" * 45)

    print(f"Inventory records: {len(inventory)}")
    print(f"Event records: {len(events)}")
    print(f"Cost reference records: {len(costs)}")
    print(f"Event types: {event_counts}")

    print("\nGenerated files:")
    print(INVENTORY_FILE)
    print(EVENTS_FILE)
    print(COST_FILE)
    print(SUMMARY_FILE)

    print("\nAll operational and cost records are simulated.")


if __name__ == "__main__":
    main()
