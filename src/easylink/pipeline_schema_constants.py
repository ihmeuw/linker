from easylink.step import (
    Edge,
    HierarchicalStep,
    ImplementedStep,
    InputSlot,
    InputStep,
    ResultStep,
)
from easylink.utilities.validation_utils import validate_input_file_dummy

SCHEMA_NODES = [
    InputStep("input_data_schema", input_slots=[], output_slots=["file1"]),
    HierarchicalStep(
        "step_1",
        input_slots=[
            InputSlot(
                "step_1_main_input",
                "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                validate_input_file_dummy,
            )
        ],
        output_slots=["step_1_main_output"],
        nodes=[
            ImplementedStep(
                "step_1a",
                input_slots=[
                    InputSlot(
                        "step_1a_main_input",
                        "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                        validate_input_file_dummy,
                    )
                ],
                output_slots=["step_1a_main_output"],
            ),
            ImplementedStep(
                "step_1b",
                input_slots=[
                    InputSlot(
                        "step_1b_main_input",
                        "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                        validate_input_file_dummy,
                    )
                ],
                output_slots=["step_1b_main_output"],
            ),
        ],
        edges=[
            Edge("step_1a", "step_1b", "step_1a_main_output", "step_1b_main_input"),
        ],
        slot_mappings={
            "input": [("step_1a", "step_1_main_input", "step_1a_main_input")],
            "output": [("step_1b", "step_1_main_output", "step_1b_main_output")],
        },
    ),
    ImplementedStep(
        "step_2",
        input_slots=[
            InputSlot(
                "step_2_main_input",
                "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                validate_input_file_dummy,
            )
        ],
        output_slots=["step_2_main_output"],
    ),
    ImplementedStep(
        "step_3",
        input_slots=[
            InputSlot(
                "step_3_main_input",
                "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                validate_input_file_dummy,
            )
        ],
        output_slots=["step_3_main_output"],
    ),
    ImplementedStep(
        "step_4",
        input_slots=[
            InputSlot(
                "step_4_main_input",
                "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                validate_input_file_dummy,
            ),
            InputSlot(
                "step_4_secondary_input",
                "DUMMY_CONTAINER_SECONDARY_INPUT_FILE_PATHS",
                validate_input_file_dummy,
            ),
        ],
        output_slots=["step_4_main_output"],
    ),
    ResultStep(
        "results_schema",
        input_slots=[InputSlot("result", None, validate_input_file_dummy)],
        output_slots=[],
    ),
]
SCHEMA_EDGES = [
    Edge(
        in_node="input_data_schema",
        out_node="step_1",
        output_slot="file1",
        input_slot="step_1_main_input",
    ),
    Edge(
        in_node="input_data_schema",
        out_node="step_4",
        output_slot="file1",
        input_slot="step_4_secondary_input",
    ),
    Edge(
        in_node="step_1",
        out_node="step_2",
        output_slot="step_1_main_output",
        input_slot="step_2_main_input",
    ),
    Edge(
        in_node="step_2",
        out_node="step_3",
        output_slot="step_2_main_output",
        input_slot="step_3_main_input",
    ),
    Edge(
        in_node="step_3",
        out_node="step_4",
        output_slot="step_3_main_output",
        input_slot="step_4_main_input",
    ),
    Edge(
        in_node="step_4",
        out_node="results_schema",
        output_slot="step_4_main_output",
        input_slot="result",
    ),
]
ALLOWED_SCHEMA_PARAMS = {"development": (SCHEMA_NODES, SCHEMA_EDGES)}

TESTING_NODES = [
    InputStep("input_data_schema", input_slots=[], output_slots=["file1"]),
    ImplementedStep(
        "step_1",
        input_slots=[
            InputSlot(
                "step_1_main_input",
                "DUMMY_CONTAINER_MAIN_INPUT_FILE_PATHS",
                validate_input_file_dummy,
            )
        ],
        output_slots=["step_1_main_output"],
    ),
    ResultStep(
        "results_schema",
        input_slots=[InputSlot("result", None, validate_input_file_dummy)],
        output_slots=[],
    ),
]
TESTING_EDGES = [
    Edge(
        in_node="input_data_schema",
        out_node="step_1",
        output_slot="file1",
        input_slot="step_1_main_input",
    ),
    Edge(
        in_node="step_1",
        out_node="results_schema",
        output_slot="step_1_main_output",
        input_slot="result",
    ),
]
TESTING_SCHEMA_PARAMS = {"integration": (TESTING_NODES, TESTING_EDGES)}
