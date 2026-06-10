"""Load a bracket document (dict / JSON) into the dataclass model.

Structural validation against ``spec/schema.json`` is available via
:func:`validate_document` when the optional ``jsonschema`` package is installed; the
parser itself depends only on the standard library and raises clear errors.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .model import Bracket, Id, Leg, Match, Pens, RenderOptions, Round, Slot

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "spec", "schema.json"
)


class BracketError(ValueError):
    """Raised when a document cannot be parsed into the model."""


def _require(obj: dict, key: str, where: str) -> Any:
    if key not in obj:
        raise BracketError(f"missing '{key}' in {where}")
    return obj[key]


def _parse_side(data: dict, n: str) -> Slot:
    """Build one side of a match from its flat fields (``n`` is "1" or "2").

    A side is described at match level: ``winnerof{n}`` wires the bracket, ``team{n}``
    (with optional ``seed{n}``/``id{n}``) names a known/advancing team. Legs fill in
    whatever the match level leaves unset (see ``_fill_team``), so both may name the
    teams; the match-level name wins. A side with neither name nor wiring renders as
    "TBD".
    """
    return Slot(
        team=data.get(f"team{n}"),
        team_id=data.get(f"id{n}"),
        seed=data.get(f"seed{n}"),
        winner_of=data.get(f"winnerof{n}"),
    )


def _parse_winner(value: Any, where: str) -> Optional[str]:
    """Map the document's ``winner`` (1 = top side, 2 = bottom) onto the model."""
    if value is None:
        return None
    if value in (1, "1"):
        return "home"
    if value in (2, "2"):
        return "away"
    raise BracketError(f"{where} 'winner' must be 1 (top) or 2 (bottom)")


# The flat keys of a played game, as carried by an inline leg and returned by
# PlayoffDiagram.get_match. "1" is that game's local (home) side, "2" the visitor.
_GAME_KEYS = ("team1", "goals1", "id1", "pen1", "team2", "goals2", "id2", "pen2")


def _parse_leg(data: dict) -> tuple[Leg, Optional[dict]]:
    """Return the leg plus its inline game data (``None`` when it carries none).

    Every field is optional: ``{}`` is a scheduled, not-yet-played leg. A ``ref``
    (pointer to the real game, filled by the host's ``get_match`` at render time) may
    coexist with an inline result — live host data wins over the baked values. The
    inline game is oriented onto the tie by :func:`apply_game`; without team names there
    is nothing to match against, so it is read as already tie-oriented (1 = top side).
    """
    leg = Leg(ref=data.get("ref"))
    game = {key: data.get(key) for key in _GAME_KEYS}
    if all(value is None for value in game.values()):
        return leg, None
    return leg, game


def _fill_team(slot: Slot, team: Optional[str], team_id: Optional[Id]) -> None:
    """Set a slot's display team from a game side, only when it isn't known yet.

    A ``winner_of`` link is kept so the bracket connector still draws.
    """
    if slot.team is None and team is not None:
        slot.team = team
    if slot.team_id is None and team_id is not None:
        slot.team_id = team_id


def apply_game(match: Match, leg: Leg, game: dict) -> None:
    """Orient one game onto the tie and fill the match's sides and the leg's scores.

    ``game`` is local-first (team1/goals1 is the game's home). The local of a second leg
    is the tie's *away* side, so when a side's team already matches the tie we flip;
    otherwise local -> tie home. Used for both inline legs (at parse time) and ``ref``
    legs (resolved later through ``get_match``).
    """
    local = (game.get("team1"), game.get("goals1"), game.get("pen1"), game.get("id1"))
    visitor = (game.get("team2"), game.get("goals2"), game.get("pen2"), game.get("id2"))
    reversed_ = (local[0] is not None and local[0] == match.away.team) or (
        visitor[0] is not None and visitor[0] == match.home.team
    )
    home_side, away_side = (visitor, local) if reversed_ else (local, visitor)

    _fill_team(match.home, home_side[0], home_side[3])
    _fill_team(match.away, away_side[0], away_side[3])
    if home_side[1] is not None:
        leg.home = home_side[1]
    if away_side[1] is not None:
        leg.away = away_side[1]
    if home_side[2] is not None or away_side[2] is not None:
        leg.pens = Pens(home=home_side[2] or 0, away=away_side[2] or 0)


def render_options(data: dict) -> RenderOptions:
    """Build :class:`RenderOptions` from a document's optional ``render`` object."""
    r = data.get("render") or {}
    return RenderOptions(
        max_label_chars=r.get("max_label_chars", 22),
        box_width=r.get("box_width", 190),
    )


def _parse_match(data: dict) -> Match:
    mid = _require(data, "id", "match")
    where = f"match '{mid}'"
    settle = data.get("settle")
    if settle not in (None, False):
        raise BracketError(f"{where} 'settle' admits only false")
    # Sides are described by flat match-level fields: 1 = top (home), 2 = bottom (away).
    match = Match(
        id=mid,
        home=_parse_side(data, "1"),
        away=_parse_side(data, "2"),
        legs=[],
        winner=_parse_winner(data.get("winner"), where),
        settle=settle is not False,
    )
    for raw in data.get("legs", []):
        leg, game = _parse_leg(raw)
        match.legs.append(leg)
        if game is not None:
            # Inline data is oriented now; ref legs are topped up by get_match later
            # (see diagram.py).
            apply_game(match, leg, game)
    return match


def parse_bracket(data: dict) -> Bracket:
    """Build a :class:`Bracket` from an already-loaded JSON dict.

    ``tournament`` is optional here: it may be supplied dynamically at render time (see
    :class:`~playoff_diagrams.diagram.PlayoffDiagram`).
    """
    rounds = []
    for rd in _require(data, "rounds", "document"):
        name = _require(rd, "name", "round")
        matches = [_parse_match(m) for m in _require(rd, "matches", f"round '{name}'")]
        rounds.append(Round(name=name, matches=matches))
    render = render_options(data)
    bracket = Bracket(
        rounds=rounds,
        tournament=data.get("tournament", ""),
        season=data.get("season"),
        render=render,
    )
    _check_references(bracket)
    return bracket


def _check_references(bracket: Bracket) -> None:
    """Ensure every ``winner_of`` points at an existing match id."""
    known = set(bracket.matches_by_id())
    for rd in bracket.rounds:
        for match in rd.matches:
            for slot in (match.home, match.away):
                if slot.winner_of is not None and slot.winner_of not in known:
                    raise BracketError(
                        f"match '{match.id}' references unknown match "
                        f"'{slot.winner_of}'"
                    )


def load_bracket(path: str) -> Bracket:
    """Read a JSON file from ``path`` and parse it into a :class:`Bracket`."""
    with open(path, encoding="utf-8") as fh:
        return parse_bracket(json.load(fh))


def validate_document(data: dict) -> None:
    """Validate ``data`` against ``spec/schema.json`` (requires ``jsonschema``)."""
    from jsonschema import Draft202012Validator  # optional dependency

    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator(schema).validate(data)
