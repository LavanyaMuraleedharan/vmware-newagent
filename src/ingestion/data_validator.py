
import numpy as np
import pandas as pd


def validate_dataframe(dataframe, dataset_name="Unknown"):
    """Validate a dataset and generate a quality report."""

    report = {
        "dataset_name": dataset_name,
        "rows": len(dataframe),
        "columns": len(dataframe.columns),
        "missing_values": int(dataframe.isnull().sum().sum()),
        "duplicate_rows": int(dataframe.duplicated().sum()),
        "column_quality": {},
        "warnings": [],
        "errors": []
    }

    # 1. Missing values
    missing_columns = dataframe.columns[
        dataframe.isnull().any()
    ].tolist()

    if missing_columns:
        report["warnings"].append(
            f"Missing values found in: {missing_columns}"
        )

    # 2. Column-level validation
    for column in dataframe.columns:

        column_data = dataframe[column]

        column_report = {
            "missing_values": int(column_data.isnull().sum()),
            "data_type": str(column_data.dtype)
        }

        # 3. Numeric validation
        if pd.api.types.is_numeric_dtype(column_data):

            numeric_data = column_data.dropna()

            # Check infinite values
            infinite_count = int(
                np.isinf(numeric_data).sum()
            )

            column_report["infinite_values"] = infinite_count

            if infinite_count > 0:
                report["errors"].append(
                    f"{column}: infinite values detected"
                )

            # Check negative resource metrics
            column_name = str(column).lower()

            resource_keywords = [
                "cpu", "memory", "mem", "disk",
                "storage", "iops", "throughput",
                "bandwidth", "capacity", "utilization",
                "usage", "network"
            ]

            excluded_keywords = [
                "timestamp", "time", "id", "latency",
                "duration", "response", "query"
            ]

            is_resource_metric = (
                any(keyword in column_name
                    for keyword in resource_keywords)
                and not any(keyword in column_name
                            for keyword in excluded_keywords)
            )

            negative_count = 0

            if is_resource_metric:
                negative_count = int(
                    (numeric_data < 0).sum()
                )

                if negative_count > 0:
                    report["warnings"].append(
                        f"{column}: {negative_count} negative values"
                    )

            column_report["negative_values"] = negative_count

        report["column_quality"][column] = column_report

    # 4. Duplicate records
    if report["duplicate_rows"] > 0:
        report["warnings"].append(
            f"{report['duplicate_rows']} duplicate rows detected"
        )

    # 5. Final status
    report["status"] = (
        "FAIL" if report["errors"]
        else "WARNING" if report["warnings"]
        else "PASS"
    )

    return report


def validate_all_datasets(datasets):
    """Validate multiple loaded datasets."""

    validation_results = {}

    for dataset_name, dataframe in datasets.items():

        validation_results[dataset_name] = (
            validate_dataframe(
                dataframe,
                dataset_name
            )
        )

    return validation_results


def print_validation_report(report):
    """Display validation results."""

    print("\n" + "=" * 60)
    print("DATA VALIDATION REPORT")
    print("=" * 60)

    print(f"Dataset: {report['dataset_name']}")
    print(f"Rows: {report['rows']}")
    print(f"Columns: {report['columns']}")
    print(f"Missing values: {report['missing_values']}")
    print(f"Duplicate rows: {report['duplicate_rows']}")
    print(f"Status: {report['status']}")

    if report["warnings"]:
        print("\nWarnings:")
        for warning in report["warnings"]:
            print(f" - {warning}")

    if report["errors"]:
        print("\nErrors:")
        for error in report["errors"]:
            print(f" - {error}")

    print("=" * 60)
