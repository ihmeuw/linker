import atexit
import os
import tempfile
from pathlib import Path
from typing import TextIO

from linker.configuration import Config
from linker.utilities.slurm_utils import get_slurm_drmaa, submit_spark_cluster_job


def build_cluster(config: Config) -> str:
    """Builds a Spark cluster. Main function for the `build-spark-cluster` command.

    Returns:
        spark_master_url: Spark master URL.
    """
    drmaa = get_slurm_drmaa()
    session = drmaa.Session()
    session.initialize()

    spark_master_url = ""

    # call build_launch_script
    launcher = build_cluster_launch_script(config.environment["spark"]["workers"]["fqdn"])

    # submit job
    submit_spark_cluster_job(
        session=session,
        launcher=launcher,
        account=config.environment["slurm"]["account"],
        partition=config.environment["slurm"]["partition"],
        memory_per_cpu=config.environment["spark"]["workers"]["mem_per_cpu"],
        max_runtime=config.environment["spark"]["workers"]["time_limit"],
        num_workers=config.environment["spark"]["workers"]["num_workers"],
        cpus_per_task=config.environment["spark"]["workers"]["cpus_per_task"],
    )

    # grep log for spark master url or is there a better approach?
    return spark_master_url


def build_cluster_launch_script(domain_string) -> TextIO:
    """Generates a shell file that, on execution, spins up a Spark cluster."""
    launcher = tempfile.NamedTemporaryFile(
        mode="w",
        dir=".",
        prefix="spark_cluster_launcher_",
        suffix=".sh",
        delete=False,
    )

    # output_dir = str(worker_settings_file.resolve().parent)

    # TODO: 23/11/03 21:53:23 WARN MasterArguments: SPARK_MASTER_IP is deprecated, please use SPARK_MASTER_HOST
    launcher.write(
        f"""#!/bin/bash
#start_spark_slurm.sh automatically generated by linker

unset SPARK_HOME
CONDA_PATH=/opt/conda/condabin/conda # must be accessible within container
CONDA_ENV=spark_cluster
SINGULARITY_IMG=image.sif

export SPARK_ROOT=/opt/spark # within the container
export SPARK_WORKER_DIR=$HOME/.spark_temp/logs
export SPARK_LOCAL_DIRS=$HOME/.spark_temp/logs
export SPARK_MASTER_PORT=28508
export SPARK_MASTER_WEBUI_PORT=28509
export SPARK_WORKER_CORES=$SLURM_CPUS_PER_TASK
export SPARK_DAEMON_MEMORY=$(( $SLURM_MEM_PER_CPU * $SLURM_CPUS_PER_TASK / 2 ))m
export SPARK_MEM=$SPARK_DAEMON_MEMORY

if [ "$SLURM_PROCID" -eq 0 ]; then
    HOSTNAME=$(hostname)
    # TODO: use fqdn from configuration
    export SPARK_MASTER_IP="$HOSTNAME.{domain_string}"
    MASTER_NODE=$( scontrol show hostname "$SLURM_NODELIST "| head -n 1 )

    mkdir -p "/tmp/spark_cluster_$USER"
    singularity exec -B /mnt:/mnt,"/tmp/spark_cluster_$USER":/tmp $SINGULARITY_IMG \
     $CONDA_PATH run --no-capture-output -n $CONDA_ENV "$SPARK_ROOT/bin/spark-class" \
     org.apache.spark.deploy.master.Master --host "$SPARK_MASTER_IP" --port "$SPARK_MASTER_PORT" \
     --webui-port "$SPARK_MASTER_WEBUI_PORT"
else
    # TODO: This step assumes that SLURM_PROCID=0 corresponds to the first node in SLURM_NODELIST.
    #  Is this reasonable?
    MASTER_NODE=spark://$( scontrol show hostname "$SLURM_NODELIST" | head -n 1 ):"$SPARK_MASTER_PORT"

    mkdir -p "/tmp/spark_cluster_$USER"
    singularity exec -B /mnt:/mnt,"/tmp/spark_cluster_$USER":/tmp "$SINGULARITY_IMG" \
    "$CONDA_PATH" run --no-capture-output -n "$CONDA_ENV" "$SPARK_ROOT/bin/spark-class" \
     org.apache.spark.deploy.worker.Worker "$MASTER_NODE"
fi
"""
    )
    launcher.close()

    # TODO: handle cleanup, but not here!!
    # atexit.register(lambda: os.remove(launcher.name))
    return launcher
