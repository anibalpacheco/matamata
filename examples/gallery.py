"""Dev preview gallery: render every example into one self-contained HTML page.

A repo-only review tool (not a library feature — it lives under ``examples/`` and is
not part of the wheel). It renders **every example** at once, each as the SVG diagram
and the HTML table in both its layouts (flat and stacked), with the example's **source
JSON** shown above so a render can be checked against its document (e.g. the Libertadores
entry's GMT datetimes / English round names vs its localized, tz-shifted render). They can
be eyeballed together (visual-regression review, prepping doc assets). Both rendering paths
are exercised: the base loader
(``load_stage`` + ``render_svg``/``render_html``) for the self-contained documents, and
the three host integrations for the ones that resolve crests, flags or refs.

Light/dark is **not** toggled in the page: each render carries #9's automatic
``@media (prefers-color-scheme: dark)`` rules, so the whole gallery follows the
browser's color-scheme setting. Flip that setting (OS or browser) to see both themes.

Each example is embedded in its own ``<iframe srcdoc=...>`` so its ``<style>`` stays
isolated — the SVG and HTML fragments share ``pd-*`` class names with different meanings,
and isolation makes every render look exactly as it would standalone. The iframes inherit
the parent page's base URL, so the crest/flag relative paths resolve as long as the page
is written inside ``examples/`` (the default).

Run it from inside ``examples/`` so those relative asset paths resolve::

    PYTHONPATH=../src python gallery.py            # writes gallery.html here
    PYTHONPATH=../src python gallery.py out.html   # or to a chosen path

Then open the file with ``file://`` in a browser.

The generated ``examples/gallery.html`` is **committed** (it doubles as browsable docs),
so it joins the other rendered artifacts on the sync list: when anything that affects
rendering changes, regenerate it with the command above and commit the result, the same
way the test goldens and the ``docs/`` PNGs are kept in sync. The output is deterministic,
so it only changes when a render does.
"""

from __future__ import annotations

import os
import sys
from typing import Callable
from xml.sax.saxutils import escape

from copa_rio_host import CopaRioDiagram
from libertadores_host import LibertadoresDiagram
from world_cup_flags_host import WorldCupFlagsDiagram

from matamata import KnockoutStage, load_stage, render_html, render_svg

_HERE = os.path.dirname(os.path.abspath(__file__))

# Each spec yields (svg, html_flat, html_stacked) for one example — the HTML table is
# shown in both layouts. Base-loader documents go through load_stage; the host-resolved
# ones through their KnockoutStage subclass so crests, flags and refs are filled (each
# host loads its own fixture — they stay independent).
Builder = Callable[[], "tuple[str, str, str]"]


def _base(filename: str) -> Builder:
    def build() -> "tuple[str, str, str]":
        stage = load_stage(os.path.join(_HERE, filename))
        return (
            render_svg(stage),
            render_html(stage, layout="flat"),
            render_html(stage, layout="stacked"),
        )

    return build


def _host(
    factory: "Callable[[], KnockoutStage]",
    language: "str | None" = None,
    timezone: "str | None" = None,
) -> Builder:
    def build() -> "tuple[str, str, str]":
        diagram = factory()
        return (
            diagram.render("svg", language=language, timezone=timezone),
            diagram.render("html", layout="flat", language=language, timezone=timezone),
            diagram.render(
                "html", layout="stacked", language=language, timezone=timezone
            ),
        )

    return build


SPECS: "list[tuple[str, str, Builder]]" = [
    (
        "knockout-8.json",
        "World Cup round of 8 — host-resolved flags by name (world_cup_flags_host).",
        _host(WorldCupFlagsDiagram),
    ),
    (
        "copa-rio-de-la-plata-2026.json",
        "Copa Río de la Plata — host-resolved club crests by id (copa_rio_host).",
        _host(CopaRioDiagram),
    ),
    (
        "libertadores-2026.json",
        "Copa Libertadores — refs resolved by libertadores_host, and the caller renders it "
        "with i18n (round names → Spanish via translate) and a timezone "
        "(GMT dt → America/Montevideo, −3h). Compare the source JSON to the render: the "
        "document keeps English round names and GMT kickoff times.",
        _host(LibertadoresDiagram, language="es", timezone="America/Montevideo"),
    ),
    (
        "facup-pending-draw.json",
        "FA Cup — a pending draw (absent winnerof: TBD, no connector). Base loader.",
        _base("facup-pending-draw.json"),
    ),
    (
        "facup-drawn.json",
        "FA Cup — the same stage once drawn (plain pairings). Base loader.",
        _base("facup-drawn.json"),
    ),
]

