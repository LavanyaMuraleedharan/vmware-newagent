
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/asi_opensource_server_hourly")

files = sorted(DATA_DIR.rglob("*.parquet"))

# Inspect the first Parquet file
file_path = files[0]

df = pd.read_parquet(file_path)

print("\nFILE:", file_path)
print("\nSHAPE:", df.shape)

print("\nCOLUMN NAMES:")
print(df.columns.tolist())

print("\nDATA TYPES:")
print(df.dtypes)

print("\nFIRST 10 ROWS:")
print(df.head(10).to_string())

print("\nMISSING VALUES:")
print(df.isnull().sum())

print("\nNON-NULL VALUES:")
print(df.notnull().sum())
