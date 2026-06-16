"""Example host integration that resolves national-team flags for the World Cup.

The companion to ``copa_rio_host.py``: where that one looks each side up by its integer
``id{n}``, this one resolves by *name*, because ``knockout-8.json`` carries no ids — its
sides are national teams identified by their plain names. :class:`WorldCupFlagsDiagram`
reads a sibling ``flag_data.json`` (a team-name -> flag-file lookup) and returns each
side's flag from ``get_crest``; the unresolved ``winnerof`` placeholders get none, so
they show that rows without an image keep their layout. In a real deployment that lookup
would be a database query and the value a URL.

The flags under ``flags/`` are public-domain SVGs from Wikimedia Commons (national flags
are government works / simple designs, below the threshold of originality). The paths are
relative, so render from inside ``examples/`` for an image viewer (or ``rsvg-convert`` /
a browser) to resolve them::

    PYTHONPATH=../src python world_cup_flags_host.py > world-cup.svg          # the diagram
    PYTHONPATH=../src python world_cup_flags_host.py html > world-cup.html    # the table

Resolving by name here (rather than by ``id`` as ``copa_rio_host.py`` does) is the
trade-off the manual calls out: it is the only key this id-less document offers, and it
ties the lookup to the document's exact spelling.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage
from matamata.model import Id

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "knockout-8.json")
FLAGS = os.path.join(_HERE, "flag_data.json")


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class WorldCupFlagsDiagram(KnockoutStage):
    """Resolves each side's flag from its team name against ``flag_data.json``."""

    def __init__(self, document: Optional[dict] = None) -> None:
        super().__init__(document if document is not None else _load_json(DOCUMENT))
        self._flags = _load_json(FLAGS)

    def get_crest(
        self, team_id: Optional[Id], team_name: Optional[str]
    ) -> Optional[str]:
        if team_name is None:
            return None
        return self._flags.get(team_name)


if __name__ == "__main__":
    import sys

    # Pass the format only if given on the CLI, so "svg" stays the library's default.
    opts: dict[str, str] = {}
    if len(sys.argv) > 1:
        opts["fmt"] = sys.argv[1]
    sys.stdout.write(WorldCupFlagsDiagram().render(**opts))
