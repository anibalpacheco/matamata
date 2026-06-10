"""Command-line entry point: render a knockout stage JSON document to SVG.

Usage::

    matamata examples/libertadores-2026.json -o out.svg
    python -m matamata examples/knockout-8.json > out.svg
"""

from __future__ import annotations

import argparse
import sys

from .parse import StageError, load_stage
from .render import render_svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="matamata",
        description="Render a tournament knockout stage JSON document to SVG.",
    )
    parser.add_argument("input", help="path to a knockout stage JSON document")
    parser.add_argument(
        "-o",
        "--output",
        help="output SVG path (defaults to standard output)",
    )
    args = parser.parse_args(argv)

    try:
        svg = render_svg(load_stage(args.input))
    except (StageError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(svg)
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
