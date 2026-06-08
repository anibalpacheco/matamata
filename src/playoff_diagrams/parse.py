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


def _parse_side(data: dict, n: str, where: str, has_legs: bool) -> Slot:
    """Build one side of a match from its flat fields (``n`` is "1" or "2").

    A side is described at match level: ``winnerof{n}`` wires the bracket, ``team{n}``
    (with optional ``seed{n}``/``id{n}``) names a known/advancing team. When the match
    has legs the team name comes from the legs, so the identity fields are rejected here;
    only the wiring is allowed. A side with neither name nor wiring renders as "TBD".
    """
    winner_of = data.get(f"winnerof{n}")
    team = data.get(f"team{n}")
    seed = data.get(f"seed{n}")
    team_id = data.get(f"id{n}")
    if has_legs and (team is not None or seed is not None or team_id is not None):
        raise BracketError(
            f"{where} has legs, so side {n} must not set 'team{n}'/'seed{n}'/'id{n}'; "
            f"the team comes from the legs"
        )
    return Slot(team=team, team_id=team_id, seed=seed, winner_of=winner_of)


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
_GAME_REQUIRED = ("team1", "goals1", "team2", "goals2")


def _parse_leg(data: dict, where: str) -> tuple[Leg, Optional[dict]]:
    """Return the leg plus its inline game data (``None`` for a host-resolved leg).

    A leg is either host-resolved (only a ``ref``) or self-contained (the flat game
    ``team1``/``goals1``/``team2``/``goals2`` with optional ``pen1``/``pen2``). The
    inline game is oriented onto the tie by :func:`apply_game`; a ``ref`` leg is left for
    the host's ``get_match`` to fill.
    """
    has_ref = "ref" in data
    has_inline = any(key in data for key in _GAME_KEYS)
    if has_ref and has_inline:
        raise BracketError(
            f"leg in {where} carries a 'ref' together with inline game data; with a "
            f"'ref' the teams and scores come from the host's get_match, so "
            f"'team1'/'goals1'/... must be omitted"
        )
    if has_ref:
        return Leg(ref=data["ref"]), None
    for key in _GAME_REQUIRED:
        if key not in data:
            raise BracketError(
                f"leg in {where} must have 'team1', 'goals1', 'team2' and 'goals2' "
                f"(or a 'ref')"
            )
    return Leg(), {key: data.get(key) for key in _GAME_KEYS}


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
    raw_legs = data.get("legs", [])
    has_legs = bool(raw_legs)
    # Sides are described by flat match-level fields: 1 = top (home), 2 = bottom (away).
    home = _parse_side(data, "1", where, has_legs)
    away = _parse_side(data, "2", where, has_legs)
    match = Match(
        id=mid,
        home=home,
        away=away,
        legs=[],
        winner=_parse_winner(data.get("winner"), where),
    )
    for raw in raw_legs:
        leg, game = _parse_leg(raw, where)
        match.legs.append(leg)
        if game is not None:
            # Inline legs are oriented now; ref legs wait for get_match (see diagram.py).
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
