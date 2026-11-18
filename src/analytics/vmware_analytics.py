
from pathlib import Path
import json
import pandas as pd

# ==================================================
# 1. PATH CONFIGURATION
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "gwa_t_12_fastStorage"
    / "fastStorage"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "vmware"
)

METRICS_FILE = OUTPUT_DIR / "vmware_file_metrics.csv"
ERROR_FILE = OUTPUT_DIR / "vmware_ingestion_errors.csv"
SUMMARY_FILE = OUTPUT_DIR / "vmware_summary.json"

CHUNK_SIZE = 100_000


# ==================================================
# 2. DATASET COLUMNS
# ==================================================

TIMESTAMP = "Timestamp [ms]"

REQUIRED_COLUMNS = [
    TIMESTAMP,
    "CPU cores",
    "CPU capacity provisioned [MHZ]",
    "CPU usage [MHZ]",
    "CPU usage [%]",
    "Memory capacity provisioned [KB]",
    "Memory usage [KB]",
    "Disk read throughput [KB/s]",
    "Disk write throughput [KB/s]",
    "Network received throughput [KB/s]",
    "Network transmitted throughput [KB/s]",
]

METRICS = [
    "CPU usage [%]",
    "CPU usage [MHZ]",
    "CPU capacity provisioned [MHZ]",
    "Memory capacity provisioned [KB]",
    "Memory usage [KB]",
    "Disk read throughput [KB/s]",
    "Disk write throughput [KB/s]",
    "Network received throughput [KB/s]",
    "Network transmitted throughput [KB/s]",
]


# ==================================================
# 3. RUNNING STATISTICS
# ==================================================

def create_stat():
    return {
        "sum": 0.0,
        "count": 0,
        "max": None,
    }


def add_stats(stats, name, values):

    values = pd.to_numeric(
        values,
        errors="coerce"
    ).dropna()

    if values.empty:
        return

    stats[name]["sum"] += float(values.sum())

    stats[name]["count"] += int(values.count())

    current_max = float(values.max())

    if stats[name]["max"] is None:
        stats[name]["max"] = current_max
    else:
        stats[name]["max"] = max(
            stats[name]["max"],
            current_max
        )


def average(stats, name):

    count = stats[name]["count"]

    if count == 0:
        return None

    return stats[name]["sum"] / count


# ==================================================
# 4. PROCESS ONE VMWARE CSV
# ==================================================

