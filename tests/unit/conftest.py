import csv
from pathlib import Path
from typing import Dict, List

import pytest
import yaml

from linker.configuration import Config

ENV_CONFIG_DICT = {
    "minimum": {
        "computing_environment": "local",
        "container_engine": "undefined",
    },
    "with_spark_and_slurm": {
        "computing_environment": "slurm",
        "container_engine": "singularity",
        "slurm": {
            "account": "some-account",
            "partition": "some-partition",
        },
        "implementation_resources": {
            "memory": 42,
            "cpus": 42,
            "time_limit": 42,
        },
        "spark": {
            "workers": {
                "num_working": 42,
                "cpus_per_node": 42,
                "mem_per_node": 42,
                "time_limit": 42,
            },
        },
    },
}

PIPELINE_CONFIG_DICT = {
    "good": {
        "steps": {
            "step_1": {
                "implementation": {
                    "name": "step_1_python_pandas",
                },
            },
            "step_2": {
                "implementation": {
                    "name": "step_2_python_pandas",
                },
            },
        },
    },
    "out_of_order": {
        "steps": {
            "step_2": {
                "implementation": {
                    "name": "step_2_python_pandas",
                },
            },
            "step_1": {
                "implementation": {
                    "name": "step_1_python_pandas",
                },
            },
        },
    },
    "missing_step": {
        "steps": {
            "step_2": {
                "implementation": {
                    "name": "step_2_python_pandas",
                },
            },
        },
    },
    "bad_step": {
        "steps": {
            "foo": {  # Not a supported step
                "implementation": {
                    "name": "step_1_python_pandas",
                },
            },
        },
    },
    "missing_implementations": {
        "steps": {
            "step_1": {
                "foo": "bar",  # Missing implementation key
            },
        },
    },
    "missing_implementation_name": {
        "steps": {
            "step_1": {
                "implementation": {
                    "foo": "bar",  # Missing name key
                },
            },
        },
    },
    "bad_implementation": {
        "steps": {
            "step_1": {
                "implementation": {
                    "name": "foo",  # Not a supported implementation
                },
            },
        },
    },
}

INPUT_DATA_FORMAT_DICT = {
    "correct_cols": [["foo", "bar", "counter"], [1, 2, 3]],
    "wrong_cols": [["wrong", "column", "names"], [1, 2, 3]],
}


def _write_csv(filepath: str, rows: List) -> None:
    with open(filepath, "w") as file:
        writer = csv.writer(file)
        writer.writerows(rows)


@pytest.fixture(scope="session")
def test_dir(tmpdir_factory) -> str:
    """Set up a persistent test directory with some of the specification files"""
    tmp_path = tmpdir_factory.getbasetemp()

    # good pipeline.yaml
    with open(f"{str(tmp_path)}/pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["good"], file, sort_keys=False)
    # bad pipeline.yamls
    with open(f"{str(tmp_path)}/out_of_order_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["out_of_order"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/missing_step_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["missing_step"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/bad_step_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["bad_step"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/missing_outer_key_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["good"]["steps"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/missing_implementation_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["missing_implementations"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/missing_implementation_name_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["missing_implementation_name"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/bad_implementation_pipeline.yaml", "w") as file:
        yaml.dump(PIPELINE_CONFIG_DICT["bad_implementation"], file, sort_keys=False)

    # dummy environment.yaml
    with open(f"{str(tmp_path)}/environment.yaml", "w") as file:
        yaml.dump(ENV_CONFIG_DICT["minimum"], file, sort_keys=False)
    with open(f"{str(tmp_path)}/spark_environment.yaml", "w") as file:
        yaml.dump(ENV_CONFIG_DICT["with_spark_and_slurm"], file, sort_keys=False)

    # input files
    input_dir1 = tmp_path.mkdir("input_data1")
    input_dir2 = tmp_path.mkdir("input_data2")
    for input_dir in [input_dir1, input_dir2]:
        for base_file in ["file1", "file2"]:
            # good input files
            _write_csv(input_dir / f"{base_file}.csv", INPUT_DATA_FORMAT_DICT["correct_cols"])
            # bad input files
            _write_csv(
                input_dir / f"broken_{base_file}.csv",
                INPUT_DATA_FORMAT_DICT["wrong_cols"],
            )
            # files with wrong extensions
            _write_csv(
                input_dir / f"{base_file}.oops",
                INPUT_DATA_FORMAT_DICT["correct_cols"],
            )

    # good input_data.yaml
    with open(f"{tmp_path}/input_data.yaml", "w") as file:
        yaml.dump(
            {
                "foo": str(input_dir1 / "file1.csv"),
                "bar": str(input_dir2 / "file2.csv"),
            },
            file,
            sort_keys=False,
        )
    # input data is just a list (does not have keys)
    with open(f"{tmp_path}/input_data_list.yaml", "w") as file:
        yaml.dump(
            [
                str(input_dir1 / "file1.csv"),
                str(input_dir2 / "file2.csv"),
            ],
            file,
            sort_keys=False,
        )
    # missing input_data.yaml
    with open(f"{tmp_path}/missing_input_data.yaml", "w") as file:
        yaml.dump(
            {
                "foo": str(input_dir1 / "missing_file1.csv"),
                "bar": str(input_dir2 / "missing_file2.csv"),
            },
            file,
            sort_keys=False,
        )
    # input directs to files without sensible data
    with open(f"{tmp_path}/bad_columns_input_data.yaml", "w") as file:
        yaml.dump(
            {
                "foo": str(input_dir1 / "broken_file1.csv"),
                "bar": str(input_dir2 / "broken_file2.csv"),
            },
            file,
            sort_keys=False,
        )
    # incorrect file type
    with open(f"{tmp_path}/bad_type_input_data.yaml", "w") as file:
        yaml.dump(
            {
                "file1": str(input_dir1 / "file1.oops"),
                "file2": str(input_dir2 / "file2.oops"),
            },
            file,
            sort_keys=False,
        )

    # bad implementation
    bad_step_implementation_dir = tmp_path.join("steps/foo/implementations/bar/").ensure(
        dir=True
    )
    with open(f"{bad_step_implementation_dir}/metadata.yaml", "w") as file:
        yaml.dump(
            {
                "step": "foo",  # not a supported step
                "image": {
                    "path": "some/path/to/container/directory",
                    "filename": "bar",
                },
            },
            file,
            sort_keys=False,
        )

    return str(tmp_path)


@pytest.fixture()
def default_config_params(test_dir) -> Dict[str, Path]:
    return {
        "pipeline_specification": Path(f"{test_dir}/pipeline.yaml"),
        "input_data": Path(f"{test_dir}/input_data.yaml"),
        "computing_environment": Path(f"{test_dir}/environment.yaml"),
    }


@pytest.fixture()
def default_config(default_config_params) -> Config:
    """A good/known Config object"""
    return Config(**default_config_params)
