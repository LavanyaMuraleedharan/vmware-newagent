
from pathlib import Path
from src.ingestion.data_loader import discover_datasets
from src.ingestion.data_classifier import classify_datasets

DATA_DIR = Path("data")

files = discover_datasets(DATA_DIR)

# Include PDFs separately
pdf_files = list(DATA_DIR.rglob("*.pdf"))

all_files = files + pdf_files

classified = classify_datasets(all_files)

for category, file_paths in classified.items():
    print(f"\n{category.upper()}: {len(file_paths)} files")

    for file_path in file_paths[:5]:
        print("  ", file_path)

    if len(file_paths) > 5:
        print("   ...")
