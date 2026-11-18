
from src.ingestion.data_loader import (
    discover_datasets,
    load_all_datasets,
    get_dataset_metadata,
    preview_dataset
)

DATA_DIR = "data"

# Discover datasets
files = discover_datasets(DATA_DIR)

print("\n========== DISCOVERED DATASETS ==========")

for file in files:
    print(file)

# Load datasets
print("\n========== LOADING DATASETS ==========")

datasets = load_all_datasets(DATA_DIR)

# Display metadata and sample records
for name, dataframe in datasets.items():

    print(f"\n========== DATASET: {name} ==========")

    print("\nMetadata:")
    print(get_dataset_metadata(dataframe))

    print("\nSample Records:")
    print(preview_dataset(dataframe, rows=3))

    print("\nData Types:")
    print(dataframe.dtypes)
