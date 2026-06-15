"""Turn a knockout stage into an HTML table string, for small screens.

The alternative to the SVG diagram: rounds stack vertically and advancement is implied
by reading order, so no connectors are drawn. Two layouts are offered:

- ``"flat"`` (the default): the whole stage is one ``<table>`` — each match is a
  ``<tr>`` per leg — ``[meta] name1 [crest1] score1  x  score2 [crest2] name2`` — and each
  round name is a full-width header row. Sharing one table keeps every column aligned
  vertically across all rounds. The names are aligned outward and the crests hug the
  central ``x``; the ``x`` is always shown, reading as "vs" when a match has no result
  yet. When metadata is on, each row leads with the bold id and that leg's own
  ``dt``/``venue`` (one row per leg, so each leg's schedule sits beside its scores).
- ``"stacked"``: each match is its own two-row ``<table>`` — a separate little box, like
  the SVG's match boxes.

The output is a self-contained fragment; styling is driven by CSS classes so it can be
themed by the host page, with sensible defaults embedded.

Like the SVG renderer this computes nothing about the tournament: labels, scores, the
emphasized winner and each side's crest/flag come straight from the model. Crests are
only ever filled by the KnockoutStage path (the ``get_crest`` hook); a document rendered
without it carries none, and ``render.crest_shape`` decides whether they are drawn as
squares (club crests) or framed 3:2 rectangles (national flags). The other ``render``
options are SVG geometry knobs and are ignored here — HTML handles long names natively.
"""

from __future__ import annotations

from typing import Optional
from xml.sax.saxutils import escape

from .model import (
    Leg,
    Match,
    Resolver,
    Stage,
    leg_meta_text,
    leg_score_text,
    meta_parts,
    score_text,
)

_ATTR = {'"': "&quot;"}  # extra escape for attribute values

_STYLE = """
  .pd-stage { font-family: sans-serif; color: #1f2937; background: #ffffff; }
  .pd-title { font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 12px; }
  .pd-season { font-size: 13px; font-weight: 400; color: #6b7280; margin-left: 8px; }
  .pd-header { font-size: 15px; font-weight: 600; color: #374151; margin: 16px 0 8px; }
  .pd-meta { font-size: 11px; color: #6b7280; margin: 0 0 3px; }
  .pd-meta-id { font-weight: 700; }
  .pd-match { border-collapse: separate; border-spacing: 0; width: 100%;
              max-width: 24em; border: 1px solid #d1d5db; border-radius: 3px;
              overflow: hidden; margin: 0 0 15px; }
  .pd-side + .pd-side td { border-top: 1px solid #e5e7eb; }
  .pd-team { font-size: 13px; padding: 5px 10px; }
  .pd-crest { width: 16px; height: 16px; vertical-align: middle; margin-right: 6px; }
  .pd-flags .pd-crest { width: 24px; height: 16px; object-fit: cover;
                        box-sizing: border-box; border: 1px solid #d1d5db; }
  .pd-score { font-size: 13px; padding: 5px 8px; text-align: right;
              white-space: nowrap; }
  .pd-win td { font-weight: 700; color: #065f46; }
  .pd-grid { border-collapse: collapse; margin: 0 0 4px; }
  .pd-grid td { font-size: 13px; padding: 4px 6px; vertical-align: middle;
                white-space: nowrap; }
  .pd-team1, .pd-score1, .pd-crest1 { text-align: right; }
  .pd-team2, .pd-score2, .pd-crest2 { text-align: left; }
  .pd-crest1, .pd-crest2 { padding: 0; }
  .pd-crest1 .pd-crest { margin: 0 0 0 6px; }
  .pd-crest2 .pd-crest { margin: 0 6px 0 0; }
  .pd-vs { color: #9ca3af; padding: 4px 8px; }
  .pd-grid .pd-round-head { font-size: 15px; font-weight: 600; color: #374151;
                            text-align: left; padding: 26px 6px 6px; }
  .pd-grid tr:first-child .pd-round-head { padding-top: 4px; }
  .pd-grid .pd-meta { font-size: 11px; color: #6b7280; text-align: left;
                      padding: 8px 6px 0; }
  .pd-grid .pd-win { font-weight: 700; color: #065f46; }
  @media (prefers-color-scheme: dark) {
    .pd-stage { color: #e5e7eb; background: #0f172a; }
    .pd-title { color: #f8fafc; }
    .pd-season { color: #94a3b8; }
    .pd-header { color: #cbd5e1; }
    .pd-meta, .pd-grid .pd-meta { color: #94a3b8; }
    .pd-team, .pd-score, .pd-grid td { color: #e5e7eb; }
    .pd-flags .pd-crest { border-color: #334155; }
    .pd-match { background: #1e293b; border-color: #334155; }
    .pd-side + .pd-side td { border-top-color: #334155; }
    .pd-win td, .pd-grid .pd-win { color: #34d399; }
    .pd-vs { color: #64748b; }
    .pd-grid .pd-round-head { color: #cbd5e1; }
  }
""".rstrip()


