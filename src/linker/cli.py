import os
import subprocess
from pathlib import Path

import click
import yaml
from loguru import logger

from linker.utilities.cli_utils import (
    configure_logging_to_terminal,
    handle_exceptions,
    prepare_results_directory,
)
from linker.utilities.docker_utils import (
    confirm_docker_daemon_running,
    load_docker_image,
    remove_docker_image,
    run_docker_container,
)
from linker.utilities.singularity_utils import (
    build_singularity_container,
    clean_up_singularity,
    run_singularity_container,
)


@click.group()
def linker():
    """A command line utility for running a linker pipeline.

    You may initiate a new run with the ``run`` sub-command.
    """
    pass


@linker.command()
@click.argument(
    "pipeline_specification",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--computing-environment",
    default="local",
    show_default=True,
    type=click.Choice(["local"]),
    help=("The computing environment on which to launch the step."),
)
@click.option(
    "-v", "verbose", count=True, help="Configure logging verbosity.", hidden=True
)
@click.option(
    "--pdb",
    "with_debugger",
    is_flag=True,
    help="Drop into python debugger if an error occurs.",
    hidden=True,
)
def run(
    pipeline_specification: Path,
    computing_environment: str,
    verbose: int,
    with_debugger: bool,
) -> None:
    """Run a pipeline from the command line.

    The pipeline itself is defined by the given PIPELINE_SPECIFICATION yaml file.

    Results will be written to the working directory.
    """
    configure_logging_to_terminal(verbose)
    results_dir = prepare_results_directory(pipeline_specification)
    main = handle_exceptions(
        func=_run, exceptions_logger=logger, with_debugger=with_debugger
    )
    main(computing_environment, pipeline_specification, results_dir)
    logger.info("*** FINISHED ***")


def _run(computing_environment: str, pipeline_specification: Path, results_dir: Path):
    with open(pipeline_specification, "r") as f:
        pipeline = yaml.full_load(f)
    # TODO: make pipeline implementation generic
    implementation = pipeline["implementation"]
    # TODO: get a handle on exception handling and logging
    if implementation == "pvs_like_python":
        # TODO: stop hard-coding filepaths
        step_dir = (
            Path(os.path.realpath(__file__)).parent.parent.parent
            / "steps"
            / "pvs_like_case_study_sample_data"
        )
    else:
        raise NotImplementedError(f"No support for impementation '{implementation}'")
    if computing_environment == "local":
        try:  # docker
            logger.info("Trying to run container with docker")
            confirm_docker_daemon_running()
            image_id = load_docker_image(step_dir / "image.tar.gz")
            run_docker_container(image_id, step_dir / "input_data", results_dir)
            # TODO: clean up image even if error raised
            remove_docker_image(image_id)
        except Exception as e_docker:
            logger.warning(f"Docker failed with error: '{e_docker}'")
            try:  # singularity
                logger.info("Trying to run container with singularity")
                build_singularity_container(results_dir, step_dir)
                run_singularity_container(results_dir, step_dir)
                # remove singulaity image from cache?
                clean_up_singularity(results_dir, step_dir)
            except Exception as e_singularity:
                raise RuntimeError(
                    f"Both docker and singularity failed:\n"
                    f"    Docker error: {e_docker}\n"
                    f"    Singularity error: {str(e_singularity)}"
                )

    else:
        raise NotImplementedError(
            "only --computing-invironment 'local' is supported; "
            f"provided '{computing_environment}'"
        )