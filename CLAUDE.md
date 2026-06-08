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
- **Flat 1/2 sides.** A match has no `home`/`away` objects: its two sides are numbered
  (`1` = top, `2` = bottom) and every side field follows the numbering — `team1`/`team2`,
  `seed1`/`seed2`, `id1`/`id2`, the bracket links `winnerof1`/`winnerof2`, and `winner`
  is `1` or `2`. Legs use the same scheme (`team1`/`goals1`/`team2`/`goals2`, plus
  `pen1`/`pen2`), with `1` = that game's local. Internally this still parses into two
  `Slot`s (`Match.home`/`away`, winner `"home"`/`"away"`), so `layout.py`/`render.py` are
  unchanged — the flat form is purely the JSON surface, mapped in `parse.py`.
- **Bracket connections are explicit** via `winnerof1`/`winnerof2`, not implicit by
  position.
- **Layout is deterministic** — geometry of the bracket tree is computed in code.
  No external layout engine (no Graphviz), no heavy dependencies. SVG is emitted
  directly as a string.
- **The renderer is pure: it computes nothing about the tournament.** The winner of a
  match is exactly its explicit `winner` field; an unresolved `winnerof{n}` is a
  placeholder unless the side already carries a resolved `team{n}` (or one filled from the
  legs). Deciding ties and advancing teams is the job of whatever maintains the JSON, not
  the renderer. No away-goals rule.
- **Host integration via `PlayoffDiagram` (`diagram.py`).** Each `leg` may carry a
  `ref` (id of the real game). Subclass `PlayoffDiagram`, override `get_match(ref)`
  (returns a flat game dict `team1`/`goals1`/`team2`/`goals2`, local first, with optional
  `pen1`/`pen2`/`id1`/`id2` — the same shape as an inline leg), and optionally
  `get_tournament()` / `get_season()`, then `MyDiagram(document).render()`. The base
  class needs no host and renders a self-contained document unchanged. `tournament`/
  `season` are optional in the JSON so they can be supplied this way.
- **Display preferences live in the document**, under a top-level `render` object
  (e.g. `{"max_label_chars": 22, "box_width": 240}`), so presentation changes need no
  code change. Add new presentation knobs there. (Scores are always shown per played leg
  — one figure for a single match, both for a tie — so there is no scores mode.)
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
examples/libertadores_host.py  # demo PlayoffDiagram subclass: get_match reads
                  #   example_data.json (a ref->game lookup) for the host-resolved tie
examples/example_data.json     # the host lookup table, NOT a bracket document
docs/*.png        # README preview images (committed; see below)
```

`libertadores-2026.json` is **host-resolved**: its first tie's legs carry only a `ref`,
so its teams and scores come from `get_match`. It is rendered through
`examples/libertadores_host.py`, not the base loader. A leg uses **either** a `ref`
**or** an inline game (`team1`/`goals1`/`team2`/`goals2`), never both; likewise a match
with legs takes its team names from the legs, so it must not set `team1`/`team2` (only the
`winnerof1`/`winnerof2` wiring) — the parser and schema reject the mix.

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
   The host-resolved `libertadores-2026.json` can't go through the CLI; render it via its
   host instead: `PYTHONPATH=src python examples/libertadores_host.py > /tmp/x.svg`.

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

Third-place playoff (`loserof1`/`loserof2` mirroring `winnerof1`/`winnerof2`), team
crests/logos.

## Conventions

- The codebase, identifiers, comments, docs and commit messages are **all in English**.
- Keep dependencies minimal; prefer the standard library.
