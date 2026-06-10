"""Model tournament knockout stages in JSON format and render the schedule in SVG
or html table format."""

from .diagram import KnockoutStage
from .model import Leg, Match, Pens, Round, Slot, Stage
from .parse import load_stage, parse_stage
from .render import render_svg

__all__ = [
    "Stage",
    "Match",
    "Round",
    "Slot",
    "Leg",
    "Pens",
    "KnockoutStage",
    "load_stage",
    "parse_stage",
    "render_svg",
]
