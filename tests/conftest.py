"""Shared test fixtures.

The example host (``examples/libertadores_host.py``) is loaded by path rather than
imported as a package: ``examples/`` is a directory of standalone examples, not an
installable package. Exposing it through a fixture keeps the test modules free of
sys.path juggling.
"""

import importlib.util
import os

import pytest

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


def _load_example(name: str):
    path = os.path.join(EXAMPLES, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def libertadores_diagram():
    """The ``LibertadoresDiagram`` class from the example host module."""
    return _load_example("libertadores_host").LibertadoresDiagram
