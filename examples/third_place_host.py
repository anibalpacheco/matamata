"""Example host that localizes the third-place stage to French.

``third-place.json`` is otherwise a plain base-loader document; this host adds nothing
but a :meth:`translate` override, to demonstrate i18n of the **generated placeholders**
when a third-place match is present — that stage shows both kinds at once: the final
points at the semifinal winners (``Winner SF1`` -> "Vainqueur SF1") and the third-place
match at the **losers** (``Loser SF1`` -> "Perdant SF1"), alongside the round names. The
same ``language`` also drives Babel, so the ``EEEE dd MMMM`` dates render in French
("mardi 14 juillet"). No ``get_match`` is needed (nothing is ref-resolved); the language
is the caller's to pass (the gallery passes ``"fr"``)::

    PYTHONPATH=../src python third_place_host.py            # the diagram, in French
    PYTHONPATH=../src python third_place_host.py html       # the table
"""

from __future__ import annotations

import json
import os
from typing import Optional

from matamata import KnockoutStage

_HERE = os.path.dirname(__file__)
DOCUMENT = os.path.join(_HERE, "third-place.json")


class ThirdPlaceDiagram(KnockoutStage):
    """Localizes the generated placeholders and round names to French."""

    # Placeholders (the library's vocabulary) keyed by their key; the renderer composes
    # the id ("Vainqueur" -> "Vainqueur SF1", "Perdant" -> "Perdant SF1").
    _TRANS_PLACEHOLDERS = {"fr": {"winner": "Vainqueur", "loser": "Perdant"}}
    # Everything else, translated by its own value (here the round names).
    _TRANS = {
        "fr": {
            "Semifinals": "Demi-finales",
            "Final": "Finale",
            "Third place": "Petite finale",
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
    opts = {"language": "fr"}
    if len(sys.argv) > 1:
        opts["fmt"] = sys.argv[1]
    sys.stdout.write(ThirdPlaceDiagram().render(**opts))
