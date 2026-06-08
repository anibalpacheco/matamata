"""Host integration point: a subclassable bracket diagram.

The library is a pure renderer. To plug a host system into it, subclass
:class:`PlayoffDiagram`, override the hooks you need, instantiate it with the JSON
document and call :meth:`render`::

    class MyDiagram(PlayoffDiagram):
        def get_match(self, ref):
            game = my_db.fetch(ref)
            return [
                {"team": game.home_team, "goals": game.home_goals, "pens": game.home_pens},
                {"team": game.away_team, "goals": game.away_goals, "pens": game.away_pens},
            ]

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
from typing import Any, Optional, Sequence

from .model import Bracket, Id, Match, Pens, RenderOptions, Slot
from .parse import parse_bracket, render_options
from .render import render_svg

# What get_match returns: a positional pair [home_side, away_side]. By convention the
# first element is the *home/local* of that game and the second the *away/visitor*.
# Each side is a mapping that may carry "team", "goals" and "pens" (all optional).
Side = dict[str, Any]
GameData = Optional[Sequence[Optional[Side]]]


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

        Called once per leg that carries a ``ref``. Return a positional pair
        ``[home_side, away_side]`` (first is the local/home of the game). Each side is a
        dict that may contain ``team`` (str), ``goals`` (int) and ``pens`` (int) — return
        only what you have. Returning ``None`` leaves the leg as the document defines it.
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
            data = self.get_match(leg.ref)  # pylint: disable=assignment-from-none
            if not data:
                continue
            local: Side = data[0] or {}  # pylint: disable=unsubscriptable-object
            visitor: Side = data[1] or {}  # pylint: disable=unsubscriptable-object

            # Orient this game onto the tie's home/away. get_match is local-first, but
            # the local of a second leg is the tie's away side, so match by team name
            # when we already know one side; otherwise take local -> home.
            reversed_ = (
                local.get("team") is not None and local.get("team") == match.away.team
            ) or (
                visitor.get("team") is not None
                and visitor.get("team") == match.home.team
            )
            home_side, away_side = (visitor, local) if reversed_ else (local, visitor)

            _fill_team(match.home, home_side)
            _fill_team(match.away, away_side)
            if "goals" in home_side:
                leg.home = home_side["goals"]
            if "goals" in away_side:
                leg.away = away_side["goals"]
            home_pens, away_pens = home_side.get("pens"), away_side.get("pens")
            if home_pens is not None or away_pens is not None:
                leg.pens = Pens(home=home_pens or 0, away=away_pens or 0)


def _fill_team(slot: Slot, side: Side) -> None:
    """Set a slot's display team from live data, only when it isn't known yet.

    A ``winner_of`` link is kept so the bracket connector still draws.
    """
    if slot.team is None and side.get("team") is not None:
        slot.team = side["team"]
    if slot.team_id is None and side.get("id") is not None:
        slot.team_id = side["id"]
