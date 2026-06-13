"""Unit tests for parsing, display helpers and the KnockoutStage hooks."""

import json
import os

import pytest

from matamata import KnockoutStage, parse_stage
from matamata.model import Leg, Match, Pens, Resolver, Slot, aggregate
from matamata.parse import StageError, validate_document

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


def test_pending_draw_side_renders_tbd_without_a_connector():
    # When the next round is redrawn from the winners, no advancement path exists
    # beforehand: the hold is simply omitting winnerof{n}. The side shows TBD and
    # no connector is drawn until the draw is written into the document.
    from matamata.layout import compute_layout

    doc = {
        "rounds": [
            {
                "name": "SF",
                "matches": [
                    {"id": "sf1", "team1": "A", "team2": "B"},
                    {"id": "sf2", "team1": "C", "team2": "D"},
                ],
            },
            {"name": "F", "matches": [{"id": "f", "winnerof1": "sf1"}]},
        ]
    }
    layout = compute_layout(parse_stage(doc))
    assert len(layout.connectors) == 1  # only the linked side connects
    final = layout.matches[-1]
    assert final.home.label == "Winner SF1"
    assert final.away.label == "TBD"

    del doc["rounds"][1]["matches"][0]["winnerof1"]
    layout = compute_layout(parse_stage(doc))
    assert not layout.connectors
    final = layout.matches[-1]
    assert final.home.label == "TBD"


def test_unknown_reference_is_rejected():
    data = {
        "tournament": "T",
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {"id": "f", "winnerof1": "ghost"},
                ],
            },
        ],
    }
    with pytest.raises(StageError):
        parse_stage(data)


def test_ref_leg_keeps_its_baked_result():
    # A ref may coexist with a baked result; with no host data it is what gets shown.
    data = {
        "rounds": [
            {
                "name": "Final",
                "matches": [
                    {"id": "f", "legs": [{"ref": 7, "goals1": 2, "goals2": 1}]},
                ],
            }
        ],
    }
    leg = parse_stage(data).matches_by_id()["f"].legs[0]
    assert leg.ref == 7
    assert (leg.home, leg.away) == (2, 1)


def test_get_match_wins_over_a_baked_result():
    class D(KnockoutStage):
        def get_match(self, ref):
            return {"goals1": 3, "goals2": 0}

    stage = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {"id": "f", "legs": [{"ref": 7, "goals1": 2, "goals2": 1}]},
                    ],
                }
            ]
        }
    ).build()
    leg = stage.matches_by_id()["f"].legs[0]
    assert (leg.home, leg.away) == (3, 0)


def test_partial_leg_parses_as_unplayed():
    data = {
        "rounds": [
            {
                "name": "F",
                "matches": [
                    {"id": "f", "legs": [{"team1": "A", "goals1": 2}, {}]},
                ],
            }
        ]
    }
    match = parse_stage(data).matches_by_id()["f"]
    assert [leg.played for leg in match.legs] == [False, False]
    assert match.home.team == "A"


def test_nameless_leg_is_tie_oriented():
    # Without team names there is nothing to match, so goals1 is the top side's.
    data = {
        "rounds": [
            {
                "name": "F",
                "matches": [
                    {
                        "id": "f",
                        "team1": "A",
                        "team2": "B",
                        "legs": [{"goals1": 1, "goals2": 0}],
                    }
                ],
            }
        ]
    }
    match = parse_stage(data).matches_by_id()["f"]
    assert (match.home.team, match.away.team) == ("A", "B")
    assert (match.legs[0].home, match.legs[0].away) == (1, 0)


def test_named_leg_orients_against_match_level_teams():
    data = {
        "rounds": [
            {
                "name": "F",
                "matches": [
                    {
                        "id": "f",
                        "team1": "A",
                        "team2": "B",
                        "legs": [
                            {"team1": "B", "goals1": 1, "team2": "A", "goals2": 0}
                        ],
                    }
                ],
            }
        ]
    }
    leg = parse_stage(data).matches_by_id()["f"].legs[0]
    assert (leg.home, leg.away) == (0, 1)


def test_settle_admits_only_false():
    def doc(value):
        return {
            "rounds": [
                {"name": "F", "matches": [{"id": "f", "settle": value}]},
            ]
        }

    assert parse_stage(doc(False)).matches_by_id()["f"].settle is False
    with pytest.raises(StageError, match="settle"):
        parse_stage(doc(True))


def test_tournament_is_optional():
    stage = parse_stage(
        {
            "rounds": [
                {
                    "name": "Final",
                    "matches": [{"id": "f", "team1": "X", "team2": "Y"}],
                }
            ]
        }
    )
    assert stage.tournament == ""


