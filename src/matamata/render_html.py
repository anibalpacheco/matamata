"""Turn a knockout stage into an HTML table string, for small screens.

The alternative to the SVG diagram: rounds stack vertically, each match is its own
two-row ``<table>`` — a separate little box, like the SVG's match boxes — and
advancement is implied by reading order, so no connectors are drawn. The output is a
self-contained fragment; styling is driven by CSS classes so it can be themed by the
host page, with sensible defaults embedded.

Like the SVG renderer this computes nothing about the tournament: labels, scores, the
emphasized winner and each side's crest/flag come straight from the model. Crests are
only ever filled by the KnockoutStage path (the ``get_crest`` hook); a document rendered
without it carries none. The ``render`` options are SVG geometry knobs and are ignored
here — HTML handles long names natively.
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
  .pd-score { font-size: 13px; padding: 5px 8px; text-align: right;
              white-space: nowrap; }
  .pd-win td { font-weight: 700; color: #065f46; }
  @media (prefers-color-scheme: dark) {
    .pd-stage { color: #e5e7eb; background: #0f172a; }
    .pd-title { color: #f8fafc; }
    .pd-season { color: #94a3b8; }
    .pd-header { color: #cbd5e1; }
    .pd-team, .pd-score { color: #e5e7eb; }
    .pd-match { background: #1e293b; border-color: #334155; }
    .pd-side + .pd-side td { border-top-color: #334155; }
    .pd-win td { color: #34d399; }
  }
""".rstrip()


def _side_row(out: list[str], match: Match, side: str, resolver: Resolver) -> None:
    slot = match.home if side == "home" else match.away
    cls = "pd-side pd-win" if match.winner == side else "pd-side"
    crest = (
        f'<img class="pd-crest" src="{escape(slot.crest, _ATTR)}" alt=""/>'
        if slot.crest
        else ""
    )
    out.append(f'<tr class="{cls}">')
    out.append(f'<td class="pd-team">{crest}{escape(resolver.label(slot))}</td>')
    out.append(f'<td class="pd-score">{escape(score_text(match, side))}</td>')
    out.append("</tr>")


def render_html(stage: Stage) -> str:
    """Render the knockout stage to a self-contained HTML table fragment string."""
    out: list[str] = []
    resolver = Resolver(stage)
    out.append('<div class="pd-stage">')
    out.append(f"<style>{_STYLE}</style>")
    if stage.tournament:
        title = escape(stage.tournament)
        season = (
            f' <span class="pd-season">{escape(stage.season)}</span>'
            if stage.season
            else ""
        )
        out.append(f'<h2 class="pd-title">{title}{season}</h2>')
    for rnd in stage.rounds:
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
    out.append("</div>")
    return "\n".join(out)
