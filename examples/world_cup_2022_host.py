"""Example host that resolves national-team flags for the 2022 World Cup knockout.

Renders the finished Qatar 2022 knockout from the Round of 16 to the final plus the
third-place match, the real results and the symmetric (default) layout — the strongest
single example of what the library draws. Like ``copa_rio_host.py`` it resolves each side's
crest from its identity, but by *name* (since ``world-cup-2022.json`` carries no ids, the
only key it offers) rather than by integer ``id{n}``; the lookup
``world_cup_2022_flags.json`` is this host's own fixture.

The flags under ``flags/`` are public-domain SVGs from Wikimedia Commons. The paths are
relative, so render from inside ``examples/`` for ``rsvg-convert`` / a browser to resolve
them::

    PYTHONPATH=../src python world_cup_2022_host.py > world-cup-2022.svg          # the diagram
    PYTHONPATH=../src python world_cup_2022_host.py html > world-cup-2022.html    # the table
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage
from matamata.model import Id

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "world-cup-2022.json")
FLAGS = os.path.join(_HERE, "world_cup_2022_flags.json")


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class WorldCup2022Diagram(KnockoutStage):
    """Resolves each side's flag from its team name against ``world_cup_2022_flags.json``."""

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
    sys.stdout.write(WorldCup2022Diagram().render(**opts))
