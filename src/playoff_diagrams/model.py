"""Parsed, in-memory representation of a bracket document, plus display helpers.

The shapes here mirror the JSON language described in ``docs/format.md``. Keeping the
models as plain dataclasses avoids any third-party dependency.

The renderer is intentionally a *pure renderer*: it never computes who advances. The
winner of a match is whatever the document's explicit ``winner`` field says, and an
unresolved ``winner_of`` slot is drawn as a placeholder unless the document (or live
data injected through :class:`~playoff_diagrams.diagram.PlayoffDiagram`) already carries
a resolved team name on it. Filling brackets forward is the job of whatever maintains
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
    bracket connector while the name is shown instead of a placeholder.
    """

    team: Optional[str] = None
    team_id: Optional[Id] = None
    seed: Optional[int] = None
    winner_of: Optional[str] = None
    tbd: bool = False

    @property
    def kind(self) -> str:
        if self.team is not None:
            return "team"
        if self.winner_of is not None:
            return "winner_of"
        return "tbd"


@dataclass
class Match:
    """One bracket node: two sides plus an optional, possibly multi-leg result."""

    id: str
    home: Slot
    away: Slot
    legs: list[Leg] = field(default_factory=list)
    winner: Optional[str] = None  # explicit, from the document: "home" | "away"
    # The document's "settle": false opts this match out of having its winner written
    # by PlayoffDiagram.apply_results. Display is unaffected.
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
    """

    max_label_chars: int = 22
    box_width: int = 190


@dataclass
class Bracket:
    rounds: list[Round]
    tournament: str = ""
    season: Optional[str] = None
    render: RenderOptions = field(default_factory=RenderOptions)

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


class Resolver:
    """Turns a slot into the display label to draw.

    No computation happens here: a ``winner_of`` slot shows its resolved ``team`` if one
    has been set, otherwise a placeholder. The renderer never walks the bracket to work
    out who won.
    """

    def __init__(self, bracket: Optional[Bracket] = None) -> None:  # bracket unused
        pass

    def label(self, slot: Slot) -> str:
        if slot.team is not None:
            return slot.team
        if slot.winner_of is not None:
            return f"Winner {slot.winner_of.upper()}"
        return "TBD"
