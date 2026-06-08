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
shown, shootouts appear in parentheses, and the winner is emphasized. Unresolved sides
fall back to placeholders such as "Winner SF2":

![Copa Libertadores 2026 bracket](docs/libertadores-2026.png)

Single matches with the default `"scores": "aggregate"`
([`knockout-8.json`](examples/knockout-8.json)) — one total per side, with shootouts in
parentheses:

![Example Cup bracket](docs/knockout-8.png)

## Why JSON (and not a DSL or Graphviz `.dot`)

- **Native database support** and a universal parser.
- A bracket node can evolve from a **placeholder** (e.g. "winner of QF1") into a
  **reference to a real match entity** (`ref`) without changing the language.
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

### Running the tests

```bash
pip install -e ".[dev]"
pytest
```

The suite includes golden (snapshot) SVG tests under `tests/golden/`. When output
changes on purpose, regenerate them with `PD_REGEN=1 pytest tests/test_render.py` and
review the diff.

## Scope

MVP: **single-elimination**, with single matches and two-legged ties decided by
penalty shootouts. Group stages, double elimination and the away-goals rule are out of
scope for now.

## Status

Early. The language spec and examples exist; the Python renderer is in progress.
