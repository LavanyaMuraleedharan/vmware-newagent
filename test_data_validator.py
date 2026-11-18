
from src.ingestion.data_loader import load_all_datasets

from src.ingestion.data_validator import (
    validate_all_datasets,
    print_validation_report
)

DATA_DIR = "data"

# Load datasets
datasets = load_all_datasets(DATA_DIR)

# Validate datasets
validation_results = validate_all_datasets(datasets)

# Display reports
for dataset_name, report in validation_results.items():

    print_validation_report(report)
