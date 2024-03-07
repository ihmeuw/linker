import csv
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from linker.configuration import Config
import yaml


def create_results_directory(output_dir: Optional[str], timestamp: bool) -> Path:
    results_dir = Path("results" if output_dir is None else output_dir).resolve()
    if timestamp:
        launch_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        results_dir = results_dir / launch_time
    _ = os.umask(0o002)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "intermediate").mkdir(exist_ok=True)
    (results_dir / "diagnostics").mkdir(exist_ok=True)

    return results_dir


def copy_configuration_files_to_results_directory(
    config: "Config", results_dir: Path
) -> None:
    shutil.copy(config.pipeline_specification_path, results_dir)
    shutil.copy(config.input_data_specification_path, results_dir)
    if config.computing_environment_specification_path:
        shutil.copy(config.computing_environment_specification_path, results_dir)


def load_yaml(filepath: Path) -> Dict:
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
    return data


def write_csv(filepath: str, rows: List) -> None:
    with open(filepath, "w") as file:
        writer = csv.writer(file)
        writer.writerows(rows)
