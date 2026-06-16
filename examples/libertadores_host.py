"""Example host integration for the Copa Libertadores knockout stage.

In ``libertadores-2026.json`` the first tie's legs carry only a ``ref`` (the id of the
real game) instead of inline scores. This module plays the part of the host system that
resolves those refs: :class:`LibertadoresDiagram` reads the games from a sibling
``example_data.json`` (indexed by game id) and returns each one from ``get_match`` as a
flat game dict (``team1``/``goals1``/``team2``/``goals2``, local first). In a real
deployment that lookup would be a database query.

It also demonstrates **i18n** (``translate``) and the **timezone** conversion — but those
are decisions of *whoever renders*, not of this host, so the caller passes them to
``render`` (the ``__main__`` below renders in Spanish and ``America/Montevideo`` time,
where every Conmebol venue here — Brazil, Argentina, Uruguay — sits at GMT-3). The host
only supplies the *translations*; it does not pick the language or the zone.

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

    # Placeholders are a defined concept (the library's own vocabulary: "winner", "tbd"),
    # so their translations get a dedicated table; the renderer routes to it via the
    # "_placeholder" path. The renderer composes the id, so the word alone suffices
    # ("Ganador" -> "Ganador SF1").
    _TRANS_PLACEHOLDERS = {"es": {"winner": "Ganador", "tbd": "A definir"}}
    # Everything else (here, the document's round names) is translated by its own value;
    # this table is generic, not round-name specific.
    _TRANS = {
        "es": {
            "Quarterfinals": "Cuartos de final",
            "Semifinals": "Semifinales",
            "Final": "Final",
        },
    }

    def __init__(self, document: Optional[dict] = None) -> None:
        super().__init__(document if document is not None else _load_json(DOCUMENT))
        # Real games keyed by id; JSON object keys are strings, hence the str() below.
        self._games = _load_json(DATA)

    def get_match(self, ref: Id) -> GameData:
        return self._games.get(str(ref))

    def translate(self, path: str, value: str, language: str) -> Optional[str]:
        # Placeholders have their own table (routed by path); anything else translates by
        # value. The renderer only calls this for a target language other than English.
        table = self._TRANS_PLACEHOLDERS if path == "_placeholder" else self._TRANS
        return table.get(language, {}).get(value)


if __name__ == "__main__":
    import sys

    # Language and timezone are the caller's choice; this demo renders the Conmebol stage
    # in Spanish and local (GMT-3) time.
    sys.stdout.write(
        LibertadoresDiagram().render(language="es", timezone="America/Montevideo")
    )