def test_render_option_defaults():
    stage = parse_stage(
        {
            "tournament": "T",
            "rounds": [
                {
                    "name": "Final",
                    "matches": [{"id": "f", "team1": "X", "team2": "Y"}],
                }
            ],
        }
    )
    assert stage.render.max_label_chars == 22
    assert stage.render.box_width == 190


def test_box_width_widens_the_layout():
    from matamata.layout import compute_layout

    doc = {
        "rounds": [
            {
                "name": "F",
                "matches": [{"id": "f", "team1": "A", "team2": "B"}],
            }
        ]
    }
    narrow = compute_layout(parse_stage(doc))
    doc["render"] = {"box_width": 300}
    wide = compute_layout(parse_stage(doc))
    assert wide.box_width == 300
    assert wide.width > narrow.width


def test_max_label_chars_truncates():
    from matamata.render import _truncate

    assert _truncate("Montevideo City Torque", 22) == "Montevideo City Torque"
    assert _truncate("Montevideo City Torque", 18) == "Montevideo City T…"


def test_render_config_exposed_on_diagram():
    diagram = KnockoutStage(
        {
            "render": {"max_label_chars": 12},
            "rounds": [
                {
                    "name": "F",
                    "matches": [{"id": "f", "team1": "A", "team2": "B"}],
                }
            ],
        }
    )
    assert diagram.render_config.max_label_chars == 12


def test_score_text_shows_each_leg():
    from matamata.model import score_text as _score_text

    single = Match(id="m", home=Slot(team="H"), away=Slot(team="A"), legs=[Leg(3, 0)])
    assert _score_text(single, "home") == "3"

    two = Match(
        id="m", home=Slot(team="H"), away=Slot(team="A"), legs=[Leg(2, 1), Leg(0, 0)]
    )
    assert _score_text(two, "home") == "2 0"
    assert _score_text(two, "away") == "1 0"

    shoot = Match(
        id="m",
        home=Slot(team="H"),
        away=Slot(team="A"),
        legs=[Leg(1, 1), Leg(0, 0, Pens(4, 2))],
    )
    assert _score_text(shoot, "home") == "1 0 (4)"
    assert _score_text(shoot, "away") == "1 0 (2)"


# --- KnockoutStage hooks ---------------------------------------------------


def test_get_match_fills_a_single_leg():
    class D(KnockoutStage):
        def get_match(self, ref):
            assert ref == 1001
            return {"team1": "Peñarol", "goals1": 2, "team2": "Nacional", "goals2": 1}

    stage = D(
        {
            "rounds": [
                {
                    "name": "Final",
                    "matches": [
                        {
                            "id": "f",
                            "legs": [{"ref": 1001}],
                        }
                    ],
                }
            ]
        }
    ).build()
    final = stage.matches_by_id()["f"]
    assert final.home.team == "Peñarol"
    assert final.away.team == "Nacional"
    assert (final.legs[0].home, final.legs[0].away) == (2, 1)


def test_get_match_fills_pens():
    class D(KnockoutStage):
        def get_match(self, ref):
            return {
                "team1": "A",
                "goals1": 0,
                "pen1": 4,
                "team2": "B",
                "goals2": 0,
                "pen2": 2,
            }

    stage = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {
                            "id": "f",
                            "legs": [{"ref": 7}],
                        }
                    ],
                }
            ]
        }
    ).build()
    leg = stage.matches_by_id()["f"].legs[0]
    assert leg.pens.home == 4 and leg.pens.away == 2


def test_get_match_orients_second_leg_by_team():
    # Leg 2 is played at the visitor's venue: its local is the tie's away side.
    class D(KnockoutStage):
        def get_match(self, ref):
            if ref == 1:
                return {
                    "team1": "Peñarol",
                    "goals1": 2,
                    "team2": "Nacional",
                    "goals2": 1,
                }
            return {"team1": "Nacional", "goals1": 0, "team2": "Peñarol", "goals2": 0}

    stage = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {
                            "id": "f",
                            "legs": [{"ref": 1}, {"ref": 2}],
                        }
                    ],
                }
            ]
        }
    ).build()
    m = stage.matches_by_id()["f"]
    assert m.home.team == "Peñarol" and m.away.team == "Nacional"
    # Both legs are stored in tie orientation: Peñarol then Nacional.
    assert [(leg.home, leg.away) for leg in m.legs] == [(2, 1), (0, 0)]


