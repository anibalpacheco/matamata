"""Turn a knockout stage into an SVG string using the deterministic layout.

The output is a self-contained ``<svg>`` document. Styling is driven by CSS classes so
the diagram can be themed by the host page; sensible defaults are embedded.
"""

from __future__ import annotations

from typing import Optional
from xml.sax.saxutils import escape

from .layout import BOX_H, ROW_H, Layout, PlacedMatch, SideView, compute_layout
from .model import Stage, meta_parts

_LABEL_PAD = 10
_SCORE_PAD = 8
_META_CHAR_W = (
    6.0  # rough px per glyph of the 11px metadata font, for wrapping to box width
)
_CREST_SIZE = 16  # square crest side, vertically centered in the 24-unit row
_FLAG_W = 24  # flag box is 3:2 (24x16); the image is fitted inside without distortion
_CREST_GAP = 6
_ATTR = {'"': "&quot;"}  # extra escape for attribute values

_STYLE = """
  .pd-bg { fill: #ffffff; }
  .pd-title { font: 600 18px sans-serif; fill: #111827; }
  .pd-season { font: 400 13px sans-serif; fill: #6b7280; }
  .pd-header { font: 600 15px sans-serif; fill: #374151; text-anchor: middle; }
  .pd-meta { font: 400 11px sans-serif; fill: #6b7280; }
  .pd-meta-id { font-weight: 700; }
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
    label: str = "",
    detail: str = "",
) -> None:
    if label or detail:
        # Below the box when its connector bends up (room above is taken), else above it.
        meta_y = pm.y + BOX_H + 14 if pm.meta_below else pm.y - 6
        inner = (
            _meta_wrapped(pm.x, label, detail, box_w)
            if pm.meta_wrap
            else _meta_single(label, detail)
        )
        out.append(
            f'<text class="pd-meta" x="{pm.x:.0f}" y="{meta_y:.0f}">{inner}</text>'
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


def _meta_single(label: str, detail: str) -> str:
    """The metadata line's inner SVG markup on one line, the id wrapped in a bold tspan."""
    if not label:
        return escape(detail)
    inner = f'<tspan class="pd-meta-id">{escape(label)}</tspan>'
    if detail:
        inner += escape(f" · {detail}")
    return inner


def _wrap_lines(text: str, max_chars: int, max_lines: int = 2) -> list[str]:
    """Greedily wrap ``text`` into at most ``max_lines`` lines of ~``max_chars`` each.

    A word longer than a line still takes its own line; when the line budget runs out the
    rest is crammed onto the last line and truncated with an ellipsis (so the wrap is
    bounded — the layout reserves room for ``max_lines``).
    """
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for i, word in enumerate(words):
        candidate = f"{cur} {word}".strip()
        if not cur or len(candidate) <= max_chars:
            cur = candidate
        elif len(lines) + 1 < max_lines:
            lines.append(cur)
            cur = word
        else:  # last allowed line: cram the remainder and ellipsize
            lines.append(_truncate(" ".join([cur] + words[i:]), max_chars))
            cur = ""
            break
    if cur:
        lines.append(cur)
    return lines or [""]


def _meta_wrapped(x: float, label: str, detail: str, box_w: float) -> str:
    """The metadata wrapped to the box width as stacked ``<tspan>`` lines (id bold on line 1)."""
    full = f"{label} · {detail}" if label and detail else (label or detail)
    max_chars = max(8, int((box_w - 2 * _SCORE_PAD) / _META_CHAR_W))
    parts = []
    for i, line in enumerate(_wrap_lines(full, max_chars)):
        dy = ' dy="13"' if i else ""
        if i == 0 and label and line.startswith(label):
            inner = f'<tspan class="pd-meta-id">{escape(label)}</tspan>' + escape(
                line[len(label) :]
            )
        else:
            inner = escape(line)
        parts.append(f'<tspan x="{x:.0f}"{dy}>{inner}</tspan>')
    return "".join(parts)


def render_layout(
    stage: Stage,
    layout: Layout,
    timezone: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
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
            f'<text class="pd-header" x="{header.cx:.0f}" y="{header.cy:.0f}">'
            f"{escape(header.name)}</text>"
        )

    for conn in layout.connectors:
        d = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in conn.points)
        out.append(f'<path class="pd-link" d="{d}"/>')

    flag = stage.render.crest_shape == "flag"
    show_meta = stage.render.show_metadata
    for pm in layout.matches:
        if show_meta:
            label, detail = meta_parts(
                pm.match, stage.render.dt_format, timezone, language
            )
        else:
            label, detail = "", ""
        _match(
            out, pm, stage.render.max_label_chars, layout.box_width, flag, label, detail
        )

    out.append("</svg>")
    return "\n".join(out)


def render_svg(
    stage: Stage, timezone: Optional[str] = None, language: Optional[str] = None
) -> str:
    """Render the knockout stage to a self-contained SVG document string.

    ``timezone`` is an optional zone name (e.g. ``"America/Montevideo"``) the metadata
    datetimes (assumed GMT) are converted to before rendering. ``language`` is the locale
    Babel formats those datetimes in (e.g. ``"es"`` -> Spanish weekday/month names);
    ``None`` leaves them in English. It localizes only the dates here — the generated
    labels are translated upstream by ``KnockoutStage.translate`` at build time.
    """
    return render_layout(
        stage, compute_layout(stage, timezone, language), timezone, language
    )
