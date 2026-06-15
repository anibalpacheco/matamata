"""Turn a knockout stage into an HTML table string, for small screens.

The alternative to the SVG diagram: rounds stack vertically and advancement is implied
by reading order, so no connectors are drawn. Two layouts are offered:

- ``"flat"`` (the default): the whole stage is one ``<table>`` — each match is a
  ``<tr>`` — ``name1 [crest1] score1  x  score2 [crest2] name2`` — and each round name is
  a full-width header row. Sharing one table keeps every column aligned vertically across
  all rounds. The names are aligned outward and the crests hug the central ``x``; the
  ``x`` is always shown, reading as "vs" when a match has no result yet.
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

from xml.sax.saxutils import escape

from .model import Match, Resolver, Stage, score_text

_ATTR = {'"': "&quot;"}  # extra escape for attribute values

_STYLE = """
  .pd-stage { font-family: sans-serif; color: #1f2937; background: #ffffff; }
  .pd-title { font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 12px; }
  .pd-season { font-size: 13px; font-weight: 400; color: #6b7280; margin-left: 8px; }
  .pd-header { font-size: 12px; font-weight: 600; color: #374151; margin: 16px 0 8px; }
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
  .pd-grid .pd-round-head { font-size: 12px; font-weight: 600; color: #374151;
                            text-align: left; padding: 26px 6px 6px; }
  .pd-grid tr:first-child .pd-round-head { padding-top: 4px; }
  .pd-grid .pd-win { font-weight: 700; color: #065f46; }
  @media (prefers-color-scheme: dark) {
    .pd-stage { color: #e5e7eb; background: #0f172a; }
    .pd-title { color: #f8fafc; }
    .pd-season { color: #94a3b8; }
    .pd-header { color: #cbd5e1; }
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


def _flat_row(out: list[str], match: Match, resolver: Resolver) -> None:
    """One match as a single ``<tr>`` of the round's grid: name-crest-score x score-crest-name."""
    home_win = " pd-win" if match.winner == "home" else ""
    away_win = " pd-win" if match.winner == "away" else ""
    home, away = match.home, match.away
    out.append('<tr class="pd-match-row">')
    out.append(
        f'<td class="pd-team pd-team1{home_win}">{escape(resolver.label(home))}</td>'
    )
    out.append(f'<td class="pd-crest1{home_win}">{_crest_img(home)}</td>')
    out.append(
        f'<td class="pd-score pd-score1{home_win}">{escape(score_text(match, "home"))}</td>'
    )
    out.append('<td class="pd-vs">x</td>')
    out.append(
        f'<td class="pd-score pd-score2{away_win}">{escape(score_text(match, "away"))}</td>'
    )
    out.append(f'<td class="pd-crest2{away_win}">{_crest_img(away)}</td>')
    out.append(
        f'<td class="pd-team pd-team2{away_win}">{escape(resolver.label(away))}</td>'
    )
    out.append("</tr>")


def _render_stacked(out: list[str], rounds, resolver: Resolver) -> None:
    """Each round as a labeled block of two-row match boxes."""
    for rnd in rounds:
        out.append('<div class="pd-round">')
        out.append(f'<h3 class="pd-header">{escape(rnd.name)}</h3>')
        for match in rnd.matches:
            out.append('<table class="pd-match">')
            out.append("<tbody>")
            _side_row(out, match, "home", resolver)
            _side_row(out, match, "away", resolver)
            out.append("</tbody>")
            out.append("</table>")
        out.append("</div>")


def _render_flat(out: list[str], rounds, resolver: Resolver) -> None:
    """The whole stage as one grid table: a header row per round, then a row per match."""
    out.append('<table class="pd-grid">')
    out.append("<tbody>")
    for rnd in rounds:
        out.append('<tr class="pd-round-row">')
        out.append(f'<td class="pd-round-head" colspan="7">{escape(rnd.name)}</td>')
        out.append("</tr>")
        for match in rnd.matches:
            _flat_row(out, match, resolver)
    out.append("</tbody>")
    out.append("</table>")


def render_html(stage: Stage, layout: str = "flat") -> str:
    """Render the knockout stage to a self-contained HTML table fragment string.

    ``layout`` is ``"flat"`` (the default — the whole stage in one grid table, one row
    per match with names aligned outward around a central ``x``) or ``"stacked"`` (each
    match its own two-row box).
    """
    render_rounds = {"flat": _render_flat, "stacked": _render_stacked}.get(layout)
    if render_rounds is None:
        raise ValueError(f"unknown layout {layout!r}")
    out: list[str] = []
    resolver = Resolver(stage)
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
    render_rounds(out, stage.rounds, resolver)
    out.append("</div>")
    return "\n".join(out)