def test_get_match_returning_none_leaves_the_leg():
    class D(KnockoutStage):
        def get_match(self, ref):
            return None

    stage = D(
        {
            "rounds": [
                {
                    "name": "F",
                    "matches": [
                        {
                            "id": "f",
                            "legs": [{"ref": 1}],
                        }
                    ],
                }
            ]
        }
    ).build()
    assert stage.matches_by_id()["f"].legs[0].played is False


def test_get_crest_emits_images():
    class D(KnockoutStage):
        def get_crest(self, team_id, team_name):
            return f"https://img.example/{team_name}.png"

    doc = {
        "rounds": [
            {
                "name": "F",
                "matches": [{"id": "f", "team1": "Flamengo", "team2": "Boca Juniors"}],
            }
        ]
    }
    svg = D(doc).render()
    assert svg.count("<image") == 2
    assert 'href="https://img.example/Flamengo.png"' in svg

    # The table layout emits the same crests, as <img> elements.
    html = D(doc).render("html")
    assert html.count("<img") == 2
    assert 'src="https://img.example/Flamengo.png"' in html

    # The base class resolves nothing: no images in either format, nothing changes.
    assert "<image" not in KnockoutStage(doc).render()
    assert "<img" not in KnockoutStage(doc).render("html")


def test_get_crest_receives_the_side_identity():
    calls = []

    class D(KnockoutStage):
        def get_crest(self, team_id, team_name):
            calls.append((team_id, team_name))

    D(
        {
            "rounds": [
                {
                    "name": "SF",
                    "matches": [{"id": "sf1", "team1": "A", "id1": 7, "team2": "B"}],
                },
                {"name": "F", "matches": [{"id": "f", "winnerof1": "sf1"}]},
            ]
        }
    ).build()
    # Only sides with an identity are queried: the final's sides (an unresolved
    # winnerof link and a pending-draw side) are skipped.
    assert calls == [(7, "A"), (None, "B")]


def test_tournament_and_season_overrides():
    class D(KnockoutStage):
        def get_tournament(self):
            return "Copa Dinámica"

        def get_season(self):
            return "2027"

    stage = D(
        {
            "tournament": "Ignored",
            "rounds": [
                {
                    "name": "F",
                    "matches": [{"id": "f", "team1": "A", "team2": "B"}],
                }
            ],
        }
    ).build()
    assert stage.tournament == "Copa Dinámica"
    assert stage.season == "2027"


def test_get_labels_translates_generated_labels():
    doc = {
        "rounds": [
            {"name": "SF", "matches": [{"id": "sf1", "team1": "A", "team2": "B"}]},
            {"name": "F", "matches": [{"id": "f", "winnerof1": "sf1"}]},
        ]
    }
    translations = {
        "es": {"winner": "Ganador {id}", "tbd": "A definir"},
        "pt": {"winner": "Vencedor {id}"},  # partial: tbd falls back to English
    }

    class D(KnockoutStage):
        def get_labels(self, language):
            return translations.get(language)

    # The requested language flows through build/render to the hook.
    es = D(doc).build("es")
    ef = es.matches_by_id()["f"]
    assert Resolver(es).label(ef.home) == "Ganador SF1"  # unresolved winnerof
    assert Resolver(es).label(ef.away) == "A definir"  # no team, no link

    # A partial translation keeps the English default for the key left out.
    pt = D(doc).build("pt")
    pf = pt.matches_by_id()["f"]
    assert Resolver(pt).label(pf.home) == "Vencedor SF1"
    assert Resolver(pt).label(pf.away) == "TBD"

    # No language (or an unknown one) leaves the labels in English.
    en = D(doc).build()
    enf = en.matches_by_id()["f"]
    assert Resolver(en).label(enf.home) == "Winner SF1"
    assert Resolver(en).label(enf.away) == "TBD"


def test_diagram_accepts_a_json_string():
    doc = json.dumps(
        {
            "tournament": "T",
            "rounds": [
                {
                    "name": "F",
                    "matches": [{"id": "f", "team1": "A", "team2": "B"}],
                }
            ],
        }
    )
    assert KnockoutStage(doc).render().startswith("<svg")


@pytest.mark.parametrize("name", ["libertadores-2026.json", "knockout-8.json"])
def test_examples_match_schema(name):
    pytest.importorskip("jsonschema")
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        validate_document(json.load(fh))


def test_example_host_resolves_ref_legs(libertadores_diagram):
    qf1 = libertadores_diagram().build().matches_by_id()["qf1"]
    # The two ref-only legs are filled from example_data.json, in tie orientation.
    assert [(leg.home, leg.away) for leg in qf1.legs] == [(2, 1), (0, 0)]
    assert qf1.home.team == "Flamengo" and qf1.away.team == "Boca Juniors"
