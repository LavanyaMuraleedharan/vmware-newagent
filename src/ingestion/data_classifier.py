
from pathlib import Path


def classify_dataset(file_path):
    """
    Classify datasets based on their folder and file names.
    """

    path = Path(file_path).as_posix().lower()
    filename = Path(file_path).name.lower()

    # VMware
    if "gwa" in path or "faststorage" in path:
        return "vmware"

    # Database
    if "raw_query_timings" in path or "system_profiling_log" in path:
        return "database"

    # Compute / GPU
    if "asi_opensource_server_hourly" in path:
        return "compute_gpu"

    # Backup
    backup_files = {
        "backup_asset_inventory.csv",
        "backup_cost_records.csv",
        "backup_job_logs.csv",
        "backup_policy_logs.csv",
        "backup_repository_logs.csv",
    }

    if filename in backup_files or "infrastructure_logs/backup/" in path:
        return "backup"

    # Storage
    if "cache" in path or "pools" in path:
        return "storage"

    # Licensing
    if path.endswith(".pdf") or "licens" in path:
        return "licensing"

    return "unknown"


def classify_datasets(file_paths):
    """
    Classify multiple dataset files.
    """

    classified_datasets = {}

    for file_path in file_paths:
        category = classify_dataset(file_path)

        classified_datasets.setdefault(category, []).append(
            str(file_path)
        )

    return classified_datasets
