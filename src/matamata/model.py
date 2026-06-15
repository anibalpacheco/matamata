"""Parsed, in-memory representation of a knockout stage document, plus display helpers.

The shapes here mirror the JSON language described in ``docs/format.md``. Keeping the
models as plain dataclasses avoids any third-party dependency.

The renderer is intentionally a *pure renderer*: it never computes who advances. The
winner of a match is whatever the document's explicit ``winner`` field says, and an
unresolved ``winner_of`` slot is drawn as a placeholder unless the document (or live
data injected through :class:`~matamata.diagram.KnockoutStage`) already carries
a resolved team name on it. Filling the knockout stage forward is the job of whatever maintains
the JSON, not of this library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

Id = Union[str, int]


@dataclass
class Pens:
    """Penalty shootout result for a leg."""

    home: int
    away: int


@dataclass
class Leg:
    """A single played game within a match.

    ``home`` and ``away`` always refer to the match's home/away sides, regardless of
    which venue the leg was played at. A leg may be self-contained (``home``/``away``,
    optional ``pens``), host-resolved (a ``ref``, a pointer to the real game whose scores
    and teams are filled in at render time), or both — a ``ref`` plus a baked result,
    where live host data wins over the baked values. ``None`` means "not played / not
    known yet".
    """

    home: Optional[int] = None
    away: Optional[int] = None
    pens: Optional[Pens] = None
    ref: Optional[Id] = None  # id of the real game in the host system

    @property
    def played(self) -> bool:
        return self.home is not None and self.away is not None


@dataclass
class Slot:
    """One side of a match.

    A slot is a concrete ``team``, a ``winner_of`` link, or ``tbd``. A ``winner_of``
    slot may *also* carry a ``team`` once that team is known: the link still drives the
    advancement connector while the name is shown instead of a placeholder.
    """

    team: Optional[str] = None
    team_id: Optional[Id] = None
    winner_of: Optional[str] = None
    tbd: bool = False
    # Image source for the side's crest/flag. Filled by the KnockoutStage path
    # (the get_crest hook) — never parsed from the document, which has no crest
    # surface by design.
    crest: Optional[str] = None

    @property
    def kind(self) -> str:
        if self.team is not None:
            return "team"
        if self.winner_of is not None:
            return "winner_of"
        return "tbd"


@dataclass
class Match:
    """One match node: two sides plus an optional, possibly multi-leg result."""

    id: str
    home: Slot
    away: Slot
    legs: list[Leg] = field(default_factory=list)
    winner: Optional[str] = None  # explicit, from the document: "home" | "away"
    # The document's "settle": false opts this match out of having its winner written
    # by KnockoutStage.apply_results. Display is unaffected.
    settle: bool = True


@dataclass
class Round:
    name: str
    matches: list[Match]


@dataclass
class RenderOptions:
    """Document-level display preferences.

    ``max_label_chars``: the longest team label drawn before it is truncated with an
    ellipsis. It is the maximum label *width*, in characters, so longer-named cups can
    raise it (or a host's ``get_match`` can read it and return shorter names).

    ``box_width``: the width of every match box, in SVG units. Widen it (instead of, or
    together with, raising ``max_label_chars``) to fit long names without truncation.

    ``crest_shape``: how each side's crest/flag image is shaped. ``"square"`` (the
    default) renders a square emblem, right for club crests; ``"flag"`` renders a
    rectangular box (3:2) with the image fitted inside without distortion and a thin
    border, so national flags look like flags instead of squashed squares. Only the
    *shape* is a document preference — the image itself is still host-only (``get_crest``).
    """

    max_label_chars: int = 22
    box_width: int = 190
    crest_shape: str = "square"


@dataclass
class Labels:
    """Text for the labels the renderer *generates* (not the team/round names, which
    come from the document). Supplied through ``KnockoutStage.get_labels`` for i18n —
    host-only, with no JSON surface, so the defaults are English and a document rendered
    without the class (CLI, ``render_svg``) stays in English.

    ``winner``: the placeholder for an unresolved ``winnerof`` side; ``{id}`` is replaced
    with the referenced match id (uppercased). ``tbd``: the placeholder for a side with
    neither a team nor an advancement link.
    """

    winner: str = "Winner {id}"
    tbd: str = "TBD"


@dataclass
class Stage:
    rounds: list[Round]
    tournament: str = ""
    season: Optional[str] = None
    render: RenderOptions = field(default_factory=RenderOptions)
    labels: Labels = field(default_factory=Labels)

    def matches_by_id(self) -> dict[str, Match]:
        return {m.id: m for r in self.rounds for m in r.matches}


def aggregate(match: Match) -> Optional[tuple[int, int]]:
    """Return (home_total, away_total) across played legs, or None if not played.

    This is presentation arithmetic for the score column; it does not decide a winner.
    """
    played = [leg for leg in match.legs if leg.played]
    if not played:
        return None
    home = sum(leg.home for leg in played)  # type: ignore[misc]
    away = sum(leg.away for leg in played)  # type: ignore[misc]
    return home, away


def pens_of(match: Match) -> Optional[Pens]:
    """Return the penalty shootout to display, if any leg carries one."""
    for leg in reversed(match.legs):
        if leg.pens is not None:
            return leg.pens
    return None


def score_text(match: Match, side: str) -> str:
    """Build the display score string for one side: each played leg's goals, in order.

    A single-leg match shows one number; a two-legged tie shows both, e.g. ``2 0``. A
    shootout is appended in parentheses. This only formats the goals that are present; it
    does not decide a winner.
    """
    played = [leg for leg in match.legs if leg.played]
    if not played:
        return ""
    goals = " ".join(str(leg.home if side == "home" else leg.away) for leg in played)
    pens = pens_of(match)
    pen_suffix = ""
    if pens is not None:
        pen_suffix = f" ({pens.home if side == 'home' else pens.away})"
    return goals + pen_suffix


class Resolver:
    """Turns a slot into the display label to draw.

    No computation happens here: a ``winner_of`` slot shows its resolved ``team`` if one
    has been set, otherwise a placeholder. The renderer never walks the tree to work
    out who won.
    """

    def __init__(self, stage: Optional[Stage] = None) -> None:
        self._labels = stage.labels if stage is not None else Labels()

    def label(self, slot: Slot) -> str:
        if slot.team is not None:
            return slot.team
        if slot.winner_of is not None:
            return self._labels.winner.replace("{id}", slot.winner_of.upper())
        return self._labels.tbd