# Wraps one render fragment into a tiny standalone document for an iframe's srcdoc. The
# body background follows the color scheme so the padding around a dark render is dark too.
_FRAME_DOC = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<style>html,body{{margin:0;padding:8px;background:#ffffff;color:#1f2937;}}"
    "@media (prefers-color-scheme: dark){{html,body{{background:#0f172a;}}}}</style>"
    "</head><body>{fragment}</body></html>"
)

_PAGE_HEAD = """<!doctype html>
<!--
  Generated by examples/gallery.py — do NOT edit by hand. Committed on purpose (it
  doubles as browsable docs); regenerate when a render changes. See this page's header
  for the regeneration command.
-->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>matamata — examples gallery</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font-family: sans-serif; background: #ffffff; color: #1f2937; }
  header { padding: 20px 24px; }
  header h1 { margin: 0 0 4px; font-size: 22px; }
  header p { margin: 0 0 10px; color: #6b7280; font-size: 14px; }
  header .regen { font-size: 13px; color: #6b7280; margin: 0; }
  header .regen code { font-family: monospace; background: #f3f4f6; color: #111827;
                       padding: 1px 6px; border-radius: 3px; }
  .example { padding: 16px 24px 28px; border-top: 1px solid #e5e7eb; }
  .example > h2 { font-size: 18px; margin: 0 0 4px; font-family: monospace; }
  .example > .note { margin: 0 0 14px; font-size: 13px; color: #6b7280; }
  details.src { margin: 0 0 16px; }
  details.src > summary { font-size: 11px; text-transform: uppercase;
                          letter-spacing: .05em; color: #6b7280; cursor: pointer; }
  details.src > pre { margin: 8px 0 0; max-height: 320px; overflow: auto; font-size: 12px;
                      line-height: 1.45; background: #f8fafc; color: #111827;
                      border: 1px solid #e5e7eb; border-radius: 4px; padding: 10px 12px; }
  .panes { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
  .pane { flex: 1 1 360px; min-width: 0; }
  /* The table columns are ~20% narrower so the diagram column gets the extra width and
     wide SVG brackets fit without an iframe scrollbar on a wide screen. */
  .pane-table { flex-basis: 288px; }
  .pane-svg { flex-grow: 2; }
  .pane > h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
               color: #6b7280; margin: 0 0 6px; }
  iframe.pane-frame { width: 100%; border: 1px solid #e5e7eb; border-radius: 4px;
                      display: block; }
  @media (prefers-color-scheme: dark) {
    body { background: #0f172a; color: #e5e7eb; }
    header p, header .regen, .pane > h3, .example > .note { color: #94a3b8; }
    header .regen code { background: #1e293b; color: #e5e7eb; }
    .example { border-top-color: #334155; }
    iframe.pane-frame { border-color: #334155; }
    details.src > summary { color: #94a3b8; }
    details.src > pre { background: #1e293b; color: #e5e7eb; border-color: #334155; }
  }
</style>
</head>
<body>
<header>
  <h1>matamata — examples gallery</h1>
  <p>Every example, rendered as the SVG diagram and the HTML table in both layouts
  (flat and stacked), with its source JSON above each so you can check the render against
  the document (e.g. the Copa Libertadores entry shows i18n and timezone: English round
  names and GMT kickoff times in the JSON, Spanish and local time in the render).
  Light/dark follows your browser's color-scheme setting — flip it to see both themes.</p>
  <p class="regen">Generated by <code>examples/gallery.py</code> — regenerate from inside
  <code>examples/</code> with <code>PYTHONPATH=../src python gallery.py</code>.</p>
</header>
"""

_PAGE_TAIL = """
<script>
  // Each render is isolated in an iframe; fit each one to its content's height, and
  // refit when the color scheme changes (a theme switch can reflow the table).
  function fit(frame) {
    try { frame.style.height =
      frame.contentDocument.documentElement.scrollHeight + 'px'; } catch (e) {}
  }
  const frames = document.querySelectorAll('iframe.pane-frame');
  for (const f of frames) f.addEventListener('load', () => fit(f));
  matchMedia('(prefers-color-scheme: dark)').addEventListener(
    'change', () => { for (const f of frames) fit(f); });
</script>
</body>
</html>
"""


def _frame(fragment: str) -> str:
    srcdoc = escape(_FRAME_DOC.format(fragment=fragment), {'"': "&quot;"})
    return f'<iframe class="pane-frame" srcdoc="{srcdoc}"></iframe>'


def _source_json(filename: str) -> str:
    """A collapsible view of the example's source document, to check it against the render
    (e.g. GMT datetimes and English round names here vs the localized, tz-shifted output).
    """
    with open(os.path.join(_HERE, filename), encoding="utf-8") as fh:
        text = fh.read()
    return (
        '<details class="src" open><summary>source JSON</summary>'
        f"<pre>{escape(text)}</pre></details>"
    )


def build_page() -> str:
    parts = [_PAGE_HEAD]
    for filename, note, builder in SPECS:
        svg, html_flat, html_stacked = builder()
        parts.append('<section class="example">')
        parts.append(f"<h2>{escape(filename)}</h2>")
        parts.append(f'<p class="note">{escape(note)}</p>')
        parts.append(_source_json(filename))
        parts.append('<div class="panes">')
        parts.append(
            f'<div class="pane pane-svg"><h3>SVG diagram</h3>{_frame(svg)}</div>'
        )
        parts.append(
            '<div class="pane pane-table"><h3>HTML table — flat</h3>'
            f"{_frame(html_flat)}</div>"
        )
        parts.append(
            '<div class="pane pane-table"><h3>HTML table — stacked</h3>'
            f"{_frame(html_stacked)}</div>"
        )
        parts.append("</div>")
        parts.append("</section>")
    parts.append(_PAGE_TAIL)
    return "\n".join(parts)


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "gallery.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(build_page())
    sys.stderr.write(f"wrote {out_path}\n")


if __name__ == "__main__":
    main()
