"""Example host that themes the render with custom CSS, via :meth:`get_style`.

``knockout-8.json`` is otherwise a plain base-loader document; this host adds nothing but
a :meth:`get_style` override, to demonstrate styling the output without touching the JSON
or the library. The hook returns extra CSS that is appended **after** the renderer's
built-in styles, so its rules cascade over the defaults — here a fixed "midnight" palette
that overrides both the light defaults *and* the default ``@media`` dark block (the colours
are restated unconditionally, so a static rasterizer like ``rsvg-convert`` gets it too).

The CSS is **per-format**: the SVG colours via ``fill``/``stroke``, the HTML table via
``color``/``background`` — so ``get_style`` returns a different block for each ``fmt``::

    PYTHONPATH=../src python styled_host.py            # the themed diagram (svg)
    PYTHONPATH=../src python styled_host.py html       # the themed table
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "knockout-8.json")

# A fixed "midnight" palette. Both blocks target the shared pd-* classes; because they are
# appended after the defaults (and after the default dark @media block), these unconditional
# rules win at equal specificity in any colour scheme.
_SVG_CSS = """
  .pd-bg { fill: #0b1020; }
  .pd-title { fill: #fbbf24; }
  .pd-season { fill: #9aa4c0; }
  .pd-header { fill: #c7d2fe; }
  .pd-meta { fill: #7c89b3; }
  .pd-box { fill: #161e3a; stroke: #2a3566; }
  .pd-divider { stroke: #2a3566; }
  .pd-team { fill: #e6e9f5; }
  .pd-score { fill: #e6e9f5; }
  .pd-win .pd-team, .pd-win .pd-score { fill: #fbbf24; }
  .pd-crest-frame { stroke: #2a3566; }
  .pd-link { stroke: #2a3566; }
""".strip("\n")

_HTML_CSS = """
  .pd-stage { color: #e6e9f5; background: #0b1020; }
  .pd-title { color: #fbbf24; }
  .pd-season { color: #9aa4c0; }
  .pd-header { color: #c7d2fe; }
  .pd-meta { color: #7c89b3; }
  .pd-team, .pd-score { color: #e6e9f5; }
  .pd-match { background: #161e3a; border-color: #2a3566; }
  .pd-side + .pd-side td { border-top-color: #2a3566; }
  .pd-vs { color: #7c89b3; }
  .pd-grid .pd-match-row td { border-color: #2a3566; background: #161e3a; }
  .pd-grid .pd-match-row td:first-child,
  .pd-grid .pd-match-row td:last-child { border-color: #2a3566; }
  .pd-win td, .pd-grid .pd-win, .pd-win .pd-team, .pd-win .pd-score { color: #fbbf24; }
""".strip("\n")


class StyledDiagram(KnockoutStage):
    """Themes the render with a fixed midnight palette (per format)."""

    def __init__(self, document: Optional[dict] = None) -> None:
        if document is None:
            with open(DOCUMENT, encoding="utf-8") as fh:
                document = json.load(fh)
        super().__init__(document)

    def get_style(self, fmt: str) -> Optional[str]:
        return _SVG_CSS if fmt == "svg" else _HTML_CSS


if __name__ == "__main__":
    import sys

    # Pass the format only if given on the CLI, so "svg" stays the library's default.
    opts: dict = {}
    if len(sys.argv) > 1:
        opts["fmt"] = sys.argv[1]
    sys.stdout.write(StyledDiagram().render(**opts))
