
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = (
    PROJECT_ROOT / "data" / "gwa_t_12_fastStorage" / "fastStorage"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "vmware"
OUTPUT_FILE = OUTPUT_DIR / "vmware_data_quality_audit.csv"

CHUNK_SIZE = 100_000

METRICS = [
    "Memory capacity provisioned [KB]",
    "Memory usage [KB]",
    "CPU capacity provisioned [MHZ]",
    "CPU usage [MHZ]",
    "CPU usage [%]",
]

def audit_file(path):
    counts = {
        "source_file_id": path.relative_to(INPUT_DIR).with_suffix("").as_posix(),
        "total_samples": 0,
        "zero_memory_capacity": 0,
        "memory_usage_above_capacity": 0,
        "zero_cpu_capacity": 0,
        "cpu_usage_mhz_above_capacity": 0,
        "cpu_percentage_above_100": 0,
        "negative_values": 0,
        "missing_metric_values": 0,
    }

    for chunk in pd.read_csv(
        path, sep=";", chunksize=CHUNK_SIZE, low_memory=False
    ):
        chunk.columns = chunk.columns.str.strip()

        missing = [c for c in METRICS if c not in chunk.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        for column in METRICS:
            chunk[column] = pd.to_numeric(
                chunk[column], errors="coerce"
            )

        mem_cap = chunk["Memory capacity provisioned [KB]"]
        mem_use = chunk["Memory usage [KB]"]
        cpu_cap = chunk["CPU capacity provisioned [MHZ]"]
        cpu_use = chunk["CPU usage [MHZ]"]
        cpu_pct = chunk["CPU usage [%]"]

        counts["total_samples"] += len(chunk)

        counts["zero_memory_capacity"] += int(
            (mem_cap == 0).sum()
        )

        counts["memory_usage_above_capacity"] += int(
            ((mem_use > mem_cap) & (mem_cap > 0)).sum()
        )

        counts["zero_cpu_capacity"] += int(
            (cpu_cap == 0).sum()
        )

        counts["cpu_usage_mhz_above_capacity"] += int(
            ((cpu_use > cpu_cap) & (cpu_cap > 0)).sum()
        )

        counts["cpu_percentage_above_100"] += int(
            (cpu_pct > 100).sum()
        )

        counts["negative_values"] += int(
            (chunk[METRICS] < 0).sum().sum()
        )

        counts["missing_metric_values"] += int(
            chunk[METRICS].isna().sum().sum()
        )

    return counts


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(INPUT_DIR.rglob("*.csv"))
    results = []

    print(f"Auditing {len(files)} VMware files...")

    for index, path in enumerate(files, start=1):
        try:
            results.append(audit_file(path))
        except Exception as error:
            print(f"ERROR: {path}: {error}")

        if index % 50 == 0 or index == len(files):
            print(f"Audited {index}/{len(files)}")

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False)

    columns = [
        "total_samples",
        "zero_memory_capacity",
        "memory_usage_above_capacity",
        "zero_cpu_capacity",
        "cpu_usage_mhz_above_capacity",
        "cpu_percentage_above_100",
        "negative_values",
        "missing_metric_values",
    ]

    print("\n========== DATA QUALITY AUDIT ==========")
    print("Files audited:", len(df))

    for column in columns:
        print(f"{column}: {int(df[column].sum()):,}")

    print("\nFiles with memory anomalies:")
    print(
        int(
            (
                (df["zero_memory_capacity"] > 0)
                | (df["memory_usage_above_capacity"] > 0)
            ).sum()
        )
    )

    print("\nAudit file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
