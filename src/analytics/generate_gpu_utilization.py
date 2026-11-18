
import pandas as pd
import random
from pathlib import Path
from datetime import datetime, timedelta

random.seed(42)

# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "compute_gpu"
    / "compute_gpu_server_metrics.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "infrastructure_logs"
    / "compute_gpu"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "gpu_utilization_metrics.csv"

# --------------------------------------------------
# GPU MEMORY REFERENCE
# GB PER GPU
# --------------------------------------------------

GPU_MEMORY_GB = {
    "A10": 24,
    "A30": 24,
    "H20": 96,
    "H800": 80,
    "A800": 80,

    # A100 variants can have different memory capacities.
    # XPU models also need their exact specifications.
    "A100": None,
    "XPU-A": None,
    "XPU-B": None,
    "XPU-C": None,
    "XPU-D": None,
    "XPU-E": None
}

# --------------------------------------------------
# LOAD EXISTING GPU INVENTORY
# --------------------------------------------------

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"GPU inventory not found: {INPUT_FILE}"
    )

inventory = pd.read_csv(INPUT_FILE)

required_columns = [
    "server_id",
    "gpu_specifications",
    "gpu_count_max_observed",
    "gpu_count_min_observed"
]

missing = [
    col for col in required_columns
    if col not in inventory.columns
]

if missing:
    raise ValueError(
        f"Missing inventory columns: {missing}"
    )

inventory = inventory.drop_duplicates(
    subset=["server_id"]
).copy()

# Use actual GPU model and observed GPU counts.
inventory["gpu_specifications"] = (
    inventory["gpu_specifications"]
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)

inventory["gpu_count_max_observed"] = pd.to_numeric(
    inventory["gpu_count_max_observed"],
    errors="coerce"
).fillna(0)

inventory["gpu_count_min_observed"] = pd.to_numeric(
    inventory["gpu_count_min_observed"],
    errors="coerce"
).fillna(0)

# --------------------------------------------------
# UTILIZATION PROFILES
# --------------------------------------------------

utilization_profiles = {
    "idle": (0, 10),
    "low": (10, 30),
    "moderate": (30, 65),
    "high": (65, 95)
}

records = []

start_date = datetime(2026, 8, 1)

# --------------------------------------------------
# GENERATE 90 DAYS OF GPU METRICS
# --------------------------------------------------

for _, server in inventory.iterrows():

    server_id = str(server["server_id"])

    gpu_model = server["gpu_specifications"]

    gpu_count_max = int(
        server["gpu_count_max_observed"]
    )

    gpu_count_min = int(
        server["gpu_count_min_observed"]
    )

    if gpu_count_max <= 0:
        continue

    # Keep GPU count consistent with inventory.
    gpu_count = gpu_count_max

    # Determine known memory per GPU.
    memory_per_gpu = GPU_MEMORY_GB.get(gpu_model)

    total_gpu_memory = (
        memory_per_gpu * gpu_count
        if memory_per_gpu is not None
        else None
    )

    # Assign one utilization profile per server.
    profile_name = random.choice(
        list(utilization_profiles.keys())
    )

    min_util, max_util = utilization_profiles[
        profile_name
    ]

    # Fixed GPU memory configuration per server.
    if total_gpu_memory is not None:
        memory_utilization = random.uniform(10, 90)

        memory_used = round(
            total_gpu_memory * memory_utilization / 100,
            2
        )
    else:
        memory_utilization = None
        memory_used = None

    for day in range(90):

        timestamp = start_date + timedelta(days=day)

        gpu_utilization = random.uniform(
            min_util,
            max_util
        )

        gpu_utilization = max(
            0,
            min(
                100,
                gpu_utilization + random.uniform(-2, 2)
            )
        )

        records.append({

            "timestamp": timestamp.isoformat(),

            "server_id": server_id,

            "gpu_id": "SERVER_GPU_AGGREGATE",

            "gpu_model": gpu_model,

            "gpu_count": gpu_count,

            "gpu_count_min_observed": gpu_count_min,

            "gpu_count_max_observed": gpu_count_max,

            "gpu_utilization_pct": round(
                gpu_utilization, 2
            ),

            "gpu_memory_used_gb": memory_used,

            "gpu_memory_total_gb": total_gpu_memory,

            "gpu_memory_utilization_pct": (
                round(memory_utilization, 2)
                if memory_utilization is not None
                else None
            )

        })

# --------------------------------------------------
# SAVE DATASET
# --------------------------------------------------

result = pd.DataFrame(records)

result.to_csv(
    OUTPUT_FILE,
    index=False
)

# --------------------------------------------------
# DISPLAY SUMMARY
# --------------------------------------------------

print("\nGPU utilization dataset generated successfully.")

print(f"Output file: {OUTPUT_FILE}")

print(f"Total records: {len(result)}")

print(
    "Unique servers:",
    result["server_id"].nunique()
)

print("\nGPU model distribution:")

print(
    inventory["gpu_specifications"].value_counts()
)

print("\nGPU utilization summary:")

print(
    result.groupby("gpu_model")["gpu_utilization_pct"]
    .mean()
    .round(2)
)

print("\nGPU memory information:")

print(
    result.groupby("gpu_model")["gpu_memory_total_gb"]
    .first()
)

print("\nSample records:")

print(
    result.head(10).to_string(index=False)
)
