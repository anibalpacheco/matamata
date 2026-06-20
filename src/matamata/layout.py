"""Deterministic geometry for a single-elimination knockout stage.

Rounds become columns. Each match is a fixed-size box with a home row and an away row. A
match in a later round is centered vertically between the matches it consumes (resolved
through ``winner_of``); first-round matches are stacked with a fixed gap. A third-place
match (fed by ``loser_of``) is off the tree: it hangs below the whole bracket with no
connector. No external layout engine is involved.

Two arrangements (``render.layout``): ``"symmetric"`` (default) is the FIFA-style mirrored
bracket — every round before the final split by document order so its two halves expand
outward, the semifinals meeting in the centre, with the final lifted above them and a
third-place round dropped below (see ``_place_symmetric``); ``"linear"`` flows the columns
left to right with the final in the last column.
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
# Box-internal horizontal metrics, mirroring how render.py draws a box — used only to size
# an "auto" box_width to its widest content. GLYPH_W is a deliberately generous px-per-glyph
# for the proportional 13px label/score font, so an auto box never clips its own text.
GLYPH_W = 7.0
LABEL_PAD = 10  # left inset of the label (render._LABEL_PAD)
SCORE_PAD = 8  # right inset of the score / the box's right margin (render._SCORE_PAD)
CREST_GAP = 6  # gap between a crest and the label (render._CREST_GAP)
CREST_SIZE = 16  # square crest side (render._CREST_SIZE)
FLAG_W = 24  # flag box width, 3:2 (render._FLAG_W)
MIN_INNER_GAP = 12  # least space kept between a label and the score column
AUTO_MIN_BOX_W = 120  # floor for an auto box, so all-short-name stages are not too thin
HEADER_Y = 68  # baseline of a column header at the top of the bracket
HEADER_BAND = 30  # vertical room a below-the-bracket round header takes (third place)
CENTRE_GAP = BOX_H + V_GAP  # gap above the semis the centred final is lifted into

ROW_PITCH = BOX_H + V_GAP


@dataclass
class SideView:
    label: str
    score: str  # "" when not played
    is_winner: bool
    crest: Optional[str] = None  # image source, only ever set via KnockoutStage


@dataclass
class PlacedMatch:  # pylint: disable=too-many-instance-attributes
    match: Match
    x: float  # top-left
    y: float
    home: SideView
    away: SideView
    # Where the metadata line is drawn: below the box when its outgoing connector bends
    # up (the room above is taken by the connector), above it otherwise — including when
    # there is no outgoing connector. Set while wiring connectors.
    meta_below: bool = False
    # Wrap the metadata to the box width instead of letting it run past. Set for the
    # symmetric centre semis, whose two same-height lines would otherwise collide.
    meta_wrap: bool = False
    # Anchor the metadata at the box's right edge (flowing left) instead of its left edge.
    # Set for the symmetric right half so a long line overflows inward (toward the centre
    # gap) like the left half, rather than running off the right margin. Ignored when
    # meta_wrap is set (the wrapped semis stay within the box width either way).
    meta_end: bool = False

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


def _auto_box_width(stage: Stage, resolver: Resolver) -> float:
    """Width of the widest match box's content, for ``render.box_width == "auto"``.

    Sizes every box to fit its longest drawn side — the label (already capped at
    ``max_label_chars``, so the cap still bounds the width), an optional crest, the score
    column and the box paddings — and returns the maximum, floored at ``AUTO_MIN_BOX_W``.
    The glyph width is estimated high (the 13px label/score font is proportional), so the
    box never clips; a touch of slack is the only cost.
    """
    max_chars = stage.render.max_label_chars
    crest_w = FLAG_W if stage.render.crest_shape == "flag" else CREST_SIZE
    widest = float(AUTO_MIN_BOX_W)
    for rnd in stage.rounds:
        for match in rnd.matches:
            for side in ("home", "away"):
                slot = match.home if side == "home" else match.away
                lead = LABEL_PAD + (crest_w + CREST_GAP if slot.crest else 0)
                label_w = min(len(resolver.label(slot)), max_chars) * GLYPH_W
                score_chars = len(score_text(match, side))
                # The score is right-anchored; reserve its column plus a gap only when there
                # is one, otherwise just the right margin.
                right = SCORE_PAD + (
                    MIN_INNER_GAP + score_chars * GLYPH_W if score_chars else 0
                )
                widest = max(widest, lead + label_w + right)
    return widest


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
    # "auto" sizes the box to its widest content; a number is used verbatim.
    bw = (
        _auto_box_width(stage, resolver)
        if stage.render.box_width == "auto"
        else stage.render.box_width
    )
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
    headers: list[Header] = []

    # Bracket rounds are columns; rounds after the final (third place, all satellites) hang
    # below it. Splitting here keeps the round-name header generic — the below round draws
    # its own, so the final needs no special-casing.
    bracket_rounds = [r for r in stage.rounds if not _is_below_round(r)]
    below_rounds = [r for r in stage.rounds if _is_below_round(r)]

    def stack_cy(match: Match, index: int) -> float:
        """Vertical centre of a match: between the matches it consumes (via ``winner_of``),
        or stacked from the top by its index within its column/half when it has no parents.
        """
        parents = [
            centers[s.winner_of]
            for s in (match.home, match.away)
            if s.winner_of is not None and s.winner_of in centers
        ]
        if parents:
            return sum(parents) / len(parents)
        return TOP + meta_top + BOX_H / 2 + index * row_pitch

    def place(match: Match, x: float, cy: float) -> None:
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

    def place_below(rnds, below_x: float, cursor: float) -> None:
        """Stack below-the-bracket rounds (third place) downward from ``cursor``, each with
        its own header and no connector — they hang off the winners' tree."""
        cx = below_x + bw / 2
        for rnd in rnds:
            header_cy = cursor + HEADER_BAND
            headers.append(Header(name=rnd.name, cx=cx, cy=header_cy))
            box_y = header_cy + header_to_box
            for match in rnd.matches:
                cy = box_y + BOX_H / 2
                place(match, below_x, cy)
                box_y = cy + BOX_H / 2 + V_GAP + meta_top
            cursor = box_y

    def place_beside(rnds, beside_x: float, cy: float) -> None:
        """Place below-the-bracket rounds (third place) in column(s) to the *right* of the
        final, level with it, each with a normal top-band header and no connector. Used for a
        small bracket (a first round of <=2 matches), where hanging third place underneath
        the final leaves a lopsided diagram; beside the final it reads as one more column.
        """
        for col, rnd in enumerate(rnds):
            x = beside_x + col * column_pitch
            headers.append(Header(name=rnd.name, cx=x + bw / 2))  # top-band header
            for i, match in enumerate(rnd.matches):
                place(match, x, cy + i * row_pitch)

    if stage.render.layout == "symmetric":
        n_cols, connect = _place_symmetric(
            bracket_rounds,
            below_rounds,
            bw,
            column_pitch,
            meta_top,
            meta_h,
            headers,
            by_placed,
            stack_cy,
            place,
            place_below,
        )
        # The lifted final can reach above the header band; nudge the diagram down to fit.
        _apply_top_offset(placed, headers, meta_top)
    else:
        n_cols, connect = _place_linear(
            bracket_rounds,
            below_rounds,
            bw,
            column_pitch,
            meta_h,
            meta_top,
            headers,
            placed,
            stack_cy,
            place,
            place_below,
            place_beside,
        )

    connectors = _connectors(connect, by_placed, bw)

    width: float = MARGIN_X * 2 + n_cols * bw + max(n_cols - 1, 0) * H_GAP
    # The metadata line is drawn left-anchored at its box's x and is not wrapped, so a long
    # one (especially the rightmost column's, e.g. the final's) can run past the canvas and
    # clip. Estimate each line's width by character count and widen the canvas to fit it.
    if stage.render.show_metadata:
        fmt = stage.render.dt_format

        def _meta_right(pm: PlacedMatch) -> float:
            # A meta_end box anchors at its right edge and flows left, and a meta_wrap box
            # wraps within the box width, so both reach only the box edge; a normal box flows
            # right (unwrapped) from its left edge.
            if pm.meta_end or pm.meta_wrap:
                return pm.x + bw
            return (
                pm.x + len(meta_text(pm.match, fmt, timezone, language)) * META_CHAR_W
            )

        rightmost = max((_meta_right(pm) for pm in placed), default=0.0)
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


