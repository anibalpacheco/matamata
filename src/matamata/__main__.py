"""Command-line entry point: render a knockout stage JSON document to SVG or HTML.

Usage::

    matamata examples/libertadores-2026.json -o out.svg
    matamata examples/knockout-8.json -o schedule.html   # format inferred
    python -m matamata examples/knockout-8.json -f html > out.html
"""

from __future__ import annotations

import argparse
import sys

from .parse import StageError, load_stage
from .render import render_svg
from .render_html import render_html

_RENDERERS = {"svg": render_svg, "html": render_html}


def _format_of(args: argparse.Namespace) -> str:
    """The explicit ``--format``, or the one the output extension implies (svg)."""
    if args.format:
        return args.format
    if args.output and args.output.lower().endswith((".html", ".htm")):
        return "html"
    return "svg"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="matamata",
        description="Render a tournament knockout stage JSON document to SVG "
        "or an HTML table.",
    )
    parser.add_argument("input", help="path to a knockout stage JSON document")
    parser.add_argument(
        "-o",
        "--output",
        help="output path (defaults to standard output)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=sorted(_RENDERERS),
        help="output format (defaults to what the output extension implies, or svg)",
    )
    parser.add_argument(
        "--layout",
        choices=("flat", "stacked"),
        default="flat",
        help="HTML table layout (default flat); ignored for svg",
    )
    parser.add_argument(
        "--timezone",
        help="zone name (e.g. America/Montevideo) the GMT metadata datetimes "
        "are converted to before rendering",
    )
    args = parser.parse_args(argv)

    try:
        stage = load_stage(args.input)
        fmt = _format_of(args)
        rendered = (
            render_html(stage, layout=args.layout, timezone=args.timezone)
            if fmt == "html"
            else render_svg(stage, timezone=args.timezone)
        )
    except (StageError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
