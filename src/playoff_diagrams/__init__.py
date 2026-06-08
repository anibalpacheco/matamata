"""Render a football playoff bracket as an SVG from a JSON source document."""

from .diagram import PlayoffDiagram
from .model import Bracket, Leg, Match, Pens, Round, Slot
from .parse import load_bracket, parse_bracket
from .render import render_svg

__all__ = [
    "Bracket",
    "Match",
    "Round",
    "Slot",
    "Leg",
    "Pens",
    "PlayoffDiagram",
    "load_bracket",
    "parse_bracket",
    "render_svg",
]
