# CLAUDE.md

Guidance for working in this repository.

## What this project is

A small library that renders a **football (soccer) playoff bracket** as an **SVG**,
on the fly, from a **JSON source document**.

The motivating use case: on a results website, the bracket source text lives in a
field of the *championship* entity in the database. When results are updated, only
that JSON field changes — never the code, and no per-cup HTML templates are
maintained. The renderer turns the JSON into an SVG deterministically.

## Core decisions (already made — do not relitigate without reason)

- **Source format: JSON** (e.g. Postgres `JSONB`). Chosen over a custom DSL and over
  Graphviz `.dot` because of native database support and because a bracket node can
  evolve from a *placeholder* into a *reference to a business match entity* without
  changing the language. See `spec/format.md`.
- **Implementation language: Python.**
- **Bracket connections are explicit** via `winner_of`, not implicit by position.
- **Layout is deterministic** — geometry of the bracket tree is computed in code.
  No external layout engine (no Graphviz), no heavy dependencies. SVG is emitted
  directly as a string.
- **The renderer is pure: it computes nothing about the tournament.** The winner of a
  match is exactly its explicit `winner` field; an unresolved `winner_of` is a
  placeholder unless the slot already carries a resolved `team`. Deciding ties and
  advancing teams is the job of whatever maintains the JSON, not the renderer. No
  away-goals rule.
- **Host integration via `PlayoffDiagram` (`diagram.py`).** Each `leg` may carry a
  `ref` (id of the real game). Subclass `PlayoffDiagram`, override `get_match(ref)`
  (returns `[home_side, away_side]`, local first; each side may have `team`/`goals`/
  `pens`), and optionally `get_tournament()` / `get_season()`, then
  `MyDiagram(document).render()`. The base class needs no host and renders a
  self-contained document unchanged. `tournament`/`season` are optional in the JSON so
  they can be supplied this way.
- **Display preferences live in the document**, under a top-level `render` object
  (e.g. `{"scores": "aggregate" | "legs"}`), so presentation changes need no code
  change. Add new presentation knobs there.
- **Key naming: `snake_case`** in the JSON, for affinity with the Python backend.
- **Scope: single-elimination**, supporting single matches and two-legged ties
  with penalty shootouts.

## Language / spec

The authoritative description of the JSON "language" is **`spec/format.md`**, with a
machine-checkable **`spec/schema.json`** (JSON Schema) and worked examples under
**`examples/`**. If you change the language, update all three together.

## Package layout (implemented)

```
src/playoff_diagrams/
  __init__.py   # public API: PlayoffDiagram, load_bracket, parse_bracket, render_svg, models
  __main__.py   # CLI: `playoff-diagrams in.json -o out.svg` / `python -m playoff_diagrams`
  model.py      # data models + display helpers (aggregate, pens_of, Resolver)
  parse.py      # JSON -> validated model; validate_document() needs `jsonschema`
  layout.py     # deterministic bracket geometry (columns, centering, connectors)
  render.py     # model -> SVG string
  diagram.py    # PlayoffDiagram: subclassable host hooks (get_match/get_tournament/get_season)
tests/
  test_model.py   # result-logic and parsing unit tests
  test_render.py  # golden/snapshot SVG tests + well-formed-XML checks
  golden/*.svg    # versioned reference SVGs
examples/*.json   # worked brackets (also rendered into docs/)
docs/*.png        # README preview images (committed; see below)
```

The CLI is wired as a `[project.scripts]` entry point, so `pip install` exposes the
`playoff-diagrams` command.

## Testing

The only executable code is the renderer plus **diagram-generation tests**, done as
**golden (snapshot) tests**: generate the SVG for each example and compare against a
versioned reference SVG. This catches visual regressions without a browser.

Run with `pytest`. When SVG output legitimately changes, regenerate goldens with
`PD_REGEN=1 pytest tests/test_render.py` and review the diff before committing.

## Maintaining examples and the README images

When you change an example JSON (teams, scores) or anything that affects rendering,
keep three things in sync:

1. The example under `examples/`.
2. Its golden under `tests/golden/` — `PD_REGEN=1 pytest tests/test_render.py`.
3. Its README preview under `docs/` — regenerate the PNG (the README embeds these):
   ```bash
   PYTHONPATH=src python -m playoff_diagrams examples/<name>.json -o /tmp/x.svg
   rsvg-convert -z 2 /tmp/x.svg -o docs/<name>.png
   ```
   `rsvg-convert` (librsvg) is the SVG→PNG converter available on this machine
   (`inkscape` and ImageMagick `magick`/`convert` are also present).

`.gitignore` ignores stray rendered `*.svg`/`*.png` but keeps `docs/*.png` and
`tests/golden/*.svg`. A gitignored `/.local/` directory holds personal scratch notes
(never committed).

## Project state (published)

- Public repo: **https://github.com/anibalpacheco/playoff-diagrams** (MIT).
- GitHub CLI is authenticated as `anibalpacheco` over SSH; pushes and `gh` work here.
- CI (`.github/workflows/ci.yml`) runs `pytest` on push/PR across Python 3.10–3.13.
- The MVP is complete and working: spec, schema, renderer, CLI, tests, README with
  preview images. Installable into other projects via
  `pip install git+https://github.com/anibalpacheco/playoff-diagrams.git`.

## Possible next steps

Third-place playoff (a `loser_of` slot mirroring `winner_of`), team crests/logos.

## Conventions

- The codebase, identifiers, comments, docs and commit messages are **all in English**.
- Keep dependencies minimal; prefer the standard library.
