import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from pprint import pprint

import pytest

from easylink.utilities.data_utils import load_yaml
from easylink.utilities.general_utils import is_on_slurm
from tests.conftest import RESULTS_DIR, SPECIFICATIONS_DIR

RESULT_CHECKSUM = "9f9cc43beef9e688d809ff4f1cc9d569c51a276fb6dd277fa7d6ca5d57f81eb0"


@pytest.mark.slow
@pytest.mark.skipif(
    not is_on_slurm(),
    reason="Must be on slurm to run this test.",
)
@pytest.mark.parametrize(
    "pipeline_specification, input_data, computing_environment",
    [
        # slurm
        (
            "e2e/pipeline.yaml",
            "common/input_data.yaml",
            "e2e/environment_slurm.yaml",
        ),
        # local
        (
            "e2e/pipeline.yaml",
            "common/input_data.yaml",
            "common/environment_local.yaml",
        ),
    ],
)
def test_easylink_run(pipeline_specification, input_data, computing_environment, capsys):
    """e2e tests for 'easylink run' command

    NOTE: We use various print statements in this test because they show up in the
    Jenkins logs.
    """
    # Create a temporary directory to store results. We cannot use pytest's tmp_path fixture
    # because other nodes do not have access to it. Also, do not use a context manager
    # (i.e. tempfile.TemporaryDirectory) because it's too difficult to debug when the test
    # fails b/c the dir gets deleted.
    results_dir = tempfile.mkdtemp(dir=RESULTS_DIR)
    # give the tmpdir the same permissions as the parent directory so that
    # cluster jobs can write to it
    os.chmod(results_dir, os.stat(RESULTS_DIR).st_mode)
    results_dir = Path(results_dir)
    with capsys.disabled():  # disabled so we can monitor job submissions
        print(
            "\n\n*** RUNNING TEST ***\n"
            f"[{pipeline_specification}, {input_data}, {computing_environment}]\n"
        )

        cmd = (
            "easylink run "
            f"-p {SPECIFICATIONS_DIR / pipeline_specification} "
            f"-i {SPECIFICATIONS_DIR / input_data} "
            f"-e {SPECIFICATIONS_DIR / computing_environment} "
            f"-o {str(results_dir)} "
            "--no-timestamp"
        )
        subprocess.run(
            cmd,
            shell=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=True,
        )

        assert (results_dir / "result.parquet").exists()
        # Check that the results file checksum matches the expected value
        with open(results_dir / "result.parquet", "rb") as f:
            actual_checksum = hashlib.sha256(f.read()).hexdigest()
        assert actual_checksum == RESULT_CHECKSUM

        assert (results_dir / Path(pipeline_specification).name).exists()
        assert (results_dir / Path(input_data).name).exists()
        assert (results_dir / Path(computing_environment).name).exists()

        # Check that implementation configuration worked
        diagnostics_dir = results_dir / "diagnostics"
        assert load_yaml(diagnostics_dir / "1_step_1" / "diagnostics.yaml")["increment"] == 1
        assert (
            load_yaml(diagnostics_dir / "2_step_2" / "diagnostics.yaml")["increment"] == 100
        )
        assert (
            load_yaml(diagnostics_dir / "3_step_3" / "diagnostics.yaml")["increment"] == 702
        )
        assert (
            load_yaml(diagnostics_dir / "4_step_4" / "diagnostics.yaml")["increment"] == 912
        )
        # If it made it through all this, print some diagnostics and delete the results_dir
        final_diagnostics = load_yaml(
            sorted([d for d in diagnostics_dir.iterdir() if d.is_dir()])[-1]
            / "diagnostics.yaml"
        )
        print("\nFinal diagnostics:\n")
        pprint(final_diagnostics)
        # sleep briefly before removing tmpdir b/c sometimes one lingers
        os.system(f"sleep 1 && rm -rf {results_dir}")
        print(
            "\n\n*** END OF TEST ***\n"
            f"[{pipeline_specification}, {input_data}, {computing_environment}]\n"
        )
