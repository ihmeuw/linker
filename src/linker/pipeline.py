from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
import yaml

from linker.configuration import Config
from linker.implementation import Implementation
from linker.utilities.general_utils import exit_with_validation_error


class Pipeline:
    """Abstraction to handle pipeline specification and execution."""

    def __init__(self, config: Config):
        self.config = config
        self.implementations = self._get_implementations()
        self._validate()

    def run(
        self,
        runner: Callable,
        results_dir: Path,
        session: Optional["drmaa.Session"],
    ) -> None:
        number_of_steps = len(self.implementations)
        number_of_steps_digit_length = len(str(number_of_steps))
        for idx, implementation in enumerate(self.implementations):
            step_number = str(idx + 1).zfill(number_of_steps_digit_length)
            step_id = f"{step_number}_{implementation.step_name}"
            diagnostics_dir = results_dir / "diagnostics" / step_id
            diagnostics_dir.mkdir(parents=True, exist_ok=True)
            output_dir = self.get_output_dir(implementation.name, results_dir)
            if idx <= number_of_steps - 1:
                output_dir.mkdir(exist_ok=True)
            input_data = self.get_input_files(implementation.name, results_dir)
            implementation.run(
                session=session,
                runner=runner,
                step_id=step_id,
                input_data=input_data,
                results_dir=output_dir,
                diagnostics_dir=diagnostics_dir,
            )
        # Close the drmaa session (if one exists) once the pipeline is finished
        if session:
            session.exit()

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

        # TODO: validate that spark and slurm resources are requested if needed
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
        return {implementation.name: idx for idx, implementation in enumerate(self.implementations)}
    
    def get_input_files(self, implementation_name: str, results_dir: Path) -> list:
        idx = self.implementation_indices[implementation_name]
        if idx == 0:
            return [str(file) for file in self.config.input_data]
        else:
            previous_output_dir = self.get_output_dir(self.implementations[idx - 1].name, results_dir)
            return [str(previous_output_dir / "result.parquet")]
    
    def get_output_dir(self, implementation_name: str, results_dir: Path) -> Path:
        idx = self.implementation_indices[implementation_name]
        num_steps = len(self.implementations)
        step_number = str(idx + 1).zfill(len(str(len(self.implementations))))
        if idx == num_steps - 1:
            return results_dir

        return results_dir / "intermediate" / f"{step_number}_{self.implementations[idx].step_name}"
    
    def build_snakefile(self, results_dir: Path) -> None:
        def list_representer(dumper, data):
            return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        def quoted_scalar(dumper, data):
            if dumper.represented_objects.get(id(data)):  # Check if it's already a key
                return dumper.represent_scalar('tag:yaml.org,2002:str', data)
            else:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")

        yaml.add_representer(str, quoted_scalar)
        yaml.add_representer(list, list_representer)
        snakefile = results_dir / "Snakefile"
        sc = {}
        sc["rule all"] = {"input": f"{results_dir}/result.parquet"}
        for implementation in self.implementations:
            input_files = self.get_input_files(implementation.name, results_dir)
            output_dir = self.get_output_dir(implementation.name, results_dir)
            sc[f"rule {implementation.name}"] = {"input": input_files, "output": f"{output_dir}/result.parquet", "script": implementation.script}
        with open(snakefile, "w") as f:
            yaml.dump(sc, f, indent=4,default_flow_style=False)
        return snakefile
    
    
