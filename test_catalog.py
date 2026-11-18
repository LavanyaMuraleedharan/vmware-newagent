
import json
from collections import Counter
from pathlib import Path

catalog_path = Path("data/processed/dataset_catalog.json")

with open(catalog_path, "r", encoding="utf-8") as file:
    catalog = json.load(file)

print("Total catalog entries:", len(catalog))

print("\nCategory distribution:")
print(Counter(item["category"] for item in catalog))

print("\nLoading status:")
print(Counter(item["status"] for item in catalog))

print("\nSample dataset metadata:")
for item in catalog[:3]:
    print(json.dumps(item, indent=2))