def process_file(file_path):

    relative_path = (
        file_path.relative_to(INPUT_DIR).with_suffix("")
    )

    # This is a source identifier, NOT a confirmed VM ID.
    source_file_id = relative_path.as_posix()

    # Initialize statistics for all metrics.
    stats = {
        metric: create_stat()
        for metric in METRICS
    }

    # Validated utilization statistics.
    stats["validated_cpu_utilization_pct"] = create_stat()

    stats["validated_memory_utilization_pct"] = create_stat()

    # Data quality counters.
    quality_counts = {
        "zero_cpu_capacity": 0,
        "cpu_usage_above_capacity": 0,
        "cpu_percentage_above_100": 0,
        "cpu_negative_values": 0,
        "zero_memory_capacity": 0,
        "memory_usage_above_capacity": 0,
        "memory_negative_values": 0,
        "missing_metric_values": 0,
        "invalid_cpu_utilization_samples": 0,
        "invalid_memory_utilization_samples": 0,
    }

    total_rows = 0

    valid_timestamp_count = 0

    timestamp_min = None
    timestamp_max = None
    timestamp_unit = None

    cpu_cores_values = set()

    # --------------------------------------------------
    # Read CSV in chunks
    # --------------------------------------------------

    for chunk in pd.read_csv(
        file_path,
        sep=";",
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):

        chunk.columns = chunk.columns.str.strip()

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in chunk.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        total_rows += len(chunk)

        # Convert all expected columns to numeric.
        for column in REQUIRED_COLUMNS:

            chunk[column] = pd.to_numeric(
                chunk[column],
                errors="coerce"
            )

        # --------------------------------------------------
        # TIMESTAMP VALIDATION
        # --------------------------------------------------

        timestamps = chunk[TIMESTAMP].dropna()

        if not timestamps.empty:

            median_timestamp = timestamps.abs().median()

            detected_unit = (
                "ms"
                if median_timestamp >= 1e11
                else "s"
            )

            if timestamp_unit is None:

                timestamp_unit = detected_unit

            elif timestamp_unit != detected_unit:

                raise ValueError(
                    "Inconsistent timestamp units in source file"
                )

            valid_timestamp_count += len(timestamps)

            chunk_min = int(timestamps.min())
            chunk_max = int(timestamps.max())

            timestamp_min = (
                chunk_min
                if timestamp_min is None
                else min(timestamp_min, chunk_min)
            )

            timestamp_max = (
                chunk_max
                if timestamp_max is None
                else max(timestamp_max, chunk_max)
            )

        # --------------------------------------------------
        # EXTRACT RESOURCE MEASUREMENTS
        # --------------------------------------------------

        cpu_capacity = chunk[
            "CPU capacity provisioned [MHZ]"
        ]

        cpu_usage = chunk[
            "CPU usage [MHZ]"
        ]

        cpu_pct = chunk[
            "CPU usage [%]"
        ]

        memory_capacity = chunk[
            "Memory capacity provisioned [KB]"
        ]

        memory_usage = chunk[
            "Memory usage [KB]"
        ]

        # --------------------------------------------------
        # DATA QUALITY COUNTS
        # --------------------------------------------------

        quality_counts["missing_metric_values"] += int(
            chunk[METRICS].isna().sum().sum()
        )

        quality_counts["zero_cpu_capacity"] += int(
            (cpu_capacity == 0).sum()
        )

        quality_counts["cpu_usage_above_capacity"] += int(
            (
                (cpu_usage > cpu_capacity)
                & (cpu_capacity > 0)
            ).sum()
        )

        quality_counts["cpu_percentage_above_100"] += int(
            (cpu_pct > 100).sum()
        )

        quality_counts["cpu_negative_values"] += int(
            (
                (cpu_capacity < 0)
                | (cpu_usage < 0)
                | (cpu_pct < 0)
            ).sum()
        )

        quality_counts["zero_memory_capacity"] += int(
            (memory_capacity == 0).sum()
        )

        quality_counts["memory_usage_above_capacity"] += int(
            (
                (memory_usage > memory_capacity)
                & (memory_capacity > 0)
            ).sum()
        )

        quality_counts["memory_negative_values"] += int(
            (
                (memory_capacity < 0)
                | (memory_usage < 0)
            ).sum()
        )

        # --------------------------------------------------
        # RAW METRICS
        # Preserve raw values for traceability.
        # --------------------------------------------------

        for metric in METRICS:

            add_stats(
                stats,
                metric,
                chunk[metric]
            )

        # --------------------------------------------------
        # VALIDATED CPU UTILIZATION
        # --------------------------------------------------

        valid_cpu = (
            cpu_capacity.gt(0)
            & cpu_usage.ge(0)
            & cpu_pct.ge(0)
            & cpu_pct.le(100)
            & cpu_usage.le(cpu_capacity)
        )

        quality_counts[
            "invalid_cpu_utilization_samples"
        ] += int((~valid_cpu).sum())

        add_stats(
            stats,
            "validated_cpu_utilization_pct",
            cpu_pct[valid_cpu]
        )

        # --------------------------------------------------
        # VALIDATED MEMORY UTILIZATION
        # --------------------------------------------------

        valid_memory = (
            memory_capacity.gt(0)
            & memory_usage.ge(0)
            & memory_usage.le(memory_capacity)
        )

        quality_counts[
            "invalid_memory_utilization_samples"
        ] += int((~valid_memory).sum())

        memory_pct = (
            memory_usage[valid_memory]
            / memory_capacity[valid_memory]
        ) * 100

        add_stats(
            stats,
            "validated_memory_utilization_pct",
            memory_pct
        )

        # --------------------------------------------------
        # CPU CORE COUNTS
        # --------------------------------------------------

        cores = chunk["CPU cores"].dropna()

        if not cores.empty:

            cpu_cores_values.update(
                cores.unique().tolist()
            )

    # ==================================================
    # 5. BUILD FILE-LEVEL RESULT
    # ==================================================

    if total_rows == 0:

        raise ValueError(
            "CSV contains no data rows"
        )

    first_timestamp = None
    last_timestamp = None

    if timestamp_min is not None:

        first_timestamp = pd.to_datetime(
            timestamp_min,
            unit=timestamp_unit,
            utc=True,
        ).isoformat()

        last_timestamp = pd.to_datetime(
            timestamp_max,
            unit=timestamp_unit,
            utc=True,
        ).isoformat()

    result = {

        "source_file_id": source_file_id,

        "source_file_name": file_path.name,

        "total_samples": total_rows,

        "valid_timestamp_samples": valid_timestamp_count,

        "timestamp_unit_detected": timestamp_unit,

        "first_observation_utc": first_timestamp,

        "last_observation_utc": last_timestamp,

        "cpu_cores_observed": (
            ",".join(
                str(x)
                for x in sorted(cpu_cores_values)
            )
            if cpu_cores_values
            else None
        ),

    }

    # --------------------------------------------------
    # RAW AVERAGE AND PEAK METRICS
    # --------------------------------------------------

    output_names = {

        "CPU usage [%]": "raw_avg_cpu_usage_pct",

        "CPU usage [MHZ]": "avg_cpu_usage_mhz",

        "CPU capacity provisioned [MHZ]": "avg_cpu_capacity_mhz",

        "Memory capacity provisioned [KB]": "avg_memory_capacity_kb",

        "Memory usage [KB]": "avg_memory_usage_kb",

        "Disk read throughput [KB/s]": "avg_disk_read_kbps",

        "Disk write throughput [KB/s]": "avg_disk_write_kbps",

        "Network received throughput [KB/s]": "avg_network_received_kbps",

        "Network transmitted throughput [KB/s]": "avg_network_transmitted_kbps",

    }

    for metric, output_name in output_names.items():

        result[output_name] = average(
            stats,
            metric
        )

        peak_name = (
            output_name.replace("avg_", "raw_peak_")
        )

        result[peak_name] = stats[metric]["max"]

    # --------------------------------------------------
    # VALIDATED UTILIZATION METRICS
    # --------------------------------------------------

    result["avg_cpu_usage_pct"] = average(
        stats,
        "validated_cpu_utilization_pct"
    )

    result["peak_cpu_usage_pct"] = (
        stats["validated_cpu_utilization_pct"]["max"]
    )

    result["avg_memory_utilization_pct"] = average(
        stats,
        "validated_memory_utilization_pct"
    )

    result["peak_memory_utilization_pct"] = (
        stats["validated_memory_utilization_pct"]["max"]
    )

    # --------------------------------------------------
    # VALID SAMPLE COUNTS
    # --------------------------------------------------

    result["valid_cpu_utilization_samples"] = (
        stats["validated_cpu_utilization_pct"]["count"]
    )

    result["valid_memory_utilization_samples"] = (
        stats["validated_memory_utilization_pct"]["count"]
    )

    result["invalid_cpu_utilization_samples"] = (
        quality_counts["invalid_cpu_utilization_samples"]
    )

    result["invalid_memory_utilization_samples"] = (
        quality_counts["invalid_memory_utilization_samples"]
    )

    # --------------------------------------------------
    # MEMORY UNIT CONVERSION
    # --------------------------------------------------

    if result["avg_memory_capacity_kb"] is not None:

        result["avg_memory_capacity_gb"] = (
            result["avg_memory_capacity_kb"]
            / (1024 ** 2)
        )

    else:

        result["avg_memory_capacity_gb"] = None

    if result["avg_memory_usage_kb"] is not None:

        result["avg_memory_usage_gb"] = (
            result["avg_memory_usage_kb"]
            / (1024 ** 2)
        )

    else:

        result["avg_memory_usage_gb"] = None

    # --------------------------------------------------
    # QUALITY COUNTERS
    # --------------------------------------------------

    for key, value in quality_counts.items():

        result[f"quality_{key}"] = value

    # --------------------------------------------------
    # PROVENANCE
    # --------------------------------------------------

    result["data_origin"] = "public_benchmark_dataset"

    result["entity_type"] = "source_file_timeseries"

    result["source_identifier_note"] = (
        "Relative source file path; not a confirmed VM ID"
    )

    result["financial_cost_status"] = (
        "Not available in source performance data"
    )

    return result


