"""Turn a knockout stage into an SVG string using the deterministic layout.

The output is a self-contained ``<svg>`` document. Styling is driven by CSS classes so
the diagram can be themed by the host page; sensible defaults are embedded.
"""

from __future__ import annotations

from typing import Optional
from xml.sax.saxutils import escape

from .layout import BOX_H, ROW_H, Layout, PlacedMatch, SideView, compute_layout
from .model import Stage, meta_text

_LABEL_PAD = 10
_SCORE_PAD = 8
_CREST_SIZE = 16  # square crest side, vertically centered in the 24-unit row
_FLAG_W = 24  # flag box is 3:2 (24x16); the image is fitted inside without distortion
_CREST_GAP = 6
_ATTR = {'"': "&quot;"}  # extra escape for attribute values

_STYLE = """
  .pd-bg { fill: #ffffff; }
  .pd-title { font: 600 18px sans-serif; fill: #111827; }
  .pd-season { font: 400 13px sans-serif; fill: #6b7280; }
  .pd-header { font: 600 12px sans-serif; fill: #374151; text-anchor: middle; }
  .pd-meta { font: 400 11px sans-serif; fill: #6b7280; }
  .pd-box { fill: #ffffff; stroke: #d1d5db; stroke-width: 1; }
  .pd-divider { stroke: #e5e7eb; stroke-width: 1; }
  .pd-team { font: 400 13px sans-serif; fill: #1f2937; }
  .pd-score { font: 400 13px sans-serif; fill: #1f2937; text-anchor: end; }
  .pd-win .pd-team, .pd-win .pd-score { font-weight: 700; fill: #065f46; }
  .pd-crest-frame { fill: none; stroke: #d1d5db; stroke-width: 1; }
  .pd-link { fill: none; stroke: #cbd5e1; stroke-width: 1.5; }
  @media (prefers-color-scheme: dark) {
    .pd-bg { fill: #0f172a; }
    .pd-title { fill: #f8fafc; }
    .pd-season { fill: #94a3b8; }
    .pd-header { fill: #cbd5e1; }
    .pd-meta { fill: #94a3b8; }
    .pd-box { fill: #1e293b; stroke: #334155; }
    .pd-divider { stroke: #334155; }
    .pd-team { fill: #e5e7eb; }
    .pd-score { fill: #e5e7eb; }
    .pd-win .pd-team, .pd-win .pd-score { fill: #34d399; }
    .pd-crest-frame { stroke: #334155; }
    .pd-link { stroke: #475569; }
  }
""".rstrip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def _row(
    out: list[str],
    pm: PlacedMatch,
    side: SideView,
    top: float,
    max_chars: int,
    box_w: float,
    flag: bool = False,
) -> None:
    text_y = top + ROW_H / 2 + 4
    cls = "pd-win" if side.is_winner else ""
    out.append(f'<g class="{cls}">')
    label_x = pm.x + _LABEL_PAD
    if side.crest:
        crest_w = _FLAG_W if flag else _CREST_SIZE
        crest_y = top + (ROW_H - _CREST_SIZE) / 2
        # In flag mode the image is fitted into the 3:2 box without distortion and framed.
        fit = ' preserveAspectRatio="xMidYMid meet"' if flag else ""
        out.append(
            f'<image class="pd-crest" '
            f'href="{escape(side.crest, _ATTR)}" '
            f'x="{label_x:.0f}" y="{crest_y:.0f}" '
            f'width="{crest_w}" height="{_CREST_SIZE}"{fit}/>'
        )
        if flag:
            out.append(
                f'<rect class="pd-crest-frame" x="{label_x:.0f}" y="{crest_y:.0f}" '
                f'width="{crest_w}" height="{_CREST_SIZE}"/>'
            )
        label_x += crest_w + _CREST_GAP
    out.append(
        f'<text class="pd-team" x="{label_x:.0f}" y="{text_y:.0f}">'
        f"{escape(_truncate(side.label, max_chars))}</text>"
    )
    if side.score:
        out.append(
            f'<text class="pd-score" x="{pm.x + box_w - _SCORE_PAD:.0f}" '
            f'y="{text_y:.0f}">{escape(side.score)}</text>'
        )
    out.append("</g>")


def _match(
    out: list[str],
    pm: PlacedMatch,
    max_chars: int,
    box_w: float,
    flag: bool = False,
    meta: Optional[str] = None,
) -> None:
    if meta:
        out.append(
            f'<text class="pd-meta" x="{pm.x:.0f}" y="{pm.y - 6:.0f}">'
            f"{escape(meta)}</text>"
        )
    out.append(
        f'<rect class="pd-box" x="{pm.x:.0f}" y="{pm.y:.0f}" '
        f'width="{box_w:.0f}" height="{BOX_H}" rx="3"/>'
    )
    mid = pm.y + ROW_H
    out.append(
        f'<line class="pd-divider" x1="{pm.x:.0f}" y1="{mid:.0f}" '
        f'x2="{pm.x + box_w:.0f}" y2="{mid:.0f}"/>'
    )
    _row(out, pm, pm.home, pm.y, max_chars, box_w, flag)
    _row(out, pm, pm.away, mid, max_chars, box_w, flag)


def render_layout(stage: Stage, layout: Layout, timezone: Optional[str] = None) -> str:
    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {layout.width:.0f} {layout.height:.0f}" '
        f'width="{layout.width:.0f}" height="{layout.height:.0f}" '
        f'font-family="sans-serif">'
    )
    out.append(f"<style>{_STYLE}</style>")
    out.append(
        f'<rect class="pd-bg" width="{layout.width:.0f}" '
        f'height="{layout.height:.0f}"/>'
    )

    title = escape(stage.tournament)
    out.append(f'<text class="pd-title" x="20" y="28">{title}</text>')
    if stage.season:
        x = 20 + round(len(stage.tournament) * 10.5) + 14
        out.append(
            f'<text class="pd-season" x="{x}" y="28">' f"{escape(stage.season)}</text>"
        )

    for header in layout.headers:
        out.append(
            f'<text class="pd-header" x="{header.cx:.0f}" y="56">'
            f"{escape(header.name)}</text>"
        )

    for conn in layout.connectors:
        d = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in conn.points)
        out.append(f'<path class="pd-link" d="{d}"/>')

    flag = stage.render.crest_shape == "flag"
    show_meta = stage.render.show_metadata
    for pm in layout.matches:
        meta = (
            meta_text(pm.match, stage.render.dt_format, timezone) if show_meta else None
        )
        _match(out, pm, stage.render.max_label_chars, layout.box_width, flag, meta)

    out.append("</svg>")
    return "\n".join(out)


def render_svg(stage: Stage, timezone: Optional[str] = None) -> str:
    """Render the knockout stage to a self-contained SVG document string.

    ``timezone`` is an optional zone name (e.g. ``"America/Montevideo"``) the metadata
    datetimes (assumed GMT) are converted to before rendering.
    """
    return render_layout(stage, compute_layout(stage), timezone)
