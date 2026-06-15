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
from datetime import datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

Id = Union[str, int]

# Datetime metadata in the document is assumed to be GMT in this format; anything else is
# shown verbatim (see render_dt).
_DT_INPUT = "%Y-%m-%d %H:%M"


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
    # Which tie side ("home"/"away") played this leg as local. The scores above are kept
    # in tie orientation, so this preserves the leg's own localía (its JSON ``team1``) for
    # renderings that show it per leg, e.g. the flat table. ``None`` when not known (a
    # result-only leg has no localía); the flat table then falls back to tie order.
    local: Optional[str] = None
    # Scheduling metadata, shown (not computed with) by the renderer. ``dt`` is a
    # datetime string, assumed GMT in the _DT_INPUT format; ``venue`` is free text.
    dt: Optional[str] = None
    venue: Optional[str] = None

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
class Match:  # pylint: disable=too-many-instance-attributes
    """One match node: two sides plus an optional, possibly multi-leg result.

    ``id`` is optional: a match nothing references (typically the final) may omit it, and
    then carries no metadata id label.
    """

    id: Optional[str]
    home: Slot
    away: Slot
    legs: list[Leg] = field(default_factory=list)
    winner: Optional[str] = None  # explicit, from the document: "home" | "away"
    # The document's "settle": false opts this match out of having its winner written
    # by KnockoutStage.apply_results. Display is unaffected.
    settle: bool = True
    # Scheduling metadata at match level — only consulted when the match has no legs to
    # carry it (see meta_text); otherwise the legs' own dt/venue are shown.
    dt: Optional[str] = None
    venue: Optional[str] = None


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

    ``show_metadata``: whether the per-match metadata line (id, then each leg's date and
    venue) is drawn. Defaults to ``True``; set it ``False`` to suppress the line.

    ``dt_format``: an optional ``strftime`` format for rendering each leg's ``dt``. When
    set, ``dt`` is parsed as GMT (``_DT_INPUT``) and reformatted (and converted to the
    render's timezone, if one is given); when unset — or when the value does not parse —
    the raw string is shown (see ``render_dt``).
    """

    max_label_chars: int = 22
    box_width: int = 190
    crest_shape: str = "square"
    show_metadata: bool = True
    dt_format: Optional[str] = None


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

    def matches_by_id(self) -> dict[Optional[str], Match]:
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


def leg_score_text(leg: Leg, side: str) -> str:
    """Display score for a single leg and side (the per-leg analogue of ``score_text``).

    Used by the flat table, which gives each leg its own row. Empty when the leg is not
    played; the leg's own shootout is appended in parentheses.
    """
    if not leg.played:
        return ""
    goals = str(leg.home if side == "home" else leg.away)
    if leg.pens is not None:
        goals += f" ({leg.pens.home if side == 'home' else leg.pens.away})"
    return goals


def render_dt(raw: str, dt_format: Optional[str], tz: Optional[str]) -> str:
    """Render a metadata datetime string, formatting/converting only when asked to.

    The document's ``dt`` is assumed to be GMT in the ``_DT_INPUT`` format. With no
    ``dt_format`` the raw string is returned unchanged (no parsing). With a ``dt_format``
    the value is parsed, optionally converted to ``tz`` (a zone name like
    ``"America/Montevideo"``), and reformatted. Anything that fails to parse — a value
    that violates the input format, or an unknown zone — falls back to the raw string.
    """
    if not dt_format:
        return raw
    try:
        moment = datetime.strptime(raw, _DT_INPUT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return raw
    if tz:
        try:
            moment = moment.astimezone(ZoneInfo(tz))
        except Exception:  # unknown zone: keep GMT rather than dropping the value
            pass
    return moment.strftime(dt_format)


def meta_parts(
    match: Match, dt_format: Optional[str] = None, tz: Optional[str] = None
) -> tuple[str, str]:
    """The metadata line split into ``(id_label, detail)`` for renderers that style them.

    ``id_label`` is the uppercased id (empty for an id-less match, e.g. the final).
    ``detail`` joins each leg's ``dt venue`` with " / " (the match-level ``dt``/``venue``
    are used when the match has no legs); either may be "". ``dt_format``/``tz`` drive
    datetime rendering (see ``render_dt``).
    """
    label = match.id.upper() if match.id else ""
    sources: list = list(match.legs) if match.legs else [match]
    parts: list[str] = []
    for src in sources:
        when = render_dt(src.dt, dt_format, tz) if src.dt else None
        piece = " ".join(p for p in (when, src.venue) if p)
        if piece:
            parts.append(piece)
    return label, " / ".join(parts)


def meta_text(
    match: Match, dt_format: Optional[str] = None, tz: Optional[str] = None
) -> str:
    """The match's metadata line as one string: the id, then each leg's ``dt``/``venue``.

    Starts with the uppercased id (mirroring the "Winner {id}" placeholder), so a match
    with no scheduling data still shows its id; a match with **no** id (the final) shows
    none. Returns "" when nothing is left to show. See :func:`meta_parts` for the split
    form used by renderers that bold the id.
    """
    label, detail = meta_parts(match, dt_format, tz)
    if label and detail:
        return f"{label} · {detail}"
    return label or detail


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
