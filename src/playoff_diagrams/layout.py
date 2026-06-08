"""Deterministic geometry for a single-elimination bracket.

Rounds become columns laid out left to right. Each match is a fixed-size box with a
home row and an away row. A match in a later round is centered vertically between the
matches it consumes (resolved through ``winner_of``); first-round matches are stacked
with a fixed gap. No external layout engine is involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Bracket, Match, Resolver, pens_of

# Geometry constants (SVG user units).
MARGIN_X = 20
TOP = 70  # room for the title and round headers
BOX_W = 190  # default box width; overridable per document via render.box_width
ROW_H = 24
BOX_H = 2 * ROW_H
H_GAP = 70
V_GAP = 22
MARGIN_BOTTOM = 24

ROW_PITCH = BOX_H + V_GAP


@dataclass
class SideView:
    label: str
    score: str  # "" when not played
    is_winner: bool


@dataclass
class PlacedMatch:
    match: Match
    x: float  # top-left
    y: float
    home: SideView
    away: SideView

    @property
    def cy(self) -> float:
        return self.y + BOX_H / 2


@dataclass
class Connector:
    points: list[tuple[float, float]]


@dataclass
class Header:
    name: str
    cx: float


@dataclass
class Layout:
    width: float
    height: float
    matches: list[PlacedMatch]
    connectors: list[Connector]
    headers: list[Header]
    box_width: float = BOX_W


def _score_text(match: Match, side: str) -> str:
    """Build the score string for one side: each played leg's goals, in order.

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


def _side_view(resolver: Resolver, match: Match, side: str) -> SideView:
    slot = match.home if side == "home" else match.away
    return SideView(
        label=resolver.label(slot),
        score=_score_text(match, side),
        is_winner=match.winner == side,  # explicit only; never computed
    )


def compute_layout(bracket: Bracket) -> Layout:
    resolver = Resolver(bracket)
    bw = bracket.render.box_width
    column_pitch = bw + H_GAP
    centers: dict[str, float] = {}
    placed: list[PlacedMatch] = []
    by_placed: dict[str, PlacedMatch] = {}

    for r_index, rnd in enumerate(bracket.rounds):
        x = MARGIN_X + r_index * column_pitch
        for m_index, match in enumerate(rnd.matches):
            parents = [
                centers[s.winner_of]
                for s in (match.home, match.away)
                if s.winner_of is not None and s.winner_of in centers
            ]
            if parents:
                cy = sum(parents) / len(parents)
            else:
                cy = TOP + BOX_H / 2 + m_index * ROW_PITCH
            centers[match.id] = cy
            pm = PlacedMatch(
                match=match,
                x=x,
                y=cy - BOX_H / 2,
                home=_side_view(resolver, match, "home"),
                away=_side_view(resolver, match, "away"),
            )
            placed.append(pm)
            by_placed[match.id] = pm

    connectors = _connectors(bracket, by_placed, bw)
    headers = [
        Header(name=rnd.name, cx=MARGIN_X + i * column_pitch + bw / 2)
        for i, rnd in enumerate(bracket.rounds)
    ]

    width = MARGIN_X * 2 + len(bracket.rounds) * bw + (len(bracket.rounds) - 1) * H_GAP
    height = max((pm.y + BOX_H for pm in placed), default=TOP) + MARGIN_BOTTOM
    return Layout(
        width=width,
        height=height,
        matches=placed,
        connectors=connectors,
        headers=headers,
        box_width=bw,
    )


def _connectors(
    bracket: Bracket, by_placed: dict[str, PlacedMatch], bw: float
) -> list[Connector]:
    connectors: list[Connector] = []
    for rnd in bracket.rounds:
        for match in rnd.matches:
            child = by_placed[match.id]
            for side, slot in (("home", match.home), ("away", match.away)):
                if slot.winner_of is None or slot.winner_of not in by_placed:
                    continue
                parent = by_placed[slot.winner_of]
                start = (parent.x + bw, parent.cy)
                conn_y = child.y + (ROW_H / 2 if side == "home" else ROW_H + ROW_H / 2)
                mid_x = (parent.x + bw + child.x) / 2
                connectors.append(
                    Connector(
                        points=[
                            start,
                            (mid_x, parent.cy),
                            (mid_x, conn_y),
                            (child.x, conn_y),
                        ]
                    )
                )
    return connectors
