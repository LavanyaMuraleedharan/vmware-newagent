
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LICENSING_DIR = (
    ROOT / "data" / "infrastructure_logs" / "licensing"
)

events_file = LICENSING_DIR / "license_events_template.csv"
inventory_file = LICENSING_DIR / "license_inventory_template.csv"
cost_file = LICENSING_DIR / "license_cost_reference_template.csv"

events = pd.read_csv(events_file)
inventory = pd.read_csv(inventory_file)
costs = pd.read_csv(cost_file)

events["event_timestamp"] = pd.to_datetime(
    events["event_timestamp"],
    errors="coerce"
)

checks = {
    "Total events": len(events),
    "Inventory records": len(inventory),
    "Cost reference records": len(costs),
    "Missing event IDs": int(events["event_id"].isna().sum()),
    "Duplicate event IDs": int(events["event_id"].duplicated().sum()),
    "Missing timestamps": int(events["event_timestamp"].isna().sum()),
    "Invalid event types": int(
        (~events["event_type"].isin(["OUT", "IN", "DENIED"])).sum()
    ),
    "Non-positive license quantities": int(
        (events["license_quantity"] <= 0).sum()
    )
}

# Match OUT and IN events using feature, user, host and quantity.
# This is a first-pass validation for this synthetic dataset.
session_keys = [
    "software_feature",
    "username",
    "hostname",
    "license_quantity"
]

checkout_counts = (
    events[events["event_type"] == "OUT"]
    .groupby(session_keys)
    .size()
)

checkin_counts = (
    events[events["event_type"] == "IN"]
    .groupby(session_keys)
    .size()
)

checks["Unmatched OUT/IN groups"] = int(
    (checkout_counts.subtract(checkin_counts, fill_value=0) != 0).sum()
)

print("\nLICENSING DATA VALIDATION")
print("=" * 45)

for name, value in checks.items():
    print(f"{name}: {value}")

print("\nEvent distribution:")
print(events["event_type"].value_counts())

print("\nInventory and cost products:")
print("Inventory products:", inventory["software_product"].nunique())
print("Cost products:", costs["software_product"].nunique())

print("\nValidation inspection completed.")
