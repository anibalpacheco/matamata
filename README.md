# matamata

[![PyPI](https://img.shields.io/pypi/v/matamata.svg)](https://pypi.org/project/matamata/)
[![Python versions](https://img.shields.io/pypi/pyversions/matamata.svg)](https://pypi.org/project/matamata/)
[![CI](https://github.com/anibalpacheco/matamata/actions/workflows/ci.yml/badge.svg)](https://github.com/anibalpacheco/matamata/actions/workflows/ci.yml)
[![Docs](https://github.com/anibalpacheco/matamata/actions/workflows/docs.yml/badge.svg)](https://anibalpacheco.github.io/matamata/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**matamata** is a JSON format for modeling tournament knockout stages, defined with a JSON Schema, plus a Python renderer to SVG or HTML tables.

**matamata** also lets a host system map documents representing championship
knockout stages onto its own business objects (e.g. a Championship or Cup entity) and persist
them apart from any presentation concern — updating results means editing a document,
never the code.

Example rendered from
[`examples/world-cup-2022.json`](https://github.com/anibalpacheco/matamata/blob/main/examples/world-cup-2022.json) —
the finished Qatar 2022 knockout from the Round of 16 to the final plus third place, with
each match's date and venue from the document and national flags supplied by a host
([`examples/world_cup_2022_host.py`](https://github.com/anibalpacheco/matamata/blob/main/examples/world_cup_2022_host.py)):

![World Cup 2022 knockout stage](https://raw.githubusercontent.com/anibalpacheco/matamata/main/docs/world-cup-2022.png)

## Quickstart

Requires Python ≥ 3.10. No runtime dependencies. Install from PyPI:

```bash
pip install matamata
```

Render a knockout stage document — plain JSON following
[the format](https://anibalpacheco.github.io/matamata/format/) — to an
SVG file, or to an HTML table for small screens:

```bash
# the installed command
matamata stage.json -o schedule.svg

# or via the module, writing to stdout
python -m matamata stage.json > schedule.svg

# or as an HTML table
matamata stage.json -o schedule.html
```

Open the result in a browser to view the schedule. From Python:

```python
from matamata import load_stage, render_svg

svg = render_svg(load_stage("stage.json"))
```

Ready-to-render worked examples live in
[`examples/`](https://github.com/anibalpacheco/matamata/tree/main/examples). For the
latest unreleased commit use
`pip install git+https://github.com/anibalpacheco/matamata.git`; to work on matamata
itself, clone the repo and `pip install -e .`.

## Examples

Both examples are rendered from the JSON files in [`examples/`](https://github.com/anibalpacheco/matamata/tree/main/examples).

The World Cup example above shows single matches — one goal figure per side, with shootouts
in parentheses (Argentina beat the Netherlands in the quarterfinals and France in the final
on penalties). Each match draws a metadata line with its date and venue, the bracket is
drawn in the default **symmetric** (FIFA-style) layout with the third-place match below the
final, and the winner of each match is emphasized. The flags come from a host:
`world-cup-2022.json` carries no ids, so [`examples/world_cup_2022_host.py`](https://github.com/anibalpacheco/matamata/blob/main/examples/world_cup_2022_host.py)
resolves each national team's flag from its name, while the dates and venues live in the
document itself.

The Copa Libertadores example shows two-legged ties — each leg's goals are shown,
shootouts appear in parentheses, and the winner of each tie is emphasized. Its first
quarterfinal is **host-resolved**: its legs carry only a `ref`, so its teams and scores
come from `get_match` (see
[`examples/libertadores_host.py`](https://github.com/anibalpacheco/matamata/blob/main/examples/libertadores_host.py)) rather than from the
document. Played ties take their team names from the legs; the final is a single match —
one leg, so just one goal figure per side — with its `winnerof` links wiring the
advancement tree. The demo also renders it in Spanish (round names localized via the
`translate` hook) and in local `America/Montevideo` time (the GMT kickoff times converted),
showing the i18n and `timezone` features:

![Copa Libertadores 2026 knockout stage](https://raw.githubusercontent.com/anibalpacheco/matamata/main/docs/libertadores-2026.png)

## The format

The document is plain JSON, so any system can store and exchange it natively, and the
language is designed so a match can evolve from a **placeholder** (e.g. "winner
of QF1") into a **reference to a real match entity** — each leg can carry a `ref` to
the real game, resolved dynamically by the host — without changing the language. The
advancement tree is laid out **deterministically**: coordinates are
computed directly and the SVG is emitted as a string, with no layout engine and no
heavy dependencies.

See [the format specification](https://anibalpacheco.github.io/matamata/format/) and its
[JSON Schema](https://anibalpacheco.github.io/matamata/schema.json). Worked examples live in
[`examples/`](https://github.com/anibalpacheco/matamata/tree/main/examples).

Minimal example:

```json
{
  "tournament": "Copa Libertadores",
  "season": "2026",
  "rounds": [
    {
      "name": "Final",
      "matches": [
        {
          "id": "final",
          "legs": [
            { "team1": "Flamengo", "goals1": 1, "team2": "River Plate", "goals2": 2 }
          ],
          "winner": 2
        }
      ]
    }
  ]
}
```

## Documentation

[The manual](https://anibalpacheco.github.io/matamata/) covers rendering from the CLI and from Python
(e.g. a Django view), feeding live data from your own database through
`KnockoutStage`, updating the stored document with `apply_results` — including a
before/after walkthrough of one call — and running the test suite.

## Status

Working: the language spec, JSON Schema, Python renderer, CLI and tests are in place,
and the package is installable from GitHub.
