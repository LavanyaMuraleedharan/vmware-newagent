
from pathlib import Path
import pandas as pd

SUPPORTED_FORMATS = {
    ".csv",
    ".parquet",
    ".xlsx",
    ".xls",
    ".json"
}


def clean_dataframe(dataframe):
    """Clean column names and dataset values."""

    # Clean column names
    dataframe.columns = (
        dataframe.columns.astype(str)
        .str.strip()
        .str.rstrip(";")
        .str.strip()
    )

    # Remove trailing semicolons from string values
    for column in dataframe.select_dtypes(include=["object"]).columns:
        dataframe[column] = dataframe[column].map(
            lambda value: value.rstrip(";").strip()
            if isinstance(value, str)
            else value
        )

    # Convert numeric-looking columns to numeric types
    for column in dataframe.columns:
        converted = pd.to_numeric(
            dataframe[column],
            errors="coerce"
        )

        # Convert only if all non-null original values are numeric
        original_non_null = dataframe[column].notna()
        converted_non_null = converted.notna()

        if (original_non_null == converted_non_null).all():
            dataframe[column] = converted

    return dataframe


def load_file(file_path):
    """Load datasets according to their file formats."""

    file_path = Path(file_path)

    try:
        extension = file_path.suffix.lower()

        if extension == ".csv":
            # Detect the actual delimiter
            dataframe = pd.read_csv(
                file_path,
                sep=None,
                engine="python"
            )

        elif extension == ".parquet":
            dataframe = pd.read_parquet(file_path)

        elif extension in [".xlsx", ".xls"]:
            dataframe = pd.read_excel(file_path)

        elif extension == ".json":
            dataframe = pd.read_json(file_path)

        else:
            raise ValueError(
                f"Unsupported format: {extension}"
            )

        return clean_dataframe(dataframe)

    except Exception as error:
        print(f"Error loading {file_path.name}: {error}")
        return None


def discover_datasets(data_directory):
    """Discover datasets recursively."""

    data_directory = Path(data_directory)

    if not data_directory.exists():
        raise FileNotFoundError(
            f"Data directory not found: {data_directory}"
        )

    return sorted(
        file_path
        for file_path in data_directory.rglob("*")
        if file_path.is_file()
        and file_path.suffix.lower() in SUPPORTED_FORMATS
    )


def load_all_datasets(data_directory):
    """Load all discovered datasets."""

    datasets = {}

    for file_path in discover_datasets(data_directory):

        dataset_name = str(
            file_path.relative_to(data_directory)
        )

        dataframe = load_file(file_path)

        if dataframe is not None:
            datasets[dataset_name] = dataframe

    return datasets


def get_dataset_metadata(dataframe):
    """Extract dataset metadata."""

    return {
        "rows": len(dataframe),
        "columns": len(dataframe.columns),
        "column_names": list(dataframe.columns),
        "missing_values": int(
            dataframe.isnull().sum().sum()
        ),
        "data_types": dataframe.dtypes.astype(str).to_dict()
    }


def preview_dataset(dataframe, rows=5):
    """Preview dataset records."""

    return dataframe.head(rows)
