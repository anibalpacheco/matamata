"""Example host integration that resolves team crests for the Copa Río de la Plata.

This short invitational starts at the semifinals and mixes two Río de la Plata clubs
(Estudiantes, Platense) with two invited foreign sides (Internacional, Athletic Club) —
a common format for these tournaments. Each side in ``copa-rio-de-la-plata-2026.json``
carries an integer ``id{n}`` on its leg; this module plays the part of the host system
that turns those ids into crest images: :class:`CopaRioDiagram` reads a sibling
``crest_data.json`` (a team-id -> crest-file lookup) and returns each match from
``get_crest``. In a real deployment that lookup would be a database query, and the value
would typically be a URL.

The crests under ``crests/`` are public-domain logos from Wikimedia Commons (each tagged
``{{PD-textlogo}}`` — simple shapes/text, below the threshold of originality). The paths
are relative, so render from inside ``examples/`` for an image viewer (or ``rsvg-convert``
/ a browser) to resolve them::

    PYTHONPATH=../src python copa_rio_host.py > copa-rio.svg          # the diagram
    PYTHONPATH=../src python copa_rio_host.py html > copa-rio.html    # the table

Resolving by ``id`` rather than the display name is deliberate: it is what the manual
recommends, and it sidesteps name-vs-source mismatches (accents, short forms).
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage
from matamata.model import Id

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "copa-rio-de-la-plata-2026.json")
CRESTS = os.path.join(_HERE, "crest_data.json")


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class CopaRioDiagram(KnockoutStage):
    """Resolves each side's crest from its ``id{n}`` against ``crest_data.json``.

    It also localizes the round names to Spanish (the generated placeholders too, though
    this fully-resolved stage shows none), so the caller can render it with
    ``language="es"`` — fitting for a Río de la Plata cup, and the foil to the World Cup's
    English render when comparing how Babel localizes the metadata weekday/month names.
    """

    # Round names by their (English) value; placeholders under "_placeholder" by key.
    _TRANS_PLACEHOLDERS = {"es": {"winner": "Ganador", "tbd": "A definir"}}
    _TRANS = {"es": {"Semifinals": "Semifinales", "Final": "Final"}}

    def __init__(self, document: Optional[dict] = None) -> None:
        super().__init__(document if document is not None else _load_json(DOCUMENT))
        # Crests keyed by team id; JSON object keys are strings, hence the str() below.
        self._crests = _load_json(CRESTS)

    def get_crest(
        self, team_id: Optional[Id], team_name: Optional[str]
    ) -> Optional[str]:
        if team_id is None:
            return None
        return self._crests.get(str(team_id))

    def translate(self, path: str, value: str, language: str) -> Optional[str]:
        table = self._TRANS_PLACEHOLDERS if path == "_placeholder" else self._TRANS
        return table.get(language, {}).get(value)


if __name__ == "__main__":
    import sys

    # The caller picks the language; this Río de la Plata cup's demo renders in Spanish.
    # Pass the format only if given on the CLI, so "svg" stays the library's default.
    opts = {"language": "es"}
    if len(sys.argv) > 1:
        opts["fmt"] = sys.argv[1]
    sys.stdout.write(CopaRioDiagram().render(**opts))
