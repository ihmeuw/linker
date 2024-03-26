import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from linker.runner import main
from linker.utilities.slurm_utils import is_on_slurm
from tests.conftest import SPECIFICATIONS_DIR


@pytest.mark.slow
@pytest.mark.skipif(
    not is_on_slurm(),
    reason="Must be on slurm to run this test.",
)
def test_slurm(caplog):
    """Test that the pipeline runs on SLURM with appropriate resources."""
    with tempfile.TemporaryDirectory(dir="tests/integration/") as results_dir:
        results_dir = Path(results_dir).resolve()
        with pytest.raises(SystemExit) as exit:
            main(
                SPECIFICATIONS_DIR / "pipeline.yaml",
                SPECIFICATIONS_DIR / "input_data.yaml",
                SPECIFICATIONS_DIR / "environment_slurm.yaml",
                results_dir,
                debug=True,
            )
        assert exit.value.code == 0
        output = caplog.text
        job_ids = re.findall(r"Job \d+ has been submitted with SLURM jobid (\d+)", output)
        assert len(job_ids) == 2
        cmd = [
            "sacct",
            "--jobs=" + ",".join(job_ids),
            "--format=JobID,Account,Partition,ReqMem,ReqNodes,TimelimitRaw",
            "--noheader",
            "--parsable2",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout
        # Filter out jobs that are not the main job and grab full line
        main_job_pattern = r"^(\d+)\|"
        main_job_lines = [
            line for line in output.split("\n") if re.match(main_job_pattern, line)
        ]
        for line in main_job_lines:
            fields = line.split("|")
            account, partition, mem, nodes, time = fields[1:6]
            assert account == "proj_simscience"
            assert partition == "all.q"
            assert mem == "1G" or mem == "1024M"  # Just in case
            assert nodes == "1"
            assert time == "1"
