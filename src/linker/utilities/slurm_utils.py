import os
import shutil
import types
from datetime import datetime
from pathlib import Path
from typing import Dict, List, TextIO

from loguru import logger


def get_slurm_drmaa() -> types.ModuleType("drmaa"):
    """Returns object() to bypass RuntimeError when not on a DRMAA-compliant system"""
    try:
        import drmaa
    except (RuntimeError, OSError):
        # TODO [MIC-4469]: make more generic for external users
        os.environ["DRMAA_LIBRARY_PATH"] = "/opt/slurm-drmaa/lib/libdrmaa.so"
        import drmaa

    return drmaa


def launch_slurm_job(
    session: types.ModuleType("drmaa.Session"),
    resources: Dict[str, str],
    container_engine: str,
    input_data: List[Path],
    results_dir: Path,
    step_name: str,
    step_dir: Path,
) -> None:
    jt = session.createJobTemplate()
    jt.jobName = f"{step_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    jt.joinFiles = False  # keeps stdout separate from stderr
    jt.outputPath = f":{str(results_dir / '%A.o%a')}"
    jt.errorPath = f":{str(results_dir / '%A.e%a')}"
    jt.remoteCommand = shutil.which("linker")
    jt_args = [
        "run-slurm-job",
        container_engine,
        str(results_dir),
        step_name,
        str(step_dir),
        "-vvv",
    ]
    for filepath in input_data:
        jt_args.extend(("--input-data", str(filepath)))
    jt.args = jt_args
    jt.jobEnvironment = {
        "LC_ALL": "en_US.UTF-8",
        "LANG": "en_US.UTF-8",
    }
    jt.nativeSpecification = get_cli_args(
        job_name=jt.jobName,
        account=resources["account"],
        partition=resources["partition"],
        peak_memory=resources["memory"],
        max_runtime=resources["time_limit"],
        num_threads=resources["cpus"],
    )
    job_id = session.runJob(jt)
    logger.info(
        f"Launching slurm job for step '{step_name}'\n"
        f"Job submitted with jobid '{job_id}'\n"
        f"Output log: {str(results_dir / f'{job_id}.o*')}\n"
        f"Error log: {str(results_dir / f'{job_id}.e*')}"
    )
    job_status = session.wait(job_id, session.TIMEOUT_WAIT_FOREVER)
    # TODO: clean up if job failed?
    logger.info(f"Job {job_id} finished with status '{job_status}'")
    session.deleteJobTemplate(jt)
    session.exit()


def get_slurm_drmaa() -> types.ModuleType("drmaa"):
    """Returns object() to bypass RuntimeError when not on a DRMAA-compliant system"""
    try:
        import drmaa
    except (RuntimeError, OSError):
        # TODO [MIC-4469]: make more generic for external users
        os.environ["DRMAA_LIBRARY_PATH"] = "/opt/slurm-drmaa/lib/libdrmaa.so"
        import drmaa

    return drmaa


def get_cli_args(job_name, account, partition, peak_memory, max_runtime, num_threads):
    return (
        f"-J {job_name} "
        f"-A {account} "
        f"-p {partition} "
        f"--mem={peak_memory*1024} "
        f"-t {max_runtime}:00:00 "
        f"-c {num_threads}"
    )


def submit_spark_cluster_job(
    session: types.ModuleType("drmaa.Session"),
    launcher: TextIO,
    account: str,
    partition: str,
    memory_per_node: int,
    max_runtime: int,
    num_workers: int,
    cpus_per_task: int,
) -> None:
    """Submits a job to launch a Spark cluster.

    Args:
        session: DRMAA session.
        launcher: Launcher script.
        account: Account to charge.
        partition: Partition to run on.
        memory_per_node: Memory per node in GB.
        max_runtime: Maximum runtime in hours.
        num_workers: Number of workers.
        cpus_per_task: Number of CPUs per task.

    Returns:
        None
    """
    jt = session.createJobTemplate()
    jt.jobName = f"spark_cluster_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    jt.workingDirectory = os.getcwd()
    jt.joinFiles = False  # keeps stdout separate from stderr
    jt.outputPath = f":{str(jt.workingDirectory / '%A.o%a')}"
    jt.errorPath = f":{str(jt.workingDirectory / '%A.e%a')}"
    jt.remoteCommand = shutil.which("sh")
    jt.args = [launcher.name]
    jt.jobEnvironment = {
        "LC_ALL": "en_US.UTF-8",
        "LANG": "en_US.UTF-8",
    }
    jt.nativeSpecification = (
        f"--account={account} "
        f"--partition={partition} "
        f"--mem-per-cpu={memory_per_node * 1024} "
        f"--time={max_runtime}:00:00 "
        f"--nodes={num_workers + 1} "
        f"--cpus-per-task={cpus_per_task} "
        "--ntasks-per-node=1"
    )
    job_id = session.runJob(jt)
    logger.info(
        f"Submitting slurm job for launching the Spark cluster: '{jt.jobName}'\n"
        f"Job submitted with jobid '{job_id}' to execute script '{launcher.name}'\n"
        f"Output log: {jt.outputPath}\n"
        f"Error log: {jt.errorPath}"
    )
    session.deleteJobTemplate(jt)
    session.exit()