def _crest_img(slot) -> str:
    """The ``<img>`` for a side's crest/flag, or an empty string if it has none."""
    if not slot.crest:
        return ""
    return f'<img class="pd-crest" src="{escape(slot.crest, _ATTR)}" alt=""/>'


def _meta_html(match: Match, dt_format, tz) -> str:
    """The metadata line's inner HTML, with the id wrapped in a bold span. "" when empty."""
    label, detail = meta_parts(match, dt_format, tz)
    if not label:
        return escape(detail)
    inner = f'<span class="pd-meta-id">{escape(label)}</span>'
    if detail:
        inner += escape(f" · {detail}")
    return inner


def _side_row(out: list[str], match: Match, side: str, resolver: Resolver) -> None:
    """One match side as a ``<tr>`` of the stacked two-row box."""
    slot = match.home if side == "home" else match.away
    cls = "pd-side pd-win" if match.winner == side else "pd-side"
    out.append(f'<tr class="{cls}">')
    out.append(
        f'<td class="pd-team">{_crest_img(slot)}{escape(resolver.label(slot))}</td>'
    )
    out.append(f'<td class="pd-score">{escape(score_text(match, side))}</td>')
    out.append("</tr>")


def _flat_meta_inner(id_cell: str, detail: str) -> str:
    """The metadata line's inner HTML: the bold id then this leg's ``dt venue``. "" if empty."""
    inner = id_cell
    if detail:
        inner = f"{inner} · {escape(detail)}" if inner else escape(detail)
    return inner


def _flat_rows(
    out: list[str],
    match: Match,
    resolver: Resolver,
    show_meta: bool,
    dt_format: Optional[str],
    tz: Optional[str],
) -> None:
    """A match as one ``<tr>`` per leg of the round's grid.

    A two-legged tie becomes two rows — one per leg, each carrying that leg's single
    score — so the columns stay one figure wide; a match with no legs is a single
    scoreless row. Each row honors the leg's localía: its local side (the JSON ``team1``)
    goes in the home/left column, so the second leg flips relative to the first. The
    winner emphasis follows the team into whichever column it lands in. When metadata is
    on, each leg's score row is preceded by a full-width metadata row carrying the id and
    *that leg's* own ``dt``/``venue`` (the one-row-per-leg layout gives each leg its own
    schedule line, instead of joining both legs as the SVG/stacked single box does).
    """
    home, away = match.home, match.away
    id_cell = (
        f'<span class="pd-meta-id">{escape(match.id.upper())}</span>'
        if match.id
        else ""
    )
    legs: list[Optional[Leg]] = list(match.legs) if match.legs else [None]
    for leg in legs:
        # The local side fills the home (left) column; tie order is the fallback.
        local = leg.local if leg is not None and leg.local is not None else "home"
        left, right = ("away", "home") if local == "away" else ("home", "away")
        left_slot = home if left == "home" else away
        right_slot = home if right == "home" else away
        left_win = " pd-win" if match.winner == left else ""
        right_win = " pd-win" if match.winner == right else ""
        score1 = leg_score_text(leg, left) if leg is not None else ""
        score2 = leg_score_text(leg, right) if leg is not None else ""
        if show_meta:
            detail = leg_meta_text(leg if leg is not None else match, dt_format, tz)
            inner = _flat_meta_inner(id_cell, detail)
            if inner:
                out.append('<tr class="pd-meta-row">')
                out.append(f'<td class="pd-meta" colspan="7">{inner}</td>')
                out.append("</tr>")
        out.append('<tr class="pd-match-row">')
        out.append(
            f'<td class="pd-team pd-team1{left_win}">'
            f"{escape(resolver.label(left_slot))}</td>"
        )
        out.append(f'<td class="pd-crest1{left_win}">{_crest_img(left_slot)}</td>')
        out.append(f'<td class="pd-score pd-score1{left_win}">{escape(score1)}</td>')
        out.append('<td class="pd-vs">x</td>')
        out.append(f'<td class="pd-score pd-score2{right_win}">{escape(score2)}</td>')
        out.append(f'<td class="pd-crest2{right_win}">{_crest_img(right_slot)}</td>')
        out.append(
            f'<td class="pd-team pd-team2{right_win}">'
            f"{escape(resolver.label(right_slot))}</td>"
        )
        out.append("</tr>")


