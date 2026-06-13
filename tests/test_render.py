"""Golden (snapshot) tests for SVG and HTML generation.

Each example is rendered and compared against a versioned reference under
``tests/golden/`` (an ``.svg`` and an ``.html`` per example). When the output
legitimately changes, regenerate the goldens with::

    PD_REGEN=1 pytest tests/test_render.py

and review the diff before committing.
"""

import glob
import os

import pytest

from matamata import load_stage, render_html, render_svg

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")
GOLDEN = os.path.join(os.path.dirname(__file__), "golden")

# libertadores-2026.json is host-resolved (one tie carries refs), so it is rendered
# through its example host (see the libertadores_diagram fixture) rather than the base
# loader; example_data.json is that host's lookup table, not a knockout stage document.
HOST_EXAMPLE = "libertadores-2026.json"
# copa-rio-de-la-plata-2026.json is a documentation example for the get_crest hook (it is
# rendered with crests through examples/copa_rio_host.py for docs/copa-rio-de-la-plata.png
# and its table variant). knockout-8.json *is* a base-loader stage (no images, snapshot-
# tested below), but it is also rendered with flags through examples/world_cup_flags_host.py
# for docs/flags.png and its table variant; that crest render is illustrative, not
# snapshot-tested. crest_data.json and flag_data.json are the hosts' lookup tables, not
# stage documents, so they are skipped by the base-loader tests below.
NON_STAGE = {
    HOST_EXAMPLE,
    "example_data.json",
    "copa-rio-de-la-plata-2026.json",
    "crest_data.json",
    "flag_data.json",
}
EXAMPLE_FILES = sorted(
    name
    for name in (
        os.path.basename(p) for p in glob.glob(os.path.join(EXAMPLES, "*.json"))
    )
    if name not in NON_STAGE
)


def _golden_path(name: str, ext: str) -> str:
    return os.path.join(GOLDEN, name.replace(".json", ext))


def _assert_golden(rendered: str, name: str, ext: str) -> None:
    path = _golden_path(name, ext)
    if os.environ.get("PD_REGEN"):
        os.makedirs(GOLDEN, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(rendered)
        pytest.skip(f"regenerated {os.path.basename(path)}")

    assert os.path.exists(path), f"missing golden {path}; run with PD_REGEN=1"
    with open(path, encoding="utf-8") as fh:
        assert rendered == fh.read()


def _assert_well_formed(rendered: str, root: str) -> None:
    import xml.dom.minidom

    xml.dom.minidom.parseString(rendered)  # raises on malformed XML
    assert rendered.startswith(f"<{root}")
    assert rendered.rstrip().endswith(f"</{root}>")


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_svg_matches_golden(name):
    _assert_golden(render_svg(load_stage(os.path.join(EXAMPLES, name))), name, ".svg")


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_svg_is_well_formed(name):
    _assert_well_formed(render_svg(load_stage(os.path.join(EXAMPLES, name))), "svg")


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_html_matches_golden(name):
    _assert_golden(render_html(load_stage(os.path.join(EXAMPLES, name))), name, ".html")


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_html_is_well_formed(name):
    _assert_well_formed(render_html(load_stage(os.path.join(EXAMPLES, name))), "div")


def test_host_example_matches_golden(libertadores_diagram):
    _assert_golden(libertadores_diagram().render(), HOST_EXAMPLE, ".svg")


def test_host_example_is_well_formed(libertadores_diagram):
    _assert_well_formed(libertadores_diagram().render(), "svg")


def test_host_example_html_matches_golden(libertadores_diagram):
    _assert_golden(libertadores_diagram().render("html"), HOST_EXAMPLE, ".html")


def test_unknown_render_format_is_rejected(libertadores_diagram):
    from matamata.parse import StageError

    with pytest.raises(StageError):
        libertadores_diagram().render("pdf")


def test_html_emphasizes_only_the_explicit_winner():
    doc = {
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {
                        "id": "f",
                        "legs": [
                            {"team1": "A", "goals1": 2, "team2": "B", "goals2": 0}
                        ],
                        "winner": 1,
                    }
                ],
            }
        ]
    }
    from matamata import parse_stage

    html = render_html(parse_stage(doc))
    assert html.count('class="pd-side pd-win"') == 1
    assert '<h3 class="pd-header">Final</h3>' in html

    del doc["rounds"][0]["matches"][0]["winner"]
    assert 'class="pd-side pd-win"' not in render_html(parse_stage(doc))


def test_cli_infers_html_from_the_output_extension(tmp_path):
    from matamata.__main__ import main

    out = tmp_path / "schedule.html"
    src = os.path.join(EXAMPLES, "knockout-8.json")
    assert main([src, "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith('<div class="pd-stage">')

    svg_out = tmp_path / "schedule.svg"
    assert main([src, "-o", str(svg_out)]) == 0
    assert svg_out.read_text(encoding="utf-8").startswith("<svg")

    forced = tmp_path / "schedule.txt"
    assert main([src, "-o", str(forced), "-f", "html"]) == 0
    assert forced.read_text(encoding="utf-8").startswith('<div class="pd-stage">')
