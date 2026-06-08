# playoff-diagrams

[![CI](https://github.com/anibalpacheco/playoff-diagrams/actions/workflows/ci.yml/badge.svg)](https://github.com/anibalpacheco/playoff-diagrams/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Render a football (soccer) **playoff bracket** as an **SVG**, on the fly, from a
**JSON source document**.

The bracket is described by a small JSON "language" that is meant to live in a
database field (e.g. Postgres `JSONB`) on a championship/cup entity. Updating results
means editing that JSON — no code changes, and no per-cup HTML templates to maintain.

## Examples

Both diagrams below are rendered straight from the JSON files in
[`examples/`](examples/), with no per-cup templates involved.

Two-legged ties with `"scores": "legs"`
([`libertadores-2026.json`](examples/libertadores-2026.json)) — each leg's goals are
shown, shootouts appear in parentheses, the winner of each tie is emphasized, and the
advancing team recorded on each `winner_of` slot carries through the rounds:

![Copa Libertadores 2026 bracket](docs/libertadores-2026.png)

Single matches with the default `"scores": "aggregate"`
([`knockout-8.json`](examples/knockout-8.json)) — one total per side, with shootouts in
parentheses. Sides that have not been resolved yet fall back to placeholders such as
"Winner SF2":

![Example Cup bracket](docs/knockout-8.png)

## Why JSON (and not a DSL or Graphviz `.dot`)

- **Native database support** and a universal parser.
- A bracket node can evolve from a **placeholder** (e.g. "winner of QF1") into a
  **reference to a real match entity** without changing the language: each leg can carry
  a `ref` to the real game, resolved dynamically by the host (see below).
- The bracket layout is **deterministic** (it is essentially a tree), so no general
  graph-layout engine is needed — coordinates are computed directly and the SVG is
  emitted as a string, with no heavy dependencies.

## The format

See [`spec/format.md`](spec/format.md) for the full specification and
[`spec/schema.json`](spec/schema.json) for the JSON Schema. Worked examples live in
[`examples/`](examples/).

Minimal example:

```json
{
  "tournament": "Copa Libertadores",
  "season": "2026",
  "format": "single-elimination",
  "rounds": [
    {
      "name": "Final",
      "matches": [
        {
          "id": "final",
          "home": { "team": "Flamengo" },
          "away": { "team": "Nacional" },
          "legs": [{ "home": 2, "away": 1 }]
        }
      ]
    }
  ]
}
```

## Quickstart

Requires Python ≥ 3.10. No runtime dependencies.

```bash
git clone https://github.com/anibalpacheco/playoff-diagrams.git
cd playoff-diagrams
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Render one of the bundled examples to an SVG file:

```bash
# via the installed command
playoff-diagrams examples/libertadores-2026.json -o libertadores.svg

# or via the module, writing to stdout
python -m playoff_diagrams examples/knockout-8.json > knockout.svg
```

Open the resulting `.svg` in a browser to view the bracket. To render your own cup,
point the command at any JSON file that follows [`spec/format.md`](spec/format.md).

Use it from Python:

```python
from playoff_diagrams import load_bracket, render_svg

svg = render_svg(load_bracket("examples/libertadores-2026.json"))
```

### Use it in another project (e.g. a Django app)

It is a standard pip-installable package with no runtime dependencies. To add it to
another project's virtual environment, install it straight from GitHub:

```bash
pip install git+https://github.com/anibalpacheco/playoff-diagrams.git
```

Pin a specific release or commit with `...playoff-diagrams.git@<tag-or-sha>`, or add
that same line to your `requirements.txt`. For a self-contained document, render it
straight away:

```python
from django.http import HttpResponse
from playoff_diagrams import parse_bracket, render_svg

def bracket_svg(request, championship):
    svg = render_svg(parse_bracket(championship.bracket_json))
    return HttpResponse(svg, content_type="image/svg+xml")
```

#### Injecting live data and dynamic title (`PlayoffDiagram`)

The renderer never computes results: the winner of a match is its explicit `winner`
field, and an advancing team is whatever `team` the document records on a `winner_of`
slot. To feed live data from your own database instead of (or on top of) the JSON,
subclass `PlayoffDiagram`. Whenever a leg carries a `ref`, `get_match(ref)` is called
with it; you return that one game as `[home_side, away_side]` (local first). The
tournament name and season can also be supplied dynamically:

```python
from playoff_diagrams import PlayoffDiagram

class ChampionshipDiagram(PlayoffDiagram):
    def __init__(self, championship):
        super().__init__(championship.bracket_json)
        self._championship = championship

    def get_match(self, ref):
        g = Match.objects.get(pk=ref)            # your own model
        return [
            {"team": g.home.name, "goals": g.home_goals, "pens": g.home_pens},
            {"team": g.away.name, "goals": g.away_goals, "pens": g.away_pens},
        ]

    def get_tournament(self):
        return self._championship.name

    def get_season(self):
        return str(self._championship.year)

def bracket_svg(request, championship):
    svg = ChampionshipDiagram(championship).render()
    return HttpResponse(svg, content_type="image/svg+xml")
```

`get_match` returns only what it has — any of `team`, `goals`, `pens` per side; a
returned `None` leaves that leg as the document defines it. Where a `winner_of` slot has
no team yet, the resolved name is filled in from the live game while the bracket
connector is kept.

The document's display preferences are available to the hooks as `self.render_config`,
so `get_match` can, for instance, read `self.render_config.max_label_chars` and return
already-shortened names. Long-named cups can raise that limit (it defaults to `22`) in
the document's `render` object.

### Running the tests

```bash
pip install -e ".[dev]"
pytest
```

The suite includes golden (snapshot) SVG tests under `tests/golden/`. When output
changes on purpose, regenerate them with `PD_REGEN=1 pytest tests/test_render.py` and
review the diff.

## Scope

**Single-elimination**, with single matches and two-legged ties decided by penalty
shootouts.

## Status

Working: the language spec, JSON Schema, Python renderer, CLI and tests are in place,
and the package is installable from GitHub.
