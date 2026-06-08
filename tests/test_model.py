"""Unit tests for parsing, display helpers and the PlayoffDiagram hooks."""

import json
import os

import pytest

from playoff_diagrams import PlayoffDiagram, parse_bracket
from playoff_diagrams.model import Leg, Match, Pens, Resolver, Slot, aggregate
from playoff_diagrams.parse import BracketError, validate_document

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


def _match(home_legs, **kw):
    legs = [Leg(h, a) for h, a in home_legs]
    return Match(id="m", home=Slot(team="H"), away=Slot(team="A"), legs=legs, **kw)


# --- display arithmetic (no winner logic) -----------------------------------


def test_aggregate_sums_played_legs():
    assert aggregate(_match([(2, 1), (0, 0)])) == (2, 1)


def test_aggregate_ignores_unplayed_legs():
    m = Match(
        id="m", home=Slot(team="H"), away=Slot(team="A"), legs=[Leg(2, 1), Leg(ref=99)]
    )  # second leg has only a ref
    assert aggregate(m) == (2, 1)


def test_not_played_has_no_aggregate():
    assert aggregate(Match(id="m", home=Slot(team="H"), away=Slot(team="A"))) is None


# --- winner is explicit only ------------------------------------------------


def test_winner_is_taken_from_the_document_field():
    assert _match([(0, 3)], winner="home").winner == "home"


def test_no_winner_is_computed():
    # A clear 3-0 on the pitch is still undecided unless the document says so.
    assert _match([(3, 0)]).winner is None


# --- resolver never computes ------------------------------------------------


def test_winner_of_without_team_is_a_placeholder():
    assert Resolver().label(Slot(winner_of="sf1")) == "Winner SF1"


def test_winner_of_with_resolved_team_shows_the_name():
    assert Resolver().label(Slot(winner_of="sf1", team="Flamengo")) == "Flamengo"


def test_tbd_label():
    assert Resolver().label(Slot(tbd=True)) == "TBD"


def test_unknown_reference_is_rejected():
    data = {
        "tournament": "T",
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {"id": "f", "home": {"winner_of": "ghost"}, "away": {"tbd": True}},
                ],
            },
        ],
    }
    with pytest.raises(BracketError):
        parse_bracket(data)


def test_tournament_is_optional():
    bracket = parse_bracket(
        {
            "rounds": [
                {
                    "name": "Final",
                    "matches": [
                        {"id": "f", "home": {"team": "X"}, "away": {"team": "Y"}}
                    ],
                }
            ]
        }
    )
    assert bracket.tournament == ""


def test_render_option_defaults():
    bracket = parse_bracket(
        {
            "tournament": "T",
            "rounds": [
                {
                    "name": "Final",
                    "matches": [
                        {"id": "f", "home": {"team": "X"}, "away": {"team": "Y"}}
                    ],
                }
            ],
        }
    )
    assert bracket.render.scores == "aggregate"
    assert bracket.render.max_label_chars == 22
    assert bracket.render.box_width == 190


def test_box_width_widens_the_layout():
    from playoff_diagrams.layout import compute_layout

    doc = {
        "rounds": [
            {
                "name": "F",
                "matches": [{"id": "f", "home": {"team": "A"}, "away": {"team": "B"}}],
            }
        ]
    }
    narrow = compute_layout(parse_bracket(doc))
    doc["render"] = {"box_width": 300}
    wide = compute_layout(parse_bracket(doc))
    assert wide.box_width == 300
    assert wide.width > narrow.width


def test_max_label_chars_truncates():
    from playoff_diagrams.render import _truncate

    assert _truncate("Montevideo City Torque", 22) == "Montevideo City Torque"
    assert _truncate("Montevideo City Torque", 18) == "Montevideo City T…"


def test_render_config_exposed_on_diagram():
    diagram = PlayoffDiagram(
        {
            "render": {"max_label_chars": 12},
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {"id": "f", "home": {"team": "A"}, "away": {"team": "B"}}
                    ],
                }
            ],
        }
    )
    assert diagram.render_config.max_label_chars == 12


