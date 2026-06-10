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

The diagram also *maintains* its document: :meth:`PlayoffDiagram.apply_results` writes
played results onto the JSON in place (and, unless told otherwise, settles the winners),
so a host can keep the stored bracket up to date without touching its structure.
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Optional, Union

from .model import Bracket, Id, Match, Pens, RenderOptions, aggregate, pens_of
from .parse import BracketError, _parse_match, apply_game, parse_bracket, render_options
from .render import render_svg

# What get_match returns: one flat game dict, the same shape as an inline leg. "1" is the
# game's local/home side, "2" the away/visitor; keys "team1"/"goals1"/"pen1"/"id1" and
# their "2" counterparts are all optional. Return only what you have.
GameData = Optional[dict[str, Any]]

# What apply_results accepts: the scores of one leg plus exactly one way to find it —
# 'ref' (the leg pointing at that real game) xor 'id' (a match id, with an optional
# 1-based 'leg' number). Unlike GameData, the score keys are tie-oriented: 1 is the
# match's top side, not the game's local.
ResultData = dict[str, Any]
_RESULT_KEYS = frozenset({"ref", "id", "leg", "goals1", "goals2", "pen1", "pen2"})
_SCORE_KEYS = ("goals1", "goals2", "pen1", "pen2")


def _decide(agg: tuple[int, int], pens: Optional[Pens]) -> Optional[int]:
    """Pick a side (1/2) from an aggregate and an optional shootout, or ``None``."""
    home, away = agg
    if home == away and pens is not None:
        home, away = pens.home, pens.away
    if home == away:
        return None
    return 1 if home > away else 2


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

    # --------------------------------------------------------------- results
    def apply_results(
        self, results: Union[ResultData, list[ResultData]], settle: bool = True
    ) -> dict:
        """Write one or more played results onto the document, in place.

        ``results`` is one dict or a list of dicts, each carrying the scores of one leg
        (``goals1``/``goals2``, optional ``pen1``/``pen2`` — **tie-oriented**: 1 is the
        match's top side) plus exactly one way to find that leg:

        - ``ref`` — the leg whose ``ref`` is this real-game id; or
        - ``id`` — a match id, with an optional 1-based ``leg`` number (default 1).
          Missing legs are created, so a result can arrive before the document lists
          its leg.

        Present keys overwrite whatever the leg holds — there is no notion of "already
        played", so a live game can be re-applied as it goes. With ``settle`` (the
        default), every touched match is settled afterwards: its winner is recomputed
        from the data a render would show, written (or removed when undecided), and
        pushed into the match that consumes it via ``winnerof``. A match carrying
        ``"settle": false`` is never settled. Returns the updated document.
        """
        if isinstance(results, dict):
            results = [results]
        touched: dict[str, dict] = {}
        for result in results:
            match_data, leg_data = self._find_leg(result)
            self._write_result(match_data, leg_data, result)
            touched[match_data["id"]] = match_data
        if settle:
            for match_data in touched.values():
                if match_data.get("settle") is not False:
                    self._settle(match_data)
        return self._doc

    def _match_dicts(self) -> Iterator[dict]:
        for rnd in self._doc.get("rounds", []):
            yield from rnd.get("matches", [])

    def _find_leg(self, result: ResultData) -> tuple[dict, dict]:
        """Validate one result dict and return the (match, leg) pair it addresses."""
        unknown = set(result) - _RESULT_KEYS
        if unknown:
            raise BracketError(
                f"result has unknown key(s): {', '.join(sorted(unknown))}"
            )
        for key in _SCORE_KEYS:
            value = result.get(key, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise BracketError(f"result '{key}' must be a non-negative integer")
        if ("ref" in result) == ("id" in result):
            raise BracketError("a result needs exactly one of 'ref' or 'id'")
        if "ref" in result:
            if "leg" in result:
                raise BracketError("'leg' goes with 'id', not with 'ref'")
            return self._leg_by_ref(result["ref"])
        return self._leg_by_number(result["id"], result.get("leg", 1))

    def _leg_by_ref(self, ref: Id) -> tuple[dict, dict]:
        found = [
            (match, leg)
            for match in self._match_dicts()
            for leg in match.get("legs", [])
            if leg.get("ref") == ref
        ]
        if not found:
            raise BracketError(f"no leg carries ref {ref!r}")
        if len(found) > 1:
            raise BracketError(f"ref {ref!r} appears in more than one leg")
        return found[0]

    def _leg_by_number(self, match_id: str, number: Any) -> tuple[dict, dict]:
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise BracketError("'leg' must be a 1-based integer")
        for match in self._match_dicts():
            if match.get("id") == match_id:
                legs = match.setdefault("legs", [])
                while len(legs) < number:
                    legs.append({})
                return match, legs[number - 1]
        raise BracketError(f"no match has id {match_id!r}")

    @staticmethod
    def _write_result(match_data: dict, leg_data: dict, result: ResultData) -> None:
        """Copy the result's scores onto the leg, oriented onto the tie.

        Results are tie-oriented, but a leg that names its teams is game-local-first
        and may list them in the opposite order; writing through such a leg flips the
        keys so the document stays consistent with itself.
        """
        match = _parse_match(match_data)
        flipped = (
            leg_data.get("team1") is not None
            and leg_data.get("team1") == match.away.team
        ) or (
            leg_data.get("team2") is not None
            and leg_data.get("team2") == match.home.team
        )
        sides = (("1", "2"), ("2", "1")) if flipped else (("1", "1"), ("2", "2"))
        for prefix in ("goals", "pen"):
            for source, target in sides:
                if f"{prefix}{source}" in result:
                    leg_data[f"{prefix}{target}"] = result[f"{prefix}{source}"]

    # ---------------------------------------------------------------- settle
    def _settle(self, match_data: dict) -> None:
        """Decide the match from its current data and write the outcome back.

        The data is what a render would show (ref legs included, via ``get_match``):
        aggregate first, penalties on a tied aggregate. No played leg at all means
        nothing to decide, so nothing is touched; a tie with no shootout removes the
        ``winner`` — it is never guessed. The outcome is then pushed into the match
        that consumes this one through ``winnerof``.
        """
        match = _parse_match(match_data)
        self._hydrate_match(match)
        agg = aggregate(match)
        if agg is None:
            return
        winner = _decide(agg, pens_of(match))
        if winner is None:
            match_data.pop("winner", None)
        else:
            match_data["winner"] = winner
        self._advance(match_data["id"], match, winner)

    def _advance(self, match_id: str, match: Match, winner: Optional[int]) -> None:
        """Rewrite the advancing team on every side that consumes this match."""
        slot = None
        if winner is not None:
            slot = match.home if winner == 1 else match.away
        for consumer in self._match_dicts():
            for n in ("1", "2"):
                if consumer.get(f"winnerof{n}") != match_id:
                    continue
                # The consumed side is derived state: clear it, then write what is known.
                consumer.pop(f"team{n}", None)
                consumer.pop(f"id{n}", None)
                if slot is None:
                    continue
                if slot.team is not None:
                    consumer[f"team{n}"] = slot.team
                if slot.team_id is not None:
                    consumer[f"id{n}"] = slot.team_id

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
