from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple

from easylink.configuration import Config
from easylink.implementation import Implementation
from easylink.rule import ImplementedRule, InputValidationRule, TargetRule
from easylink.utilities.general_utils import exit_with_validation_error
from easylink.utilities.paths import SPARK_SNAKEFILE
from easylink.utilities.validation_utils import validate_input_file_dummy
from loguru import logger


class Pipeline:
    """Abstraction to handle pipeline specification and execution."""

    def __init__(self, config: Config):
        self.config = config
        self.implementations = self._get_implementations()
        # TODO [MIC-4880]: refactor into validation object
        self._validate()

    def _get_implementations(self) -> Tuple[Implementation, ...]:
        return tuple(
            Implementation(
                config=self.config,
                step=step,
            )
            for step in self.config.schema.steps
        )

    def _validate(self) -> None:
        """Validates the pipeline."""

        errors = {**self._validate_implementations()}

        if errors:
            exit_with_validation_error(errors)

    def _validate_implementations(self) -> Dict:
        """Validates each individual Implementation instance."""
        errors = defaultdict(dict)
        for implementation in self.implementations:
            implementation_errors = implementation.validate()
            if implementation_errors:
                errors["IMPLEMENTATION ERRORS"][implementation.name] = implementation_errors
        return errors

    @property
    def implementation_indices(self) -> dict:
        return {
            implementation.name: idx
            for idx, implementation in enumerate(self.implementations)
        }

    @property
    def snakefile_path(self) -> Path:
        return self.config.results_dir / "Snakefile"

    # The following are in Pipeline instead of Implementation because they require
    # information about the entire pipeline (namely the index number),
    # not just the individual implementation.

    def get_step_id(self, implementation: Implementation) -> str:
        idx = self.implementation_indices[implementation.name]
        step_number = str(idx + 1).zfill(len(str(len(self.implementations))))
        return f"{step_number}_{implementation.step_name}"

    def get_input_files(self, implementation: Implementation) -> list:
        idx = self.implementation_indices[implementation.name]
        if idx == 0:
            return [str(file) for file in self.config.input_data]
        else:
            previous_output_dir = self.get_output_dir(self.implementations[idx - 1])
            return [str(previous_output_dir / "result.parquet")]

    def get_output_dir(self, implementation: Implementation) -> Path:
        idx = self.implementation_indices[implementation.name]
        if idx == len(self.implementations) - 1:
            return Path()

        return Path("intermediate") / self.get_step_id(implementation)

    def get_diagnostics_dir(self, implementation: Implementation) -> Path:
        return Path("diagnostics") / self.get_step_id(implementation)

    def build_snakefile(self) -> Path:
        if self.snakefile_path.is_file():
            logger.warning("Snakefile already exists, overwriting.")
            self.snakefile_path.unlink()
        self.write_imports()
        self.write_config()
        self.write_target_rules()
        if self.config.spark:
            self.write_spark_module()
        for implementation in self.implementations:
            self.write_implementation_rules(implementation)
        return self.snakefile_path

    def write_imports(self) -> None:
        with open(self.snakefile_path, "a") as f:
            f.write("from easylink.utilities import validation_utils")

    def write_target_rules(self) -> None:
        final_output = ["result.parquet"]
        validator_file = str("input_validations/final_validator")
        # Snakemake resolves the DAG based on the first rule, so we put the target
        # before the validation
        target_rule = TargetRule(
            target_files=final_output,
            validation=validator_file,
            requires_spark=bool(self.config.spark),
        )
        final_validation = InputValidationRule(
            name="results",
            input=final_output,
            output=validator_file,
            validator=validate_input_file_dummy,
        )
        target_rule.write_to_snakefile(self.snakefile_path)
        final_validation.write_to_snakefile(self.snakefile_path)

    def write_implementation_rules(self, implementation: Implementation) -> None:
        input_files = self.get_input_files(implementation)
        output_files = [str(self.get_output_dir(implementation) / "result.parquet")]
        diagnostics_dir = self.get_diagnostics_dir(implementation)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        validation_file = f"input_validations/{implementation.validation_filename}"
        resources = (
            self.config.slurm_resources
            if self.config.computing_environment == "slurm"
            else None
        )
        validation_rule = InputValidationRule(
            name=implementation.name,
            input=input_files,
            output=validation_file,
            validator=implementation.step.input_validator,
        )
        implementation_rule = ImplementedRule(
            step_name=implementation.step_name,
            implementation_name=implementation.name,
            execution_input=input_files,
            validation=validation_file,
            output=output_files,
            resources=resources,
            envvars=implementation.environment_variables,
            diagnostics_dir=str(diagnostics_dir),
            image_path=implementation.singularity_image_path,
            script_cmd=implementation.script_cmd,
            requires_spark=implementation.requires_spark,
        )
        validation_rule.write_to_snakefile(self.snakefile_path)
        implementation_rule.write_to_snakefile(self.snakefile_path)

    def write_config(self) -> None:
        with open(self.snakefile_path, "a") as f:
            if self.config.spark:
                f.write(
                    f"\nscattergather:\n\tnum_workers={self.config.spark_resources['num_workers']},"
                )

    def write_spark_module(self) -> None:
        with open(self.snakefile_path, "a") as f:
            module = f"""
module spark_cluster:
    snakefile: '{SPARK_SNAKEFILE}'
    config: config

use rule * from spark_cluster
use rule terminate_spark from spark_cluster with:
    input: rules.all.input.final_output"""
            if self.config.computing_environment == "slurm":
                module += f"""
use rule start_spark_master from spark_cluster with:
    resources:
        slurm_account={self.config.slurm_resources['slurm_account']},
        slurm_partition={self.config.slurm_resources['slurm_partition']},
        mem_mb={self.config.spark_resources['slurm_mem_mb']},
        runtime={self.config.spark_resources['runtime']},
        cpus_per_task={self.config.spark_resources['cpus_per_task']},
        slurm_extra="--output 'spark_logs/start_spark_master-slurm-%j.log'"
use rule start_spark_worker from spark_cluster with:
    resources:
        slurm_account={self.config.slurm_resources['slurm_account']},
        slurm_partition={self.config.slurm_resources['slurm_partition']},
        mem_mb={self.config.spark_resources['slurm_mem_mb']},
        runtime={self.config.spark_resources['runtime']},
        cpus_per_task={self.config.spark_resources['cpus_per_task']},
        slurm_extra="--output 'spark_logs/start_spark_worker-slurm-%j.log'"
    params:
        terminate_file_name=rules.terminate_spark.output,
        user=os.environ["USER"],
        cores={self.config.spark_resources['cpus_per_task']},
        memory={self.config.spark_resources['mem_mb']}
                        """
            f.write(module)