import tempfile
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, TextIO, Tuple

from loguru import logger

from linker.utilities.paths import CONTAINER_DIR
from linker.utilities.slurm_utils import submit_spark_cluster_job


def build_spark_cluster(
    drmaa: "drmaa",
    session: "drmaa.Session",
    resources: Dict[str, Any],
    step_id: str,
    results_dir: Path,
    diagnostics_dir: Path,
    input_data: List[Path],
) -> Tuple[str, str]:
    """Builds a Spark cluster.

    Args:
        drmaa: DRMAA module.
        session: DRMAA session.
        resources: Slurm and spark cluster resource requests.
        step_id: Step ID for naming jobs.
        results_dir: Results directory.
        diagnostics_dir: Diagnostics directory.
        input_data: Input data.

    Returns:
        spark_master_url: Spark master URL.
    """

    # call build_launch_script
    launcher = build_cluster_launch_script(
        results_dir=results_dir,
        diagnostics_dir=diagnostics_dir,
        input_data=input_data,
    )

    # submit job, get logfile for master node
    logfile, job_id = submit_spark_cluster_job(
        drmaa=drmaa,
        session=session,
        launcher=launcher,
        diagnostics_dir=diagnostics_dir,
        step_id=step_id,
        account=resources["slurm"]["account"],
        partition=resources["slurm"]["partition"],
        memory_per_node=resources["spark"]["workers"]["mem_per_node"],
        max_runtime=resources["spark"]["workers"]["time_limit"],
        num_workers=resources["spark"]["workers"]["num_workers"],
        cpus_per_node=resources["spark"]["workers"]["cpus_per_node"],
    )

    spark_master_url = find_spark_master_url(logfile)
    webui_url = spark_master_url.replace("spark://", "http://").replace(":28508", ":28509")
    logger.info(f"Spark master URL: {spark_master_url})\n" f"Spark web UI URL: {webui_url}")
    return spark_master_url, job_id


def build_cluster_launch_script(
    results_dir: Path, diagnostics_dir: Path, input_data: List[Path]
) -> TextIO:
    """Generates a shell file that, on execution, spins up a Spark cluster.

    Returns:
        launcher: Launcher script.
    """
    launcher = tempfile.NamedTemporaryFile(
        mode="w",
        dir=diagnostics_dir,
        prefix="spark_cluster_launcher_",
        suffix=".sh",
        delete=False,
    )

    # need to bind required files/dirs to worker nodes
    worker_bindings = (
        f"--bind {results_dir}:/results " f"--bind {diagnostics_dir}:/diagnostics "
    )
    for filepath in input_data:
        worker_bindings += (
            f"--bind {str(filepath)}:/input_data/main_input_{str(filepath.name)} "
        )
    # TODO: MIC-4744: Add support for varying SPARK_MASTER_PORT and SPARK_MASTER_WEBUI_PORT
    launcher.write(
        f"""
#!/bin/bash
#start_spark_slurm.sh automatically generated by linker

CONDA_PATH=/opt/conda/condabin/conda # must be accessible within container
CONDA_ENV=spark_cluster
SINGULARITY_IMG={CONTAINER_DIR}/spark_cluster.sif

SPARK_ROOT=/opt/spark # within the container
SPARK_MASTER_PORT=28508
SPARK_MASTER_WEBUI_PORT=28509
SPARK_WORKER_WEBUI_PORT=28510

if [ "$SLURM_ARRAY_TASK_ID" -eq 1 ]; then
    SPARK_MASTER_HOST=$(hostname -f)

    mkdir -p "/tmp/spark_cluster_$USER"

    singularity exec \
        -B /mnt:/mnt,"/tmp/spark_cluster_$USER":/tmp \
        $SINGULARITY_IMG \
        $CONDA_PATH run --no-capture-output -n $CONDA_ENV \
        $SPARK_ROOT/bin/spark-class org.apache.spark.deploy.master.Master \
        --host $SPARK_MASTER_HOST \
        --port $SPARK_MASTER_PORT \
        --webui-port $SPARK_MASTER_WEBUI_PORT
else
    MASTER_HOST=$(squeue --job ${{SLURM_ARRAY_JOB_ID}}_1 -o "%N" | tail -n1 | xargs -I {{}} host {{}} | awk '{{print $1}}')
    MASTER_URL=spark://$MASTER_HOST:$SPARK_MASTER_PORT

    mkdir -p "/tmp/spark_cluster_$USER"
    mkdir -p "/tmp/singularity_spark_$USER/spark_work"

    singularity exec \
        -B /mnt:/mnt,"/tmp/spark_cluster_$USER":/tmp \
        {worker_bindings} \
        "$SINGULARITY_IMG" \
        $CONDA_PATH run --no-capture-output -n $CONDA_ENV \
        $SPARK_ROOT/bin/spark-class org.apache.spark.deploy.worker.Worker \
        --cores "$SLURM_CPUS_ON_NODE" --memory "$SLURM_MEM_PER_NODE"M \
        --webui-port $SPARK_WORKER_WEBUI_PORT \
        --work-dir /tmp/spark_work \
        $MASTER_URL
fi
"""
    )
    launcher.close()
    return launcher


def find_spark_master_url(logfile: Path, attempt_sleep_time: int = 10) -> str:
    """Finds the Spark master URL in the logfile.

    Args:
        logfile: Path to logfile.

    Returns:
        Spark master URL.
    """
    logger.debug(f"Searching for Spark master URL in {logfile}")
    spark_master_url = ""
    read_logfile_attempt = 0
    while spark_master_url == "" and read_logfile_attempt < 10:
        read_logfile_attempt += 1
        sleep(attempt_sleep_time)
        try:
            with open(logfile, "r") as f:
                for line in f:
                    if "Starting Spark master at" in line:
                        spark_master_url = line.split(" ")[-1:]
                if spark_master_url == "":
                    logger.debug(
                        f"Unable to find Spark master URL in logfile. Waiting {attempt_sleep_time} seconds and retrying...\n"
                        f"(attempt {read_logfile_attempt}/10)"
                    )
        except FileNotFoundError:
            logger.debug(
                f"Logfile {logfile} not found. Waiting {attempt_sleep_time} seconds and retrying...\n"
                f"(attempt {read_logfile_attempt}/10)"
            )
            continue

    if spark_master_url == "":
        raise FileNotFoundError(
            f"Could not find expected logfile {logfile} and so could not extract "
            "the spark cluster master URL."
        )

    return spark_master_url[0].strip()
