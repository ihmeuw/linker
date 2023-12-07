import atexit
import os
import tempfile
from pathlib import Path
from time import sleep
from typing import TextIO

from loguru import logger

from linker.configuration import Config
from linker.utilities.paths import CONTAINER_DIR
from linker.utilities.slurm_utils import get_slurm_drmaa, submit_spark_cluster_job


def build_cluster(config: Config) -> str:
    """Builds a Spark cluster. Main function for the `build-spark-cluster` command.

    Args:
        config: Config object.

    Returns:
        spark_master_url: Spark master URL.
    """
    drmaa = get_slurm_drmaa()
    session = drmaa.Session()
    session.initialize()

    # call build_launch_script
    launcher = build_cluster_launch_script()

    # submit job
    logfile = submit_spark_cluster_job(
        session=session,
        launcher=launcher,
        account=config.environment["slurm"]["account"],
        partition=config.environment["slurm"]["partition"],
        memory_per_cpu=config.environment["spark"]["workers"]["mem_per_cpu"],
        max_runtime=config.environment["spark"]["workers"]["time_limit"],
        num_workers=config.environment["spark"]["workers"]["num_workers"],
        cpus_per_task=config.environment["spark"]["workers"]["cpus_per_task"],
    )

    spark_master_url = find_spark_master_url(logfile)
    logger.info(f"Spark master URL: {spark_master_url}")
    return spark_master_url


def build_cluster_launch_script() -> TextIO:
    """Generates a shell file that, on execution, spins up a Spark cluster.

    Returns:
        launcher: Launcher script.
    """
    launcher = tempfile.NamedTemporaryFile(
        mode="w",
        dir=".",
        prefix="spark_cluster_launcher_",
        suffix=".sh",
        delete=False,
    )

    # TODO: fix the $HOME usage, not accessible
    # TODO: update the SINGULARITY_IMG path to point at the other container dir
    launcher.write(
        f"""#!/bin/bash
#start_spark_slurm.sh automatically generated by linker

unset SPARK_HOME
CONDA_PATH=/opt/conda/condabin/conda # must be accessible within container
CONDA_ENV=spark_cluster
SINGULARITY_IMG={CONTAINER_DIR / "spark_cluster" / "image.sif"}

export SPARK_ROOT=/opt/spark # within the container
export SPARK_WORKER_DIR=$HOME/.spark_temp/logs
export SPARK_LOCAL_DIRS=$HOME/.spark_temp/logs
export SPARK_MASTER_PORT=28508
export SPARK_MASTER_WEBUI_PORT=28509
export SPARK_WORKER_CORES=$SLURM_CPUS_PER_TASK
export SPARK_DAEMON_MEMORY=$(( $SLURM_MEM_PER_CPU * $SLURM_CPUS_PER_TASK / 2 ))m
export SPARK_MEM=$SPARK_DAEMON_MEMORY

echo "XXX Debug hello from $(hostname -f)"
if [ "$SLURM_PROCID" -eq 0 ]; then
    SPARK_MASTER_HOST=$(hostname -f)

    mkdir -p "/tmp/spark_cluster_$USER"
    singularity exec -B /mnt:/mnt,"/tmp/spark_cluster_$USER":/tmp $SINGULARITY_IMG \
     $CONDA_PATH run --no-capture-output -n $CONDA_ENV "$SPARK_ROOT/bin/spark-class" \
     org.apache.spark.deploy.master.Master --host "$SPARK_MASTER_HOST" --port "$SPARK_MASTER_PORT" \
     --webui-port "$SPARK_MASTER_WEBUI_PORT"
else
    echo "DEBUG XXX: I AM A WORKER"
    MASTER_HOST=$( scontrol show hostname $SLURM_NODELIST | head -n 1 | xargs -I {{}} host {{}} | awk '{{print $1}}')
    MASTER_URL=spark://$MASTER_HOST:$SPARK_MASTER_PORT

    mkdir -p "/tmp/spark_cluster_$USER"
    singularity exec -B /mnt:/mnt,"/tmp/spark_cluster_$USER":/tmp "$SINGULARITY_IMG" \
    "$CONDA_PATH" run --no-capture-output -n "$CONDA_ENV" "$SPARK_ROOT/bin/spark-class" \
     org.apache.spark.deploy.worker.Worker "$MASTER_URL"
fi
"""
    )
    launcher.close()
    # XXX TODO uncomment this after debug
    # atexit.register(lambda: os.remove(launcher.name))
    return launcher


def find_spark_master_url(logfile: Path) -> str:
    """Finds the Spark master URL in the logfile.

    Args:
        logfile: Path to logfile.

    Returns:
        Spark master URL.
    """
    logger.debug(f"Searching for Spark master URL in {logfile}")
    spark_master_url = ""
    while spark_master_url == "":
        sleep(5)
        with open(logfile, "r") as f:
            for line in f:
                if "Starting Spark master at" in line:
                    spark_master_url = line.split(" ")[-1:]
    return spark_master_url[0].strip()
