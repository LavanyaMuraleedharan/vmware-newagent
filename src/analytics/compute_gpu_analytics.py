
from pathlib import Path
import json
import pandas as pd

# ==================================================
# 1. PATHS
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "asi_opensource_server_hourly"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "compute_gpu"
)

FILE_METRICS = OUTPUT_DIR / "compute_gpu_file_metrics.csv"
SERVER_METRICS = OUTPUT_DIR / "compute_gpu_server_metrics.csv"
ERROR_FILE = OUTPUT_DIR / "compute_gpu_ingestion_errors.csv"
SUMMARY_FILE = OUTPUT_DIR / "compute_gpu_summary.json"

# ==================================================
# 2. REQUIRED COLUMNS
# ==================================================

REQUIRED_COLUMNS = [
    "server_id",
    "cluster_id",
    "asw_id",
    "gpu_spec_public",
    "gpu_count",
    "cpu_capacity_cores",
]


# ==================================================
# 3. PROCESS ONE PARQUET FILE
# ==================================================

def process_file(file_path):

    df = pd.read_parquet(file_path)

    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    df = df[REQUIRED_COLUMNS].copy()

    # Preserve source information.
    relative_path = file_path.relative_to(INPUT_DIR)

    df["source_file_id"] = relative_path.as_posix()

    # Extract partition information from directory names.
    partition_parts = relative_path.parts

    day = next(
        (x.replace("day=", "") for x in partition_parts
         if x.startswith("day=")),
        None
    )

    hour = next(
        (x.replace("hour=", "") for x in partition_parts
         if x.startswith("hour=")),
        None
    )

    df["partition_day"] = day
    df["partition_hour"] = hour

    # Convert numeric fields.
    for column in ["gpu_count", "cpu_capacity_cores"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Validate identifiers and capacities.
    invalid_server = (
        df["server_id"].isna()
        | df["server_id"].astype(str).str.strip().eq("")
    )

    invalid_gpu = (
        df["gpu_count"].notna()
        & (df["gpu_count"] < 0)
    )

    invalid_cpu = (
        df["cpu_capacity_cores"].notna()
        & (df["cpu_capacity_cores"] < 0)
    )

    df["record_quality_status"] = "valid"

    df.loc[
        invalid_server,
        "record_quality_status"
    ] = "missing_server_id"

    df.loc[
        invalid_gpu | invalid_cpu,
        "record_quality_status"
    ] = "invalid_capacity"

    valid_df = df[
        df["record_quality_status"] == "valid"
    ].copy()

    # File-level metrics.
    file_metrics = {
        "source_file_id": relative_path.as_posix(),
        "total_records": int(len(df)),
        "valid_records": int(len(valid_df)),
        "invalid_server_records": int(invalid_server.sum()),
        "invalid_gpu_capacity_records": int(invalid_gpu.sum()),
        "invalid_cpu_capacity_records": int(invalid_cpu.sum()),
        "missing_gpu_count": int(df["gpu_count"].isna().sum()),
        "missing_cpu_capacity": int(
            df["cpu_capacity_cores"].isna().sum()
        ),
        "unique_servers": int(
            valid_df["server_id"].nunique()
        ),
        "partition_day": day,
        "partition_hour": hour,
        "data_origin": "public_benchmark_dataset",
    }

    return valid_df, file_metrics


# ==================================================
# 4. SERVER-LEVEL ANALYTICS
# ==================================================

def build_server_metrics(all_data):

    if all_data.empty:
        return pd.DataFrame()

    # Group repeated observations by server.
    grouped = all_data.groupby(
        "server_id",
        dropna=True
    )

    records = []

    for server_id, group in grouped:

        gpu_counts = group["gpu_count"].dropna()

        cpu_capacities = (
            group["cpu_capacity_cores"].dropna()
        )

        gpu_specs = (
            group["gpu_spec_public"]
            .dropna()
            .astype(str)
            .unique()
        )

        clusters = (
            group["cluster_id"]
            .dropna()
            .astype(str)
            .unique()
        )

        days = sorted(
            group["partition_day"].dropna().unique()
        )

        records.append({

            "server_id": str(server_id),

            "observed_records": int(len(group)),

            "source_file_count": int(
                group["source_file_id"].nunique()
            ),

            "cluster_ids": ",".join(clusters),

            "gpu_specifications": ",".join(gpu_specs),

            "gpu_count_max_observed": (
                float(gpu_counts.max())
                if not gpu_counts.empty else None
            ),

            "gpu_count_min_observed": (
                float(gpu_counts.min())
                if not gpu_counts.empty else None
            ),

            "cpu_capacity_cores_max_observed": (
                float(cpu_capacities.max())
                if not cpu_capacities.empty else None
            ),

            "cpu_capacity_cores_min_observed": (
                float(cpu_capacities.min())
                if not cpu_capacities.empty else None
            ),

            "first_observed_day": (
                days[0] if days else None
            ),

            "last_observed_day": (
                days[-1] if days else None
            ),

            "data_origin": "public_benchmark_dataset",

        })

    return pd.DataFrame(records)


# ==================================================
# 5. MAIN EXECUTION
# ==================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        INPUT_DIR.rglob("*.parquet")
    )

    print("\n========== COMPUTE/GPU INGESTION ==========")

    print(f"Parquet files discovered: {len(files)}")

    all_valid_data = []

    file_results = []
    errors = []

    for index, file_path in enumerate(
        files,
        start=1
    ):

        try:

            valid_df, file_metrics = process_file(
                file_path
            )

            all_valid_data.append(valid_df)

            file_results.append(file_metrics)

        except Exception as error:

            errors.append({

                "source_file": str(
                    file_path.relative_to(INPUT_DIR)
                ),

                "error": str(error),

            })

            print(
                f"ERROR: {file_path.name} - {error}"
            )

        if index % 10 == 0 or index == len(files):

            print(
                f"Processed {index}/{len(files)} files"
            )

    # --------------------------------------------------
    # COMBINE VALID RECORDS
    # --------------------------------------------------

    if all_valid_data:

        combined_df = pd.concat(
            all_valid_data,
            ignore_index=True
        )

    else:

        combined_df = pd.DataFrame(
            columns=REQUIRED_COLUMNS + [
                "source_file_id",
                "partition_day",
                "partition_hour",
                "record_quality_status",
            ]
        )

    # --------------------------------------------------
    # SERVER-LEVEL METRICS
    # --------------------------------------------------

    server_df = build_server_metrics(
        combined_df
    )

    # --------------------------------------------------
    # SAVE OUTPUTS
    # --------------------------------------------------

    file_df = pd.DataFrame(file_results)

    file_df.to_csv(
        FILE_METRICS,
        index=False
    )

    server_df.to_csv(
        SERVER_METRICS,
        index=False
    )

    pd.DataFrame(
        errors,
        columns=["source_file", "error"]
    ).to_csv(
        ERROR_FILE,
        index=False
    )

    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------

    total_records = sum(
        x["total_records"] for x in file_results
    )

    valid_records = sum(
        x["valid_records"] for x in file_results
    )

    summary = {

        "domain": "Compute/GPU",

        "files_discovered": len(files),

        "files_processed": len(file_results),

        "files_failed": len(errors),

        "total_records": total_records,

        "valid_records": valid_records,

        "invalid_records": (
            total_records - valid_records
        ),

        "unique_servers": int(
            combined_df["server_id"].nunique()
        ) if not combined_df.empty else 0,

        "unique_clusters": int(
            combined_df["cluster_id"].nunique()
        ) if not combined_df.empty else 0,

        "total_gpu_count_across_records": (
            float(combined_df["gpu_count"].sum())
            if not combined_df.empty else 0
        ),

        "maximum_cpu_capacity_cores_observed": (
            float(
                combined_df["cpu_capacity_cores"].max()
            )
            if not combined_df.empty else None
        ),

        "data_origin": "reference_dataset",

        "limitations": [
            "Dataset contains capacity and inventory fields.",
            "Actual CPU and GPU utilization is not established.",
            "Actual infrastructure costs are not provided.",
            "Repeated server observations are aggregated.",
            "Maximum observed capacity is not necessarily current capacity.",
        ],

        "outputs": {
            "file_metrics": str(FILE_METRICS),
            "server_metrics": str(SERVER_METRICS),
            "errors": str(ERROR_FILE),
        },

    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=4
        )

    # --------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------

    print("\n========== COMPUTE/GPU COMPLETE ==========")

    print(f"Discovered files: {len(files):,}")

    print(f"Processed files: {len(file_results):,}")

    print(f"Failed files: {len(errors):,}")

    print(f"Total records: {total_records:,}")

    print(f"Valid records: {valid_records:,}")

    print(
        f"Invalid records: {total_records - valid_records:,}"
    )

    print(
        f"Unique servers: {summary['unique_servers']:,}"
    )

    print(
        f"Unique clusters: {summary['unique_clusters']:,}"
    )

    print("\nOUTPUT FILES")

    print(FILE_METRICS)
    print(SERVER_METRICS)
    print(ERROR_FILE)
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()
