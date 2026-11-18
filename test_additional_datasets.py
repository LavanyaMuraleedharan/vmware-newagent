
from pathlib import Path
from src.ingestion.data_loader import load_file
from src.ingestion.data_validator import validate_dataframe

DATASETS = {
    "Cache and Pools": Path("data/dataset/dataset"),
    "ASI Server Hourly": Path("data/asi_opensource_server_hourly")
}

for dataset_name, directory in DATASETS.items():

    print(f"\n{'=' * 70}")
    print(f"VALIDATING: {dataset_name}")
    print("=" * 70)

    total_files = 0
    passed = 0
    warnings = 0
    failed = 0

    for file_path in sorted(directory.rglob("*")):

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in [".csv", ".parquet"]:
            continue

        total_files += 1

        dataframe = load_file(file_path)

        if dataframe is None:
            failed += 1
            print(f"LOAD FAILED: {file_path.name}")
            continue

        report = validate_dataframe(
            dataframe,
            dataset_name=str(file_path.relative_to(directory))
        )

        if report["status"] == "PASS":
            passed += 1
        elif report["status"] == "WARNING":
            warnings += 1
        else:
            failed += 1

        print(
            f"{file_path.name} | "
            f"Rows: {report['rows']} | "
            f"Columns: {report['columns']} | "
            f"Missing: {report['missing_values']} | "
            f"Duplicates: {report['duplicate_rows']} | "
            f"Status: {report['status']}"
        )

    print("\nSUMMARY")
    print(f"Total files: {total_files}")
    print(f"Passed: {passed}")
    print(f"Warnings: {warnings}")
    print(f"Failed: {failed}")
