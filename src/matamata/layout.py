"""Deterministic geometry for a single-elimination knockout stage.

Rounds become columns laid out left to right. Each match is a fixed-size box with a
home row and an away row. A match in a later round is centered vertically between the
matches it consumes (resolved through ``winner_of``); first-round matches are stacked
with a fixed gap. A third-place match (fed by ``loser_of``) is off the tree: it hangs
below the whole bracket with no connector. No external layout engine is involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .model import Match, Resolver, Stage, meta_text, score_text

# Geometry constants (SVG user units).
MARGIN_X = 20
TOP = 70  # room for the title and round headers
BOX_W = 190  # default box width; overridable per document via render.box_width
ROW_H = 24
BOX_H = 2 * ROW_H
H_GAP = 70
V_GAP = 22
MARGIN_BOTTOM = 24
META_H = 34  # vertical room reserved between stacked boxes for their metadata lines
META_TOP = 30  # room above the first box of a column for its single metadata caption
META_CHAR_W = 6.0  # rough px per glyph of the 11px metadata font, to size the canvas
HEADER_Y = 68  # baseline of a column header at the top of the bracket
HEADER_BAND = 30  # vertical room a below-the-bracket round header takes (third place)

ROW_PITCH = BOX_H + V_GAP


@dataclass
class SideView:
    label: str
    score: str  # "" when not played
    is_winner: bool
    crest: Optional[str] = None  # image source, only ever set via KnockoutStage


@dataclass
class PlacedMatch:
    match: Match
    x: float  # top-left
    y: float
    home: SideView
    away: SideView
    # Where the metadata line is drawn: below the box when its outgoing connector bends
    # up (the room above is taken by the connector), above it otherwise — including when
    # there is no outgoing connector. Set while wiring connectors.
    meta_below: bool = False

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
    # Baseline y of the header text. Column headers sit at the top (HEADER_Y); a
    # below-the-bracket round (third place) places its own header at its section's y.
    cy: float = HEADER_Y


@dataclass
class Layout:
    width: float
    height: float
    matches: list[PlacedMatch]
    connectors: list[Connector]
    headers: list[Header]
    box_width: float = BOX_W


def _is_satellite(match: Match) -> bool:
    """Whether a match hangs off the bracket rather than belonging to the advancement tree.

    A match fed by ``loser_of`` (a third-place match) consumes the losers of earlier
    matches, so it is not part of the winners' tree: it is placed below everything and
    draws no connector.
    """
    return any(s.loser_of is not None for s in (match.home, match.away))


def _is_below_round(rnd) -> bool:
    """Whether a whole round renders below the bracket instead of as a left-right column.

    A round every match of which is a satellite (a third-place round, fed by ``loser_of``)
    comes *after* the final and is drawn beneath it, keeping its own header — so the
    round name needs no special-casing.
    """
    return bool(rnd.matches) and all(_is_satellite(m) for m in rnd.matches)


def _side_view(resolver: Resolver, match: Match, side: str) -> SideView:
    slot = match.home if side == "home" else match.away
    return SideView(
        label=resolver.label(slot),
        score=score_text(match, side),
        is_winner=match.winner == side,  # explicit only; never computed
        crest=slot.crest,
    )


def compute_layout(
    stage: Stage, timezone: Optional[str] = None, language: Optional[str] = None
) -> Layout:
    resolver = Resolver(stage)
    bw = stage.render.box_width
    column_pitch = bw + H_GAP
    # The metadata line sits above each box. META_H is the room reserved *between* stacked
    # boxes (so a box's below-metadata and the next box's above-caption never collide);
    # META_TOP is the smaller room above the first box of a column, which only ever holds a
    # single caption. Both are zero when metadata is suppressed.
    meta_h = META_H if stage.render.show_metadata else 0
    meta_top = META_TOP if stage.render.show_metadata else 0
    row_pitch = ROW_PITCH + meta_h
    # Distance from a header's baseline to the top of the box that follows it, kept equal
    # for the top columns and the below-the-bracket rounds so the header-to-metadata gap
    # matches everywhere.
    header_to_box = TOP + meta_top - HEADER_Y
    # Keys are match ids; an id-less match (e.g. the final) keys on None — harmless since
    # only a referenced match is ever looked up, and such matches always carry an id.
    centers: dict[Optional[str], float] = {}
    placed: list[PlacedMatch] = []
    by_placed: dict[Optional[str], PlacedMatch] = {}

    # Bracket rounds are columns left to right; rounds after the final (third place, all
    # satellites) hang below it. Splitting here keeps the round-name header generic — the
    # below round draws its own, so the final needs no special-casing.
    bracket_rounds = [r for r in stage.rounds if not _is_below_round(r)]
    below_rounds = [r for r in stage.rounds if _is_below_round(r)]

    headers: list[Header] = []
    for r_index, rnd in enumerate(bracket_rounds):
        x = MARGIN_X + r_index * column_pitch
        headers.append(Header(name=rnd.name, cx=x + bw / 2))
        for m_index, match in enumerate(rnd.matches):
            parents = [
                centers[s.winner_of]
                for s in (match.home, match.away)
                if s.winner_of is not None and s.winner_of in centers
            ]
            if parents:
                cy = sum(parents) / len(parents)
            else:
                cy = TOP + meta_top + BOX_H / 2 + m_index * row_pitch
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

    # Below the bracket, in the final's column: each below round's header, then its
    # match(es), with no connector. Reserve a band for the lowest bracket box's possible
    # below-box metadata (meta_below is only set later, in _connectors).
    if below_rounds:
        below_x = MARGIN_X + max(len(bracket_rounds) - 1, 0) * column_pitch
        cx = below_x + bw / 2
        cursor = max((pm.y + BOX_H for pm in placed), default=TOP) + meta_h + V_GAP
        for rnd in below_rounds:
            header_cy = cursor + HEADER_BAND
            headers.append(Header(name=rnd.name, cx=cx, cy=header_cy))
            box_y = header_cy + header_to_box
            for match in rnd.matches:
                cy = box_y + BOX_H / 2
                centers[match.id] = cy
                pm = PlacedMatch(
                    match=match,
                    x=below_x,
                    y=box_y,
                    home=_side_view(resolver, match, "home"),
                    away=_side_view(resolver, match, "away"),
                )
                placed.append(pm)
                by_placed[match.id] = pm
                box_y = cy + BOX_H / 2 + V_GAP + meta_top
            cursor = box_y

    connectors = _connectors(placed, by_placed, bw)

    n_cols = len(bracket_rounds)
    width: float = MARGIN_X * 2 + n_cols * bw + max(n_cols - 1, 0) * H_GAP
    # The metadata line is drawn left-anchored at its box's x and is not wrapped, so a long
    # one (especially the rightmost column's, e.g. the final's) can run past the canvas and
    # clip. Estimate each line's width by character count and widen the canvas to fit it.
    if stage.render.show_metadata:
        fmt = stage.render.dt_format
        rightmost = max(
            (
                pm.x + len(meta_text(pm.match, fmt, timezone, language)) * META_CHAR_W
                for pm in placed
            ),
            default=0.0,
        )
        width = max(width, rightmost + MARGIN_X)
    # A box whose metadata sits below it extends META_H further down.
    height = (
        max(
            (pm.y + BOX_H + (meta_h if pm.meta_below else 0) for pm in placed),
            default=TOP,
        )
        + MARGIN_BOTTOM
    )
    return Layout(
        width=width,
        height=height,
        matches=placed,
        connectors=connectors,
        headers=headers,
        box_width=bw,
    )


def _connectors(
    placed: list[PlacedMatch], by_placed: dict[Optional[str], PlacedMatch], bw: float
) -> list[Connector]:
    connectors: list[Connector] = []
    # Iterate placed matches (not ids): two id-less matches — the final and a third-place
    # match — share the ``None`` key in by_placed, so the child must be the placed match
    # itself. Parents are always looked up by a real ``winner_of`` id, never None.
    for child in placed:
        match = child.match
        for side, slot in (("home", match.home), ("away", match.away)):
            if slot.winner_of is None or slot.winner_of not in by_placed:
                continue
            parent = by_placed[slot.winner_of]
            start = (parent.x + bw, parent.cy)
            conn_y = child.y + (ROW_H / 2 if side == "home" else ROW_H + ROW_H / 2)
            # This connector leaves the parent toward its child: bending up means the
            # space above the parent is taken, so its metadata goes below.
            parent.meta_below = conn_y < parent.cy
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