def _place_symmetric(  # noqa: PLR0913 — geometry helper, threads compute_layout's state
    bracket_rounds,
    below_rounds,
    bw: float,
    column_pitch: float,
    meta_top: float,
    meta_h: float,
    headers: list[Header],
    by_placed: dict[Optional[str], PlacedMatch],
    stack_cy,
    place,
    place_below,
) -> "tuple[int, list[PlacedMatch]]":
    """Place the FIFA-style mirrored diagram; return its column count and the matches to connect.

    Every round *before* the final is mirror-split by document order — its first half fans
    in from the left, its second half mirrors on the right — so the innermost such round
    (the semifinals) lands in the two central, adjacent columns ("pegadas"); an odd round
    puts the extra match on the left. Each outer round draws *two* top-band headers (left
    and right column), its winners' connectors running inward (handled by ``_connectors``).

    The final is lifted into the gap *above* the semis and a third-place (below) round
    dropped *below* them, both straddling the centre. No connector is drawn between the
    final and the semis — the pairing into the final is understood by position, so the
    final is skipped in ``_connectors`` — which frees the gap above the semis for their
    title, placed there (close to the boxes) instead of in the top band. The central column
    is therefore taller than the side ones — accepted, per the FIFA layout.
    """
    *mirror_rounds, final_round = bracket_rounds  # the last bracket round is the final
    m = len(mirror_rounds)
    connect: list[PlacedMatch] = []  # the matches whose incoming connectors are drawn
    for r_index, rnd in enumerate(mirror_rounds):
        x_left = MARGIN_X + r_index * column_pitch
        x_right = MARGIN_X + (2 * m - 1 - r_index) * column_pitch
        split = (len(rnd.matches) + 1) // 2  # odd round: the extra match goes left
        for i, match in enumerate(rnd.matches[:split]):
            place(match, x_left, stack_cy(match, i))
        for i, match in enumerate(rnd.matches[split:]):
            place(match, x_right, stack_cy(match, i))
            by_placed[match.id].meta_end = True  # right half: metadata flows inward
        connect.extend(by_placed[mt.id] for mt in rnd.matches)
        if r_index < m - 1:  # outer rounds: header in the top band over each column
            headers.append(Header(name=rnd.name, cx=x_left + bw / 2))
            headers.append(Header(name=rnd.name, cx=x_right + bw / 2))

    # The centre straddles the two innermost columns (the semis). With no earlier rounds
    # the final stands alone in the first column.
    if m:
        centre_x = MARGIN_X + (m - 0.5) * column_pitch
        semis = [by_placed[mt.id] for mt in mirror_rounds[-1].matches]
        semi_top = min(s.y for s in semis)
        semi_bottom = max(s.y + BOX_H for s in semis)
        # The semifinals' title hugs their boxes (in the gap the dropped final connector
        # used to fill); their metadata goes below, leaving that gap free for it, and wraps
        # to the box width so the two adjacent same-height lines can't collide.
        for s in semis:
            s.meta_below = True
            s.meta_wrap = True
            headers.append(
                Header(name=mirror_rounds[-1].name, cx=s.x + bw / 2, cy=s.y - 16)
            )
    else:
        centre_x = MARGIN_X
        semi_top = TOP + meta_top
        semi_bottom = TOP + meta_top + BOX_H

    # The final, lifted into the gap above the semis, with its header above its box. No
    # connector down to the semis (the pairing is implied), so it is skipped in _connectors.
    final_cy = semi_top - CENTRE_GAP - BOX_H / 2
    for match in final_round.matches:
        place(match, centre_x, final_cy)
        fp = by_placed[match.id]
        headers.append(
            Header(name=final_round.name, cx=centre_x + bw / 2, cy=fp.y - meta_top - 6)
        )

    # Third place dropped below the semis, straddling the centre.
    if below_rounds:
        place_below(below_rounds, centre_x, semi_bottom + meta_h + V_GAP)

    n_cols = 2 * m if m else 1
    return n_cols, connect