def test_score_text_modes():
    from playoff_diagrams.layout import _score_text

    m = Match(
        id="m", home=Slot(team="H"), away=Slot(team="A"), legs=[Leg(2, 1), Leg(0, 0)]
    )
    assert _score_text(m, "home", "aggregate") == "2"
    assert _score_text(m, "home", "legs") == "2 0"
    assert _score_text(m, "away", "legs") == "1 0"

    shoot = Match(
        id="m",
        home=Slot(team="H"),
        away=Slot(team="A"),
        legs=[Leg(1, 1), Leg(0, 0, Pens(4, 2))],
    )
    assert _score_text(shoot, "home", "aggregate") == "1 (4)"
    assert _score_text(shoot, "home", "legs") == "1 0 (4)"


# --- PlayoffDiagram hooks ---------------------------------------------------


def test_get_match_fills_a_single_leg():
    class D(PlayoffDiagram):
        def get_match(self, ref):
            assert ref == 1001
            return [{"team": "Peñarol", "goals": 2}, {"team": "Nacional", "goals": 1}]

    bracket = D(
        {
            "rounds": [
                {
                    "name": "Final",
                    "matches": [
                        {
                            "id": "f",
                            "home": {"tbd": True},
                            "away": {"tbd": True},
                            "legs": [{"ref": 1001}],
                        }
                    ],
                }
            ]
        }
    ).build()
    final = bracket.matches_by_id()["f"]
    assert final.home.team == "Peñarol"
    assert final.away.team == "Nacional"
    assert (final.legs[0].home, final.legs[0].away) == (2, 1)


def test_get_match_fills_pens():
    class D(PlayoffDiagram):
        def get_match(self, ref):
            return [
                {"team": "A", "goals": 0, "pens": 4},
                {"team": "B", "goals": 0, "pens": 2},
            ]

    bracket = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {
                            "id": "f",
                            "home": {"tbd": True},
                            "away": {"tbd": True},
                            "legs": [{"ref": 7}],
                        }
                    ],
                }
            ]
        }
    ).build()
    leg = bracket.matches_by_id()["f"].legs[0]
    assert leg.pens.home == 4 and leg.pens.away == 2


def test_get_match_orients_second_leg_by_team():
    # Leg 2 is played at the visitor's venue: its local is the tie's away side.
    class D(PlayoffDiagram):
        def get_match(self, ref):
            if ref == 1:
                return [
                    {"team": "Peñarol", "goals": 2},
                    {"team": "Nacional", "goals": 1},
                ]
            return [{"team": "Nacional", "goals": 0}, {"team": "Peñarol", "goals": 0}]

    bracket = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {
                            "id": "f",
                            "home": {"tbd": True},
                            "away": {"tbd": True},
                            "legs": [{"ref": 1}, {"ref": 2}],
                        }
                    ],
                }
            ]
        }
    ).build()
    m = bracket.matches_by_id()["f"]
    assert m.home.team == "Peñarol" and m.away.team == "Nacional"
    # Both legs are stored in tie orientation: Peñarol then Nacional.
    assert [(leg.home, leg.away) for leg in m.legs] == [(2, 1), (0, 0)]


def test_get_match_returning_none_leaves_the_leg():
    class D(PlayoffDiagram):
        def get_match(self, ref):
            return None

    bracket = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {
                            "id": "f",
                            "home": {"team": "A"},
                            "away": {"team": "B"},
                            "legs": [{"ref": 1}],
                        }
                    ],
                }
            ]
        }
    ).build()
    assert bracket.matches_by_id()["f"].legs[0].played is False


def test_tournament_and_season_overrides():
    class D(PlayoffDiagram):
        def get_tournament(self):
            return "Copa Dinámica"

        def get_season(self):
            return "2027"

    bracket = D(
        {
            "tournament": "Ignored",
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {"id": "f", "home": {"team": "A"}, "away": {"team": "B"}}
                    ],
                }
            ],
        }
    ).build()
    assert bracket.tournament == "Copa Dinámica"
    assert bracket.season == "2027"


def test_diagram_accepts_a_json_string():
    doc = json.dumps(
        {
            "tournament": "T",
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {"id": "f", "home": {"team": "A"}, "away": {"team": "B"}}
                    ],
                }
            ],
        }
    )
    assert PlayoffDiagram(doc).render().startswith("<svg")


@pytest.mark.parametrize("name", ["libertadores-2026.json", "knockout-8.json"])
def test_examples_match_schema(name):
    pytest.importorskip("jsonschema")
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        validate_document(json.load(fh))
