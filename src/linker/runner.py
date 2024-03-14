import os
import socket
from pathlib import Path
from typing import List

from loguru import logger
from snakemake.cli import main as snake_main

from linker.configuration import Config
from linker.pipeline import Pipeline
from linker.utilities.data_utils import copy_configuration_files_to_results_directory
from linker.utilities.slurm_utils import get_cli_args


def main(
    config: Config,
    results_dir: Path,
) -> None:
    """Set up and run the pipeline"""

    pipeline = Pipeline(config)

    # Now that all validation is done, copy the configuration files to the results directory
    copy_configuration_files_to_results_directory(config, results_dir)
    snakefile = pipeline.build_snakefile(results_dir)
    environment_args = get_environment_args(config, results_dir)
    # We need to set a dummy environment variable to avoid logging a wall of text.
    # TODO [MIC-4920]: Remove when https://github.com/snakemake/snakemake-interface-executor-plugins/issues/55 merges
    os.environ["foo"] = "bar"
    argv = [
        "--snakefile",
        str(snakefile),
        "--jobs=2",
        "--latency-wait=60",
        "--cores",
        "1",
        ## See above
        "--envvars",
        "foo",
        "--quiet",
        "progress"
    ]
    argv.extend(environment_args)
    logger.info(f"Running Snakemake")
    snake_main(argv)


def get_environment_args(config, results_dir) -> List[str]:
    # Set up computing environment
    if config.computing_environment == "local":
        return []

        # TODO [MIC-4822]: launch a local spark cluster instead of relying on implementation
    elif config.computing_environment == "slurm":
        # Set up a single drmaa.session that is persistent for the duration of the pipeline
        # TODO [MIC-4468]: Check for slurm in a more meaningful way
        hostname = socket.gethostname()
        if "slurm" not in hostname:
            raise RuntimeError(
                f"Specified a 'slurm' computing-environment but on host {hostname}"
            )
        os.environ["DRMAA_LIBRARY_PATH"] = "/opt/slurm-drmaa/lib/libdrmaa.so"
        diagnostics = results_dir / "diagnostics/"
        job_name = "snakemake-linker"
        resources = config.slurm_resources
        slurm_args = [
            "--executor",
            "slurm",
            "--default-resources",
            f"slurm_account={resources['account']}",
            f"slurm_partition='{resources['partition']}'",
            f"mem={resources['memory']}",
            f"runtime={resources['time_limit']}",
            f"nodes={resources['cpus']}",
                    ]
        return slurm_args
    else:
        raise NotImplementedError(
            "only computing_environment 'local' and 'slurm' are supported; "
            f"provided {config.computing_environment}"
        )
