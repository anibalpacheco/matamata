"""Example host integration for the Copa Libertadores knockout stage.

In ``libertadores-2026.json`` the first tie's legs carry only a ``ref`` (the id of the
real game) instead of inline scores. This module plays the part of the host system that
resolves those refs: :class:`LibertadoresDiagram` reads the games from a sibling
``example_data.json`` (indexed by game id) and returns each one from ``get_match`` as a
flat game dict (``team1``/``goals1``/``team2``/``goals2``, local first). In a real
deployment that lookup would be a database query.

It also shows the **timezone** conversion: the document's ``dt`` values are GMT, and this
host displays them in ``America/Montevideo`` (every Conmebol venue here — in Brazil,
Argentina and Uruguay — sits at GMT-3, so a single display zone is correct for all). It
does so by defaulting :meth:`render`'s ``timezone`` to that zone, the same knob the CLI
exposes as ``--timezone``.

Run it to render the host-resolved knockout stage to SVG on stdout::

    PYTHONPATH=src python examples/libertadores_host.py > libertadores.svg
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage
from matamata.diagram import GameData
from matamata.model import Id

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "libertadores-2026.json")
DATA = os.path.join(_HERE, "example_data.json")


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class LibertadoresDiagram(KnockoutStage):
    """Resolves each leg's ``ref`` against ``example_data.json``."""

    # The timezone this host displays the GMT metadata datetimes in (see module docstring).
    TIMEZONE = "America/Montevideo"

    def __init__(self, document: Optional[dict] = None) -> None:
        super().__init__(document if document is not None else _load_json(DOCUMENT))
        # Real games keyed by id; JSON object keys are strings, hence the str() below.
        self._games = _load_json(DATA)

    def get_match(self, ref: Id) -> GameData:
        return self._games.get(str(ref))

    def render(
        self,
        fmt: str = "svg",
        language: Optional[str] = None,
        layout: str = "flat",
        timezone: Optional[str] = None,
    ) -> str:
        # Default the display timezone to this host's, while still allowing an override.
        return super().render(fmt, language, layout, timezone or self.TIMEZONE)


if __name__ == "__main__":
    import sys

    sys.stdout.write(LibertadoresDiagram().render())
