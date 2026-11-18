
from pathlib import Path
import json

from data_loader import (
    discover_datasets,
    load_file,
    get_dataset_metadata
)

from data_classifier import classify_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"
OUTPUT_DIRECTORY = DATA_DIRECTORY / "processed"
CATALOG_FILE = OUTPUT_DIRECTORY / "dataset_catalog.json"


def run_data_pipeline():

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Discover source datasets, excluding generated output folders
    dataset_files = discover_datasets(DATA_DIRECTORY)

    dataset_files = [
        file_path
        for file_path in dataset_files
        if OUTPUT_DIRECTORY not in file_path.resolve().parents
    ]

    catalog = []

    print(f"\nDiscovered source datasets: {len(dataset_files)}")

    for file_path in dataset_files:

        category = classify_dataset(file_path)

        print(f"\nProcessing: {file_path.name}")
        print(f"Category: {category}")

        dataframe = load_file(file_path)

        if dataframe is None:
            catalog.append({
                "file_name": file_path.name,
                "file_path": str(file_path.relative_to(PROJECT_ROOT)),
                "category": category,
                "status": "load_failed"
            })
            continue

        metadata = get_dataset_metadata(dataframe)

        catalog.append({
            "file_name": file_path.name,
            "file_path": str(file_path.relative_to(PROJECT_ROOT)),
            "category": category,
            "status": "loaded",
            "metadata": metadata
        })

        print(f"Rows: {metadata['rows']}")
        print(f"Columns: {metadata['columns']}")

        del dataframe

    with open(CATALOG_FILE, "w", encoding="utf-8") as file:
        json.dump(catalog, file, indent=4)

    print("\n--------------------------------")
    print("DATA PIPELINE COMPLETED")
    print("--------------------------------")
    print(f"Source datasets discovered: {len(dataset_files)}")
    print(f"Catalog saved: {CATALOG_FILE}")


if __name__ == "__main__":
    run_data_pipeline()