def _render_stacked(
    out: list[str],
    rounds,
    resolver: Resolver,
    show_meta: bool,
    dt_format: Optional[str],
    tz: Optional[str],
) -> None:
    """Each round as a labeled block of two-row match boxes, each with a metadata line."""
    for rnd in rounds:
        out.append('<div class="pd-round">')
        out.append(f'<h3 class="pd-header">{escape(rnd.name)}</h3>')
        for match in rnd.matches:
            meta = _meta_html(match, dt_format, tz) if show_meta else ""
            if meta:
                out.append(f'<div class="pd-meta">{meta}</div>')
            out.append('<table class="pd-match">')
            out.append("<tbody>")
            _side_row(out, match, "home", resolver)
            _side_row(out, match, "away", resolver)
            out.append("</tbody>")
            out.append("</table>")
        out.append("</div>")


def _render_flat(
    out: list[str],
    rounds,
    resolver: Resolver,
    show_meta: bool,
    dt_format: Optional[str],
    tz: Optional[str],
) -> None:
    """The whole stage as one grid table: a header row per round, then a row per leg."""
    out.append('<table class="pd-grid">')
    out.append("<tbody>")
    for rnd in rounds:
        out.append('<tr class="pd-round-row">')
        out.append(f'<td class="pd-round-head" colspan="7">{escape(rnd.name)}</td>')
        out.append("</tr>")
        for match in rnd.matches:
            _flat_rows(out, match, resolver, show_meta, dt_format, tz)
    out.append("</tbody>")
    out.append("</table>")


def render_html(
    stage: Stage, layout: str = "flat", timezone: Optional[str] = None
) -> str:
    """Render the knockout stage to a self-contained HTML table fragment string.

    ``layout`` is ``"flat"`` (the default — the whole stage in one grid table, one row
    per leg with names aligned outward around a central ``x``) or ``"stacked"`` (each
    match its own two-row box). ``timezone`` is an optional zone name the metadata
    datetimes (assumed GMT) are converted to before rendering.
    """
    if layout not in ("flat", "stacked"):
        raise ValueError(f"unknown layout {layout!r}")
    out: list[str] = []
    resolver = Resolver(stage)
    show_meta = stage.render.show_metadata
    stage_cls = (
        "pd-stage pd-flags" if stage.render.crest_shape == "flag" else "pd-stage"
    )
    out.append(f'<div class="{stage_cls}">')
    out.append(f"<style>{_STYLE}</style>")
    if stage.tournament:
        title = escape(stage.tournament)
        season = (
            f' <span class="pd-season">{escape(stage.season)}</span>'
            if stage.season
            else ""
        )
        out.append(f'<h2 class="pd-title">{title}{season}</h2>')
    if layout == "flat":
        _render_flat(
            out, stage.rounds, resolver, show_meta, stage.render.dt_format, timezone
        )
    else:
        _render_stacked(
            out, stage.rounds, resolver, show_meta, stage.render.dt_format, timezone
        )
    out.append("</div>")
    return "\n".join(out)