# ==================================================
# 6. MAIN EXECUTION
# ==================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        INPUT_DIR.rglob("*.csv")
    )

    print("\n========== VMWARE INGESTION ==========")

    print(
        f"VMware CSV files discovered: {len(files):,}"
    )

    results = []
    errors = []

    for index, file_path in enumerate(
        files,
        start=1
    ):

        try:

            record = process_file(file_path)

            results.append(record)

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

        if index % 50 == 0 or index == len(files):

            print(
                f"Processed {index}/{len(files)} files"
            )

    # --------------------------------------------------
    # SAVE METRICS
    # --------------------------------------------------

    metrics_df = pd.DataFrame(results)

    metrics_df.to_csv(
        METRICS_FILE,
        index=False
    )

    # --------------------------------------------------
    # SAVE ERRORS
    # --------------------------------------------------

    errors_df = pd.DataFrame(
        errors,
        columns=[
            "source_file",
            "error"
        ]
    )

    errors_df.to_csv(
        ERROR_FILE,
        index=False
    )

    # --------------------------------------------------
    # AGGREGATE DATA QUALITY
    # --------------------------------------------------

    quality_columns = [
        column
        for column in metrics_df.columns
        if column.startswith("quality_")
    ]

    quality_summary = {}

    for column in quality_columns:

        quality_summary[column] = int(
            metrics_df[column].sum()
        )

    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------

    summary = {

        "domain": "VMware",

        "files_discovered": len(files),

        "files_processed": len(results),

        "files_failed": len(errors),

        "total_samples_processed": int(
            metrics_df["total_samples"].sum()
        ) if not metrics_df.empty else 0,

        "total_valid_cpu_samples": int(
            metrics_df[
                "valid_cpu_utilization_samples"
            ].sum()
        ) if not metrics_df.empty else 0,

        "total_valid_memory_samples": int(
            metrics_df[
                "valid_memory_utilization_samples"
            ].sum()
        ) if not metrics_df.empty else 0,

        "data_quality_summary": quality_summary,

        "output_metrics": str(METRICS_FILE),

        "output_errors": str(ERROR_FILE),

        "timestamp_note": (
            "Timestamp units detected from numeric magnitude. "
            "Source header says ms, but sample values around "
            "1.37 billion indicate Unix seconds."
        ),

        "source_identifier_note": (
            "source_file_id is a relative file path, "
            "not a confirmed VM ID."
        ),

        "financial_cost_note": (
            "No actual financial cost is present in these "
            "VMware performance files."
        ),

        "validation_note": (
            "Validated CPU and memory utilization excludes "
            "zero-capacity, negative and above-capacity samples. "
            "Raw measurements are retained separately."
        ),

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

    # ==================================================
    # 7. FINAL REPORT
    # ==================================================

    print("\n========== VMWARE INGESTION COMPLETE ==========")

    print(
        f"Discovered files : {len(files):,}"
    )

    print(
        f"Processed files  : {len(results):,}"
    )

    print(
        f"Failed files     : {len(errors):,}"
    )

    print(
        "Total samples    : "
        f"{summary['total_samples_processed']:,}"
    )

    print(
        "Valid CPU samples: "
        f"{summary['total_valid_cpu_samples']:,}"
    )

    print(
        "Valid memory samples: "
        f"{summary['total_valid_memory_samples']:,}"
    )

    print("\nDATA QUALITY SUMMARY")

    for key, value in quality_summary.items():

        print(
            f"{key}: {value:,}"
        )

    print("\nOUTPUT FILES")

    print(f"Metrics : {METRICS_FILE}")

    print(f"Errors  : {ERROR_FILE}")

    print(f"Summary : {SUMMARY_FILE}")


if __name__ == "__main__":

    main()
