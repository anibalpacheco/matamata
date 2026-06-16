# Knockout stage source format

This document specifies the JSON "language" used to describe a tournament knockout
stage. A document of this format is the single source of truth from which the
schedule is rendered (in SVG or HTML table format).

The canonical, machine-checkable definition is [`schema.json`](schema.json). This
prose document explains intent and the rules a renderer must implement.

## Top-level document

```jsonc
{
  "tournament": "Copa Libertadores", // optional, string (may be supplied dynamically)
  "season": "2026",                  // optional, string (may be supplied dynamically)
  "render": { "box_width": 240 },    // optional, display preferences (see below)
  "rounds": [ /* Round, ... */ ]      // required, ordered first round -> final
}
```

`rounds` are ordered from the earliest round to the final. The order is significant:
it determines the columns of the schedule, left to right.

`tournament` and `season` are optional in the document because a host system may want
to supply them dynamically at render time (e.g. from the championship entity) rather
than store them in the JSON. See "Host integration" below.

## Render options

The optional top-level `render` object lets the document declare how it should be
displayed, so the same renderer serves different presentation choices without code
changes.

```jsonc
{
  "max_label_chars": 22,        // optional, longest team label before it is truncated
  "box_width": 190,             // optional, width of every match box in SVG units
  "crest_shape": "square",      // optional, "square" (default) or "flag"
  "show_metadata": true,        // optional, draw the per-match metadata line (default true)
  "dt_format": "EEEE dd MMMM, HH:mm"  // optional, Babel/LDML pattern for each leg's dt
}
```

- `"max_label_chars"` (default `22`) — the maximum team-label width, in characters.
  Longer labels are truncated with an ellipsis. Cups with long team names can raise it;
  a host's `get_match` can also read it and return shorter names.
- `"box_width"` (default `190`) — the width of every match box. Widen it (instead of, or
  together with, lowering `max_label_chars`) to fit long names without truncation.
- `"crest_shape"` (default `"square"`) — the shape of each side's crest/flag image.
  `"square"` suits club crests; `"flag"` renders a rectangular (3:2) box with the image
  fitted inside without distortion and a thin border, so national flags look like flags
  instead of squashed squares. Only the *shape* is declared here — the image itself is
  still supplied by the host's `get_crest`, never by the document.