def _place_linear(  # noqa: PLR0913 — geometry helper, threads compute_layout's state
    bracket_rounds,
    below_rounds,
    bw: float,
    column_pitch: float,
    meta_h: float,
    meta_top: float,
    headers: list[Header],
    placed: list[PlacedMatch],
    stack_cy,
    place,
    place_below,
    place_beside,
) -> "tuple[int, list[PlacedMatch]]":
    """Place the left-to-right linear diagram; return its column count and matches to connect.

    Rounds flow into columns with the final last. A third-place (below) round goes *beside*
    the final, level with it, for a small bracket — a first round of <=2 matches — or hangs
    under the final's column otherwise (placed beside a tall bracket it would float far out).
    Every placed match's incoming connector is drawn (third place simply has none).
    """
    for r_index, rnd in enumerate(bracket_rounds):
        x = MARGIN_X + r_index * column_pitch
        headers.append(Header(name=rnd.name, cx=x + bw / 2))
        for m_index, match in enumerate(rnd.matches):
            place(match, x, stack_cy(match, m_index))
    n_cols = len(bracket_rounds)
    if below_rounds:
        final_x = MARGIN_X + max(n_cols - 1, 0) * column_pitch
        if bracket_rounds and len(bracket_rounds[0].matches) <= 2:
            final_pm = next((pm for pm in placed if pm.x == final_x), None)
            final_cy = final_pm.cy if final_pm else TOP + meta_top + BOX_H / 2
            start = len(placed)
            place_beside(below_rounds, final_x + column_pitch, final_cy)
            n_cols += len(below_rounds)
            # The final and third place sit side by side: wrap each one's metadata to its box
            # width and drop it below the box, so the two long lines don't run into each other.
            for pm in [final_pm, *placed[start:]]:
                if pm is not None:
                    pm.meta_below = True
                    pm.meta_wrap = True
        else:
            # Hang third place just below the final, in its own (last) column — not below the
            # whole bracket, whose lowest first-round box sits far lower and would leave a big
            # empty gap. The final is the only box in that column.
            final_bottom = max(
                (pm.y + BOX_H for pm in placed if pm.x == final_x), default=TOP
            )
            place_below(below_rounds, final_x, final_bottom + meta_h + V_GAP)
    return n_cols, placed


