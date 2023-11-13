from pathlib import Path

import pytest

from linker.configuration import Config
from tests.unit.conftest import ENV_CONFIG_DICT, PIPELINE_CONFIG_DICT

# TODO [MIC-4491]: beef these up


@pytest.mark.parametrize(
    "computing_environment",
    [
        "foo",
        "bad/path/to/environment.yaml",
        Path("another/bad/path"),
    ],
)
def test_bad_computing_environment_fails(test_dir, computing_environment):
    with pytest.raises(FileNotFoundError):
        Config(f"{test_dir}/pipeline.yaml", "foo", computing_environment)


def test_default_computing_environment(test_dir):
    config = Config(f"{test_dir}/pipeline.yaml", f"{test_dir}/input_data.yaml", None)
    assert config.computing_environment == "local"


def test_get_specs(test_dir, config):
    assert config.pipeline == PIPELINE_CONFIG_DICT["good"]
    assert config.environment == ENV_CONFIG_DICT
    assert config.input_data == [
        Path(x) for x in [f"{test_dir}/input_data{n}/file{n}" for n in [1, 2]]
    ]
