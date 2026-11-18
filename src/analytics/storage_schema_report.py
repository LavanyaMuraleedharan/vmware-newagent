from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_PATH = PROJECT_ROOT / "data" / "dataset" / "dataset"

for folder in ["cache", "pools"]:
    folder_path = STORAGE_PATH / folder

    print(f"\n{'=' * 60}")
    print(f"FOLDER: {folder.upper()}")
    print("=" * 60)

    for file_path in folder_path.glob("*.csv"):
        df = pd.read_csv(file_path, nrows=5)

        print(f"\nFile: {file_path.name}")
        print(f"Columns: {list(df.columns)}")
        print(f"Sample:")
        print(df.head(2).to_string(index=False))