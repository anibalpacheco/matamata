"""Host integration point: a subclassable bracket diagram.

The library is a pure renderer. To plug a host system into it, subclass
:class:`PlayoffDiagram`, override the hooks you need, instantiate it with the JSON
document and call :meth:`render`::

    class MyDiagram(PlayoffDiagram):
        def get_match(self, ref):
            game = my_db.fetch(ref)
            return {
                "team1": game.home_team, "goals1": game.home_goals, "pen1": game.home_pens,
                "team2": game.away_team, "goals2": game.away_goals, "pen2": game.away_pens,
            }

        def get_tournament(self):
            return championship.name

        def get_season(self):
            return str(championship.year)

    svg = MyDiagram(document).render()

Resolution is automatic: whenever a leg in the document carries a ``ref``,
:meth:`get_match` is called with it. Legs without a ``ref`` are left untouched.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .model import Bracket, Id, Match, RenderOptions
from .parse import apply_game, parse_bracket, render_options
from .render import render_svg

# What get_match returns: one flat game dict, the same shape as an inline leg. "1" is the
# game's local/home side, "2" the away/visitor; keys "team1"/"goals1"/"pen1"/"id1" and
# their "2" counterparts are all optional. Return only what you have.
GameData = Optional[dict[str, Any]]


class PlayoffDiagram:
    """Render a bracket document, with overridable hooks for live host data.

    Override any of :meth:`get_match`, :meth:`get_tournament` and :meth:`get_season`;
    none of them is required. The defaults read straight from the document, so the base
    class renders a self-contained document unchanged.
    """

    def __init__(self, document: Any) -> None:
        self._doc: dict = (
            document if isinstance(document, dict) else json.loads(document)
        )
        # The document's display preferences, available to the hooks (e.g. get_match can
        # consult self.render_config.max_label_chars to decide whether to return short
        # names).
        self.render_config: RenderOptions = render_options(self._doc)

    # ----------------------------------------------------------------- hooks
    def get_match(self, ref: Id) -> GameData:  # pylint: disable=unused-argument
        """Return the live data for a single real game, or ``None``.

        Called once per leg that carries a ``ref``. Return one flat game dict, local
        first: ``team1``/``goals1``/``pen1``/``id1`` for the game's home side and the
        ``2`` counterparts for the away side — all optional, so return only what you
        have. Returning ``None`` leaves the leg as the document defines it.
        """
        return None

    def get_tournament(self) -> Optional[str]:
        """Return the tournament name. Defaults to the document's ``tournament``."""
        return self._doc.get("tournament")

    def get_season(self) -> Optional[str]:
        """Return the season label. Defaults to the document's ``season``."""
        return self._doc.get("season")

    # ----------------------------------------------------------------- build
    def build(self) -> Bracket:
        """Parse the document, hydrate it from the hooks and return the model."""
        bracket = parse_bracket(self._doc)
        for rnd in bracket.rounds:
            for match in rnd.matches:
                self._hydrate_match(match)
        tournament = self.get_tournament()
        if tournament is not None:
            bracket.tournament = tournament
        bracket.season = self.get_season()
        return bracket

    def render(self) -> str:
        """Render the bracket to a self-contained SVG document string."""
        return render_svg(self.build())

    # --------------------------------------------------------------- hydrate
    def _hydrate_match(self, match: Match) -> None:
        for leg in match.legs:
            if leg.ref is None:
                continue
            # get_match is an overridable hook; the base returns None, so pylint
            # follows that literal return rather than the GameData annotation.
            game = self.get_match(leg.ref)  # pylint: disable=assignment-from-none
            if not game:
                continue
            # Same orientation as an inline leg, shared with the parser.
            apply_game(match, leg, game)