- `"show_metadata"` (default `true`) — whether the per-match metadata line (the id, then
  each leg's date and venue) is drawn. Set it `false` to suppress the line entirely.
- `"dt_format"` (default `"dd/MM HH:mm"`) — a [Babel/LDML](https://babel.pocoo.org/en/latest/dates.html#date-fields)
  pattern applied to each leg's `dt` (`EEEE` weekday, `MMMM` month, `dd` day, `HH:mm`
  time). `dt` is parsed as **GMT** in `%Y-%m-%d %H:%M`, converted to the render's timezone
  if one is given (see "Host integration"), and formatted by Babel in the render's language
  so weekday/month names follow the locale. The default omits the year (usually already in
  the title); a value that does not parse is shown unchanged.

Each side always shows the goals of every played leg in order, e.g. `2 0` for a tie or
`2` for a single match; a shootout is appended in parentheses on the relevant side, e.g.
`0 0 (4)`. The winning side is emphasized when the `winner` field says so.

## Round

```jsonc
{
  "name": "Quarterfinals",   // required, display label
  "matches": [ /* Match, ... */ ]  // required
}
```

## Match

A match is one node in the knockout stage: two sides plus an optional result. The two sides are
numbered — **`1` is the top side, `2` the bottom** — and every side field follows that
numbering. There are no `home`/`away` objects.

```jsonc
{
  "id": "sf1",            // optional, unique within the document (omit it on the final)
  "winnerof1": "qf1",     // optional, side 1 is the winner of another match (advancement link)
  "winnerof2": "qf2",     // optional, same for side 2
  "team1": "Flamengo",    // optional, a known/advancing team on side 1 (with id1)
  "team2": "River Plate", // optional, same for side 2
  "legs": [ /* Leg, ... */ ], // optional; absent => not played yet
  "winner": 1,            // optional; 1 (top) | 2 (bottom)
  "settle": false         // optional; only false is admitted (see "Applying results")
}
```

- `id` — identifier referenced by `winnerof1`/`winnerof2`, and shown (uppercased) as the
  first part of the match's [metadata line](#rendering-notes-non-normative). It is
  **optional**: a match that nothing references — typically the final, whose round title
  already names it — may omit it, and then shows no metadata id.
- `winnerof1`/`winnerof2` — explicit advancement links: each must reference the `id` of
  another match. References must not form a cycle. They draw the connector and, while
  unresolved, show a placeholder ("Winner QF1"). They declare a **preestablished**
  advancement path: in a round that is redrawn from the winners no such path exists,
  so omit the links — the sides render "TBD" with no connector — and, once the draw
  is made, write the drawn pairings as plain `team{n}` names, keeping the links (and
  their connectors, which could cross arbitrarily) out.
- `team1`/`team2` (optional `id1`/`id2`) — a side's known team: an entrant, or the team
  that advanced (written here by whatever maintains the JSON; the renderer never works
  it out). Legs may also name teams: they fill in whatever the match level leaves
  unset, and where both name a side the match-level name wins.
- A side with neither `team{n}` nor `winnerof{n}` renders as "TBD".
- `winner` — which side won, `1` or `2`. This is the **only** source of the winner: the
  renderer never computes it from the scores. Absent means undecided.
- `settle` — when present it must be `false`: it opts this match out of having its
  `winner` written by the result-application helper (see "Applying results" below).
  Display is unaffected.

## Leg

A single game within a match. Two-legged ties have two legs (and nothing caps the
count, so longer series are expressible). When a leg names its teams, they are numbered
like a match's sides but **game-locally**: **`1` = the game's local/home, `2` = the
visitor** — so the second leg of a tie, played at the other venue, lists the teams in
the opposite order.

```jsonc
// self-contained: the game lives in the document
{
  "team1": "River Plate", "goals1": 1,  // local team and its goals (id via id1)
  "team2": "Palmeiras",   "goals2": 1,  // visiting team and its goals
  "pen1": 4, "pen2": 2                  // optional, penalty shootout result
}

// host-resolved: a pointer to the real game, optionally with a baked result
{
  "ref": 84021                          // id of the real game in the host system
}

// result-only: no team names, so 1/2 are the *match's* sides (tie-oriented)
{
  "goals1": 2, "goals2": 0
}
```

- Every field is optional. An empty leg `{}` is scheduled but not played yet.
- A leg **without team names** has nothing to match against the tie, so its `1`/`2` are
  read as the match's sides: `goals1` belongs to the top side. This is the shape the
  result-application helper writes (see "Applying results").
- `ref` is a pointer to the real game in the host system's database: the leg's teams and
  scores are filled in dynamically at render time — see "Host integration". A `ref` may
  coexist with an inline result (a baked snapshot); when the host supplies live data it
  wins over the baked values.
- `dt` and `venue` are optional scheduling metadata for the leg, shown on the match's
  metadata line (see "Match metadata"). `dt` is a datetime string (assumed GMT, formatted
  per `render.dt_format`); `venue` is free text. Unlike the score/team fields they are not
  game-oriented — they describe the leg itself, so they are never flipped. A host's
  `get_match` may also supply them, and present values win over baked ones. When a match
  has **no legs**, a `dt`/`venue` written at *match* level is used as a fallback.
- The renderer reads the first named leg to place the two sides (its `team1` → the tie's
  top, `team2` → the tie's bottom) and orients later legs by matching team names.
- A match with no legs is "not played yet".

## Determining the winner

The winner of a match is exactly its `winner` field (`1` / `2`), or undecided if absent.
**The renderer computes no winner** — not from the aggregate, not from penalties, and
the away-goals rule does not exist here. Advancing teams and decided series are written
into the document by whatever updates it — by hand, by the host, or through the
result-application helper below.

## Host integration (non-normative)

A leg's `ref` lets a host system inject live data. When using the Python renderer's
`KnockoutStage` class, override `get_match(ref)` to return that one game as a flat dict
in the same shape as a self-contained leg — `team1`/`goals1`/`team2`/`goals2` (local
first), with optional `pen1`/`pen2`, `id1`/`id2` and the leg's `dt`/`venue`. Return only
what you have; the renderer fills the leg's scores, metadata and, where a side has no team
yet, its name — keeping any `winnerof` link, and letting present values win over baked
ones. `get_tournament()` and `get_season()` can likewise be supplied dynamically, and
`get_crest(team_id, team_name)` can resolve each side's crest/flag image from the side's
identity. The document itself never carries images: crests have no JSON surface, by
design.

The metadata datetimes are assumed to be **GMT**. The render entry points
(`render_svg`, `render_html`, `KnockoutStage.render`, and the CLI's `--timezone`) take an
optional `timezone` (a zone name like `"America/Montevideo"`) the datetimes are converted
to before being formatted with `render.dt_format`. They also take a `language` that Babel
uses to localize the weekday/month names in that pattern (e.g. `"es"` → `jueves`,
`septiembre`); the same `language` drives the generated-label translation hook
(`KnockoutStage.translate`), but the two are independent — only the argument is shared.

## Applying results (non-normative)

`KnockoutStage.apply_results(results, settle=True)` is the document-maintenance
helper: it writes played results onto the JSON in place, so a host updates the stored
document without touching its structure. `results` is one dict or a list of dicts, each
carrying the scores of one leg — `goals1`/`goals2`, optional `pen1`/`pen2`,
**tie-oriented** (`1` = the match's top side) — plus exactly one way to find that leg:

```jsonc
{ "ref": 84021, "goals1": 1, "goals2": 1, "pen1": 4, "pen2": 2 }  // the leg with this ref
{ "id": "sf1", "goals1": 2, "goals2": 0 }                          // match sf1, leg 1
{ "id": "sf1", "leg": 2, "goals1": 0, "goals2": 3 }                // match sf1, leg 2
```

`ref` and `id` are mutually exclusive and one is required; `leg` (1-based, default 1)
only combines with `id`, and missing legs are created on the way. Present keys overwrite
whatever the leg holds — there is no notion of "already played", so a live game can be
re-applied as it goes.

With `settle` (the default), every match a result touched is then *settled*: its winner
is recomputed from the data a render would show (aggregate over the played legs, then a
shootout on a tied aggregate), written as `winner`, removed when undecided, and the
advancing team's name/id is pushed into the match that consumes it via `winnerof`. A
match carrying `"settle": false` is never settled, whatever the call says.

## Rendering notes (non-normative)

- Layout is deterministic: rounds map to columns left-to-right; within the tree,
  a match in round *n+1* is drawn vertically centered between the two matches it
  consumes (resolved via `winnerof1`/`winnerof2`). Connectors exist only where a
  `winnerof` link does; a match with no links (a pairing pending a draw) is stacked
  from the top of its column like a first-round match.
- An unresolved side displays the team that advanced when known, otherwise the
  placeholder label (e.g. "Winner QF1") for a `winnerof` link, or "TBD".
- The winning side of a match is emphasized only when the `winner` field says so.
- **Match metadata.** Next to each match the renderer draws a line that starts with the
  match **id** (uppercased; a match with no scheduling data still shows its id, while a
  match with no `id` at all — e.g. the final — shows none) followed by each leg's `dt` and
  `venue` when present: `ID · dt venue` for one leg, `ID · dt venue / dt venue` for two.
  In the SVG it sits above the box, or below it when the box's outgoing connector bends up
  (so the line stays clear of the connector). Suppress the whole line with
  `render.show_metadata: false`. (SVG and the stacked HTML table draw the whole line; the
  flat table, having one row per leg, draws a full-width metadata row above each leg with
  the id and *that leg's* own `dt`/`venue` — see below.)
- Besides the SVG diagram there is an HTML table rendering for small screens: rounds
  stack vertically and no connectors are drawn — advancement is read top-down. The
  **stacked** layout draws each match as a two-row box (aggregate scores); the **flat**
  layout is one grid where a two-legged tie becomes **two rows**, one per leg, each
  carrying that leg's single score in its own bordered box (like the SVG/stacked boxes)
  and preceded by a full-width metadata row (the id plus that leg's date/venue). Each flat
  row honors that leg's
  **localía**: the leg's local side (its `team1`) sits in the home (left) column, so the
  second leg's row is flipped relative to the first. Both renderings show the same
  resolved data.