def _apply_top_offset(
    placed: list[PlacedMatch],
    headers: list[Header],
    meta_top: float,
) -> None:
    """Shift boxes and their attached captions down so the lifted final clears the band.

    The symmetric final is lifted above the semis and, in a short bracket, would otherwise
    overlap the column-header band (which keeps its place at the top). Pushing the topmost
    box down to a normal first-row position keeps the final's own (attached) header and
    metadata clear of that band; the side columns then hang lower, the intended taller
    centre. Top-band column headers (at ``HEADER_Y``) stay put; the final's, the semis' and
    the third place's captions travel with their boxes. A no-op when nothing rises that
    high. (Connectors are wired afterwards, from the shifted boxes, so none need moving.)
    """
    top = min((p.y for p in placed), default=TOP)
    offset = (TOP + meta_top + 14) - top
    if offset <= 0:
        return
    for p in placed:
        p.y += offset
    for h in headers:
        if h.cy != HEADER_Y:  # column headers stay in the band; attached captions move
            h.cy += offset


def _connectors(
    children: list[PlacedMatch],
    by_placed: dict[Optional[str], PlacedMatch],
    bw: float,
) -> list[Connector]:
    """Draw the advancement connector into each given child from its ``winner_of`` parents.

    The caller passes exactly the matches whose incoming connectors should be drawn — every
    placed match in the linear layout, but only the mirror rounds in the symmetric one,
    where the centred final's pairing is shown by position rather than a connector. Children
    are passed as placed matches (not looked up by id) because two id-less matches — the
    final and a third place — would share the ``None`` key; parents are always a real
    ``winner_of`` id, never None.
    """
    connectors: list[Connector] = []
    for child in children:
        match = child.match
        for side, slot in (("home", match.home), ("away", match.away)):
            if slot.winner_of is None or slot.winner_of not in by_placed:
                continue
            parent = by_placed[slot.winner_of]
            # In the mirrored (symmetric) layout the right half's parent sits to the right
            # of its child, so the connector leaves the parent's *left* edge and meets the
            # child's *right* edge; the linear case (and the left half) is the reverse.
            mirrored = parent.x > child.x
            start = (parent.x if mirrored else parent.x + bw, parent.cy)
            child_x = child.x + bw if mirrored else child.x
            conn_y = child.y + (ROW_H / 2 if side == "home" else ROW_H + ROW_H / 2)
            # This connector leaves the parent toward its child: bending up means the
            # space above the parent is taken, so its metadata goes below.
            parent.meta_below = conn_y < parent.cy
            mid_x = (start[0] + child_x) / 2
            connectors.append(
                Connector(
                    points=[
                        start,
                        (mid_x, parent.cy),
                        (mid_x, conn_y),
                        (child_x, conn_y),
                    ]
                )
            )
    return connectors
