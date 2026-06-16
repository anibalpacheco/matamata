"""Example host that localizes the FA Cup pending-draw stage to Spanish.

``facup-pending-draw.json`` is otherwise a plain base-loader document; this host adds
nothing but a :meth:`translate` override, to demonstrate i18n of the **generated
placeholders** — which that stage shows plenty of: the pending draw leaves the semifinals
undrawn (``TBD`` -> "A definir") and the final still points at the semifinal winners
(``Winner SF1`` -> "Ganador SF1") — alongside the round names. No ``get_match`` is needed
(nothing is ref-resolved); the language is the caller's to pass (the gallery passes
``"es"``)::

    PYTHONPATH=../src python facup_host.py            # the diagram, in Spanish
    PYTHONPATH=../src python facup_host.py html       # the table
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "facup-pending-draw.json")


class FaCupDiagram(KnockoutStage):
    """Localizes the generated placeholders and round names to Spanish."""

    # Placeholders (the library's vocabulary) keyed by their key; the renderer composes
    # the id ("Ganador" -> "Ganador SF1").
    _TRANS_PLACEHOLDERS = {"es": {"winner": "Ganador", "tbd": "A definir"}}
    # Everything else, translated by its own value (here the round names).
    _TRANS = {
        "es": {
            "Quarterfinals": "Cuartos de final",
            "Semifinals": "Semifinales",
            "Final": "Final",
        },
    }

    def __init__(self, document: Optional[dict] = None) -> None:
        if document is None:
            with open(DOCUMENT, encoding="utf-8") as fh:
                document = json.load(fh)
        super().__init__(document)

    def translate(self, path: str, value: str, language: str) -> Optional[str]:
        table = self._TRANS_PLACEHOLDERS if path == "_placeholder" else self._TRANS
        return table.get(language, {}).get(value)


if __name__ == "__main__":
    import sys

    # Pass the format only if given on the CLI, so "svg" stays the library's default.
    opts = {"language": "es"}
    if len(sys.argv) > 1:
        opts["fmt"] = sys.argv[1]
    sys.stdout.write(FaCupDiagram().render(**opts))
