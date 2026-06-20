"""Golden (snapshot) tests for SVG and HTML generation.

Each example is rendered and compared against a versioned reference under
``tests/golden/`` (an ``.svg`` plus an ``.html`` for the flat HTML layout and a
``.stacked.html`` for the stacked one, per example). When the output legitimately
changes, regenerate the goldens with::

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
# and its table variant); crest_data.json is that host's lookup table, not a stage document,
# so it is skipped by the base-loader tests below. knockout-8.json *is* a base-loader stage
# (no images, snapshot-tested below).
# world-cup-2026.json is a gallery-only illustration (the full 32-team symmetric bracket of
# the in-progress World Cup, all seed placeholders); like the host examples it is not
# snapshot-tested, so it carries no goldens.
# world-cup-2022.json *is* a base-loader stage (snapshot-tested below), but it is also
# rendered with flags through examples/world_cup_2022_host.py for docs/world-cup-2022.png;
# world_cup_2022_flags.json is that host's lookup table, not a stage document.
NON_STAGE = {
    HOST_EXAMPLE,
    "example_data.json",
    "copa-rio-de-la-plata-2026.json",
    "crest_data.json",
    "world-cup-2026.json",
    "world_cup_2022_flags.json",
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


# The HTML renderer offers two layouts; each gets its own golden extension.
HTML_LAYOUTS = {"flat": ".html", "stacked": ".stacked.html"}


@pytest.mark.parametrize("name", EXAMPLE_FILES)
@pytest.mark.parametrize("layout", sorted(HTML_LAYOUTS))
def test_html_matches_golden(name, layout):
    rendered = render_html(load_stage(os.path.join(EXAMPLES, name)), layout=layout)
    _assert_golden(rendered, name, HTML_LAYOUTS[layout])


@pytest.mark.parametrize("name", EXAMPLE_FILES)
@pytest.mark.parametrize("layout", sorted(HTML_LAYOUTS))
def test_html_is_well_formed(name, layout):
    rendered = render_html(load_stage(os.path.join(EXAMPLES, name)), layout=layout)
    _assert_well_formed(rendered, "div")


def test_unknown_html_layout_is_rejected():
    with pytest.raises(ValueError):
        render_html(
            load_stage(os.path.join(EXAMPLES, "knockout-8.json")), layout="grid"
        )


def test_dark_mode_rules_are_embedded():
    # Dark mode is automatic via a prefers-color-scheme media query baked into the
    # default <style>; both renderers carry it, re-coloring the pd-* classes.
    stage = load_stage(os.path.join(EXAMPLES, "knockout-8.json"))
    svg = render_svg(stage)
    assert "@media (prefers-color-scheme: dark)" in svg
    assert ".pd-bg { fill: #0f172a; }" in svg
    html = render_html(stage)
    assert "@media (prefers-color-scheme: dark)" in html
    assert ".pd-stage { color: #e5e7eb; background: #0f172a; }" in html


def test_crest_shape_flag_renders_rectangular_framed_images():
    from matamata import parse_stage

    doc = {
        "render": {"crest_shape": "flag"},
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {
                        "id": "f",
                        "legs": [
                            {"team1": "A", "goals1": 1, "team2": "B", "goals2": 0}
                        ],
                        "winner": 1,
                    }
                ],
            }
        ],
    }
    stage = parse_stage(doc)
    # The host's get_crest normally sets this; inject one to exercise rendering.
    stage.rounds[0].matches[0].home.crest = "a.svg"

    html = render_html(stage)
    assert 'class="pd-stage pd-flags"' in html
    svg = render_svg(stage)
    assert 'class="pd-crest-frame"' in svg
    assert 'width="24"' in svg  # 3:2 flag box, not the 16px square

    # Default ("square"): no flag class, square crest, no frame. (The pd-flags and
    # pd-crest-frame rules always sit in the <style> block, so assert on real usage.)
    doc["render"] = {}
    square = parse_stage(doc)
    square.rounds[0].matches[0].home.crest = "a.svg"
    assert 'class="pd-stage pd-flags"' not in render_html(square)
    square_svg = render_svg(square)
    assert 'class="pd-crest-frame"' not in square_svg
    assert 'width="16"' in square_svg


# Language and timezone are the caller's choice; the demo renders in Spanish and
# Montevideo time, and the goldens capture that, matching the docs preview.
_ES = {"language": "es", "timezone": "America/Montevideo"}


def test_host_example_matches_golden(libertadores_diagram):
    _assert_golden(libertadores_diagram().render(**_ES), HOST_EXAMPLE, ".svg")


def test_host_example_is_well_formed(libertadores_diagram):
    _assert_well_formed(libertadores_diagram().render(**_ES), "svg")


def test_host_example_html_matches_golden(libertadores_diagram):
    _assert_golden(libertadores_diagram().render("html", **_ES), HOST_EXAMPLE, ".html")


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

    # Stacked: exactly one of the two side rows is emphasized.
    stacked = render_html(parse_stage(doc), layout="stacked")
    assert stacked.count('class="pd-side pd-win"') == 1
    assert '<h3 class="pd-header">Final</h3>' in stacked

    # Flat: the winning side's three cells (name, crest, score) carry pd-win.
    flat = render_html(parse_stage(doc), layout="flat")
    assert flat.count('pd-win"') == 3
    assert '<td class="pd-vs">x</td>' in flat

    del doc["rounds"][0]["matches"][0]["winner"]
    assert 'pd-win"' not in render_html(parse_stage(doc), layout="stacked")
    assert 'pd-win"' not in render_html(parse_stage(doc), layout="flat")


def test_metadata_line_is_rendered_in_svg_and_stacked():
    from matamata import parse_stage

    doc = {
        "render": {"dt_format": "dd/MM HH:mm", "box_width": 300},
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {
                        "id": "f",
                        "winner": 1,
                        "legs": [
                            {
                                "team1": "A",
                                "goals1": 1,
                                "team2": "B",
                                "goals2": 0,
                                "dt": "2026-05-01 18:00",
                                "venue": "Centenario",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    stage = parse_stage(doc)
    svg = render_svg(stage)
    # The id is wrapped in a bold tspan; the date/venue follow in normal weight.
    assert '<tspan class="pd-meta-id">F</tspan> · 01/05 18:00 Centenario' in svg
    stacked = render_html(stage, layout="stacked")
    assert (
        '<div class="pd-meta"><span class="pd-meta-id">F</span>'
        " · 01/05 18:00 Centenario</div>" in stacked
    )


def test_flat_splits_a_two_leg_tie_into_two_id_rows():
    from matamata import parse_stage

    doc = {
        "rounds": [
            {
                "name": "SF",
                "matches": [
                    {
                        "id": "sf1",
                        "winner": 1,  # the top side (Boca)
                        "legs": [
                            {
                                "team1": "Boca",
                                "goals1": 0,
                                "team2": "River",
                                "goals2": 0,
                            },
                            {
                                "team1": "River",
                                "goals1": 1,
                                "team2": "Boca",
                                "goals2": 2,
                            },
                        ],
                    }
                ],
            }
        ]
    }
    import re

    flat = render_html(parse_stage(doc), layout="flat")
    assert flat.count('<tr class="pd-match-row">') == 2  # one row per leg
    # A full-width metadata row sits above each leg row, repeating the bold id.
    assert flat.count('<tr class="pd-meta-row">') == 2
    assert flat.count('<td class="pd-meta" colspan="7">') == 2
    assert flat.count('<span class="pd-meta-id">SF1</span>') == 2  # bold id repeated
    # The winning (Boca) side's three cells carry pd-win, on each of the two rows.
    assert flat.count('pd-win"') == 6
    # Each row honors that leg's localía: the local team (JSON team1) sits on the left.
    rows = [
        re.findall(r"pd-team\d[^>]*>([^<]+)<", r)
        for r in flat.split("</tr>")
        if '<tr class="pd-match-row">' in r
    ]
    assert rows == [["Boca", "River"], ["River", "Boca"]]


def test_id_less_match_shows_no_id_label():
    from matamata import parse_stage

    doc = {
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {  # no id: nothing references the final
                        "legs": [
                            {"team1": "A", "goals1": 1, "team2": "B", "goals2": 0}
                        ],
                    }
                ],
            }
        ]
    }
    stage = parse_stage(doc)
    svg = render_svg(stage)
    assert '<text class="pd-meta"' not in svg  # no metadata text for the id-less final
    flat = render_html(stage, layout="flat")
    assert '<tr class="pd-meta-row">' not in flat  # nothing to show -> no metadata row
    stacked = render_html(stage, layout="stacked")
    assert '<div class="pd-meta">' not in stacked  # nothing to show -> no div


def test_show_metadata_false_drops_the_line_and_the_flat_column():
    from matamata import parse_stage

    doc = {
        "render": {"show_metadata": False},
        "rounds": [
            {
                "name": "F",
                "matches": [
                    {
                        "id": "f",
                        "legs": [
                            {
                                "team1": "A",
                                "goals1": 1,
                                "team2": "B",
                                "goals2": 0,
                                "dt": "2026-05-01 18:00",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    stage = parse_stage(doc)
    assert '<text class="pd-meta"' not in render_svg(stage)
    flat = render_html(stage, layout="flat")
    assert '<tr class="pd-meta-row">' not in flat  # no metadata rows
    assert '<td class="pd-meta"' not in flat
    assert '<div class="pd-meta">' not in render_html(stage, layout="stacked")


def test_symmetric_layout_mirrors_the_bracket():
    from matamata.layout import compute_layout

    stage = load_stage(os.path.join(EXAMPLES, "symmetric-8.json"))
    layout = compute_layout(stage)

    # Every round but the final draws over two columns (left + right), so its header is
    # emitted twice; the final's single central header is emitted once.
    names = [h.name for h in layout.headers]
    assert names.count("Quarterfinals") == 2
    assert names.count("Semifinals") == 2
    assert names.count("Final") == 1

    by_id = {pm.match.id: pm for pm in layout.matches}
    # The final and the third place are both id-less; tell them apart by their links.
    final = next(
        pm
        for pm in layout.matches
        if pm.match.home.winner_of is not None and pm.match.id is None
    )
    third = next(pm for pm in layout.matches if pm.match.home.loser_of is not None)

    # The two semifinals meet in the centre at equal height, the final straddling them...
    assert by_id["sf1"].cy == by_id["sf2"].cy
    assert by_id["sf1"].x < final.x < by_id["sf2"].x
    # ...lifted into the gap above them, with the third place dropped below — both central.
    assert final.cy < by_id["sf1"].cy < third.cy
    assert final.x == third.x

    # The quarterfinals' connectors run inward toward the centre: the left half rightward,
    # the right half leftward (leaving a box's left edge). Both directions are present.
    runs_left = [c for c in layout.connectors if c.points[0][0] > c.points[-1][0]]
    runs_right = [c for c in layout.connectors if c.points[0][0] < c.points[-1][0]]
    assert runs_left and runs_right


def test_cli_infers_html_from_the_output_extension(tmp_path):
    from matamata.__main__ import main

    out = tmp_path / "schedule.html"
    src = os.path.join(EXAMPLES, "knockout-8.json")
    assert main([src, "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith('<div class="pd-stage')

    svg_out = tmp_path / "schedule.svg"
    assert main([src, "-o", str(svg_out)]) == 0
    assert svg_out.read_text(encoding="utf-8").startswith("<svg")

    forced = tmp_path / "schedule.txt"
    assert main([src, "-o", str(forced), "-f", "html"]) == 0
    assert forced.read_text(encoding="utf-8").startswith('<div class="pd-stage')
