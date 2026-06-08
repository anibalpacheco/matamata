"""Golden (snapshot) tests for SVG generation.

Each example is rendered and compared against a versioned reference SVG under
``tests/golden/``. When the output legitimately changes, regenerate the goldens with::

    PD_REGEN=1 pytest tests/test_render.py

and review the diff before committing.
"""

import glob
import os

import pytest

from playoff_diagrams import load_bracket, render_svg

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")
GOLDEN = os.path.join(os.path.dirname(__file__), "golden")

# libertadores-2026.json is host-resolved (one tie carries refs), so it is rendered
# through its example host (see the libertadores_diagram fixture) rather than the base
# loader; example_data.json is that host's lookup table, not a bracket document.
HOST_EXAMPLE = "libertadores-2026.json"
NON_BRACKET = {HOST_EXAMPLE, "example_data.json"}
EXAMPLE_FILES = sorted(
    name
    for name in (
        os.path.basename(p) for p in glob.glob(os.path.join(EXAMPLES, "*.json"))
    )
    if name not in NON_BRACKET
)


def _golden_path(name: str) -> str:
    return os.path.join(GOLDEN, name.replace(".json", ".svg"))


def _assert_golden(svg: str, name: str) -> None:
    path = _golden_path(name)
    if os.environ.get("PD_REGEN"):
        os.makedirs(GOLDEN, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        pytest.skip(f"regenerated {os.path.basename(path)}")

    assert os.path.exists(path), f"missing golden {path}; run with PD_REGEN=1"
    with open(path, encoding="utf-8") as fh:
        assert svg == fh.read()


def _assert_well_formed(svg: str) -> None:
    import xml.dom.minidom

    xml.dom.minidom.parseString(svg)  # raises on malformed XML
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_svg_matches_golden(name):
    _assert_golden(render_svg(load_bracket(os.path.join(EXAMPLES, name))), name)


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_svg_is_well_formed(name):
    _assert_well_formed(render_svg(load_bracket(os.path.join(EXAMPLES, name))))


def test_host_example_matches_golden(libertadores_diagram):
    _assert_golden(libertadores_diagram().render(), HOST_EXAMPLE)


def test_host_example_is_well_formed(libertadores_diagram):
    _assert_well_formed(libertadores_diagram().render())
