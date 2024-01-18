import pytest

from linker.implementation import Implementation


def test_implementation_is_missing_from_metadata():
    with pytest.raises(
        RuntimeError,
        match="Implementation 'some-other-implementation' is not defined in implementation_metadata.yaml",
    ):
        Implementation(
            step_name="some-step",
            implementation_name="some-other-implementation",
            implementation_config=None,
            container_engine="undefined",
            environment={"foo": "bar"},
        )
