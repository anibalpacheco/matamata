# Playoff bracket source format

This document specifies the JSON "language" used to describe a football playoff
bracket. A document of this format is the single source of truth from which an SVG
diagram is rendered.

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
it determines the columns of the bracket, left to right.

`tournament` and `season` are optional in the document because a host system may want
to supply them dynamically at render time (e.g. from the championship entity) rather
than store them in the JSON. See "Host integration" below.

## Render options

The optional top-level `render` object lets the document declare how it should be
displayed, so the same renderer serves different presentation choices without code
changes.

```jsonc
{
  "max_label_chars": 22,  // optional, longest team label before it is truncated
  "box_width": 190        // optional, width of every match box in SVG units
}
```

- `"max_label_chars"` (default `22`) — the maximum team-label width, in characters.
  Longer labels are truncated with an ellipsis. Cups with long team names can raise it;
  a host's `get_match` can also read it and return shorter names.
- `"box_width"` (default `190`) — the width of every match box. Widen it (instead of, or
  together with, lowering `max_label_chars`) to fit long names without truncation.

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

A match is one bracket node: two sides plus an optional result. The two sides are
numbered — **`1` is the top side, `2` the bottom** — and every side field follows that
numbering. There are no `home`/`away` objects.

```jsonc
{
  "id": "sf1",            // required, unique within the document
  "winnerof1": "qf1",     // optional, side 1 is the winner of another match (bracket link)
  "winnerof2": "qf2",     // optional, same for side 2
  "team1": "Flamengo",    // optional, a known/advancing team on side 1 (with seed1/id1)
  "team2": "River Plate", // optional, same for side 2
  "legs": [ /* Leg, ... */ ], // optional; absent => not played yet
  "winner": 1             // optional; 1 (top) | 2 (bottom)
}
```

- `id` — internal identifier, referenced by `winnerof1`/`winnerof2`. Not a display value.
- `winnerof1`/`winnerof2` — explicit bracket connections: each must reference the `id` of
  another match. References must not form a cycle. They draw the connector and, while
  unresolved, show a placeholder ("Winner QF1").
- `team1`/`team2` (optional `seed1`/`seed2`, `id1`/`id2`) — a side's known team: a seeded
  entrant, or the team that advanced (written here by whatever maintains the JSON; the
  renderer never works it out). **When the match has legs the team names come from the
  legs, so `team1`/`team2` (and `seed`/`id`) must be omitted** — setting them is rejected.
- A side with neither `team{n}` nor `winnerof{n}` renders as "TBD".
- `winner` — which side won, `1` or `2`. This is the **only** source of the winner: the
  renderer never computes it from the scores. Absent means undecided.

## Leg

A single game within a match. Two-legged ties have two legs. Like a match's sides, a
leg's two teams are numbered **`1` = the game's local/home, `2` = the visitor** — so the
second leg of a tie, played at the other venue, lists the teams in the opposite order.
A leg comes in exactly one of two shapes and never mixes them:

```jsonc
// self-contained: the game lives in the document
{
  "team1": "River Plate", "goals1": 1,  // local team and its goals (seed/id via id1)
  "team2": "Palmeiras",   "goals2": 1,  // visiting team and its goals
  "pen1": 4, "pen2": 2                  // optional, penalty shootout result
}

// host-resolved: only a pointer to the real game
{
  "ref": 84021                          // id of the real game in the host system
}
```

- A self-contained leg requires `team1`, `goals1`, `team2`, `goals2`; `pen1`/`pen2` and
  `id1`/`id2` are optional.
- `ref` is a pointer to the real game in the host system's database. A leg with a `ref`
  has its teams and scores filled in dynamically at render time — see "Host integration".
  Because that data comes from the host, a `ref` leg must **not** also carry any
  `team`/`goals`/`pen`; combining them is rejected.
- The renderer reads the first leg to place the two sides (its `team1` → the tie's top,
  `team2` → the tie's bottom) and orients later legs by matching team names.
- A match with no legs is "not played yet".

## Determining the winner

The winner of a match is exactly its `winner` field (`1` / `2`), or undecided if absent.
**No winner is computed** — not from the aggregate, not from penalties, and the
away-goals rule does not exist here. Advancing teams and decided series are written into
the document by whatever updates it.

## Host integration (non-normative)

A leg's `ref` lets a host system inject live data. When using the Python renderer's
`PlayoffDiagram` class, override `get_match(ref)` to return that one game as a flat dict
in the same shape as a self-contained leg — `team1`/`goals1`/`team2`/`goals2` (local
first), with optional `pen1`/`pen2` and `id1`/`id2`. Return only what you have; the
renderer fills the leg's scores and, where a side has no team yet, its name — keeping any
`winnerof` link. `get_tournament()` and `get_season()` can likewise be supplied
dynamically.

## Rendering notes (non-normative)

- Layout is deterministic: rounds map to columns left-to-right; within the bracket,
  a match in round *n+1* is drawn vertically centered between the two matches it
  consumes (resolved via `winnerof1`/`winnerof2`).
- An unresolved side displays the team that advanced when known, otherwise the
  placeholder label (e.g. "Winner QF1") for a `winnerof` link, or "TBD".
- The winning side of a match is emphasized only when the `winner` field says so.
