"""Unit tests for KnockoutStage.apply_results: locating legs, writing, settling."""

import pytest

from matamata import KnockoutStage
from matamata.parse import StageError, validate_document


def doc():
    """Two semifinals feeding a final: s1 is inline-named, s2 is host-resolved."""
    return {
        "rounds": [
            {
                "name": "Semifinals",
                "matches": [
                    {
                        "id": "s1",
                        "team1": "Peñarol",
                        "id1": 10,
                        "team2": "Nacional",
                        "id2": 20,
                    },
                    {"id": "s2", "legs": [{"ref": 901}, {"ref": 902}]},
                ],
            },
            {
                "name": "Final",
                "matches": [{"id": "f", "winnerof1": "s1", "winnerof2": "s2"}],
            },
        ]
    }


def match_of(document, match_id):
    return {m["id"]: m for r in document["rounds"] for m in r["matches"]}[match_id]


# --- locating and writing ----------------------------------------------------


def test_apply_by_match_id_writes_leg_one():
    out = KnockoutStage(doc()).apply_results(
        {"id": "s1", "goals1": 2, "goals2": 1}, settle=False
    )
    assert match_of(out, "s1")["legs"] == [{"goals1": 2, "goals2": 1}]


def test_apply_by_ref_keeps_the_ref():
    out = KnockoutStage(doc()).apply_results(
        {"ref": 901, "goals1": 1, "goals2": 1, "pen1": 4, "pen2": 2}, settle=False
    )
    assert match_of(out, "s2")["legs"][0] == {
        "ref": 901,
        "goals1": 1,
        "goals2": 1,
        "pen1": 4,
        "pen2": 2,
    }


def test_apply_creates_missing_legs():
    out = KnockoutStage(doc()).apply_results(
        {"id": "s1", "leg": 2, "goals1": 0, "goals2": 3}, settle=False
    )
    assert match_of(out, "s1")["legs"] == [{}, {"goals1": 0, "goals2": 3}]


def test_apply_overwrites_only_the_present_keys():
    diagram = KnockoutStage(doc())
    diagram.apply_results(
        {"id": "s1", "goals1": 0, "goals2": 0, "pen1": 4, "pen2": 2}, settle=False
    )
    out = diagram.apply_results({"id": "s1", "goals1": 1}, settle=False)
    assert match_of(out, "s1")["legs"][0] == {
        "goals1": 1,
        "goals2": 0,
        "pen1": 4,
        "pen2": 2,
    }


def test_apply_accepts_a_list_mixing_both_forms():
    out = KnockoutStage(doc()).apply_results(
        [
            {"id": "s1", "goals1": 2, "goals2": 1},
            {"ref": 902, "goals1": 0, "goals2": 0},
        ],
        settle=False,
    )
    assert match_of(out, "s1")["legs"][0] == {"goals1": 2, "goals2": 1}
    assert match_of(out, "s2")["legs"][1] == {"ref": 902, "goals1": 0, "goals2": 0}


def test_writing_through_a_reversed_named_leg_flips_the_keys():
    # Results are tie-oriented; the second leg lists the teams the other way around.
    document = {
        "rounds": [
            {
                "name": "F",
                "matches": [
                    {
                        "id": "f",
                        "legs": [
                            {
                                "team1": "Peñarol",
                                "goals1": 1,
                                "team2": "Nacional",
                                "goals2": 0,
                            },
                            {"team1": "Nacional", "team2": "Peñarol"},
                        ],
                    }
                ],
            }
        ]
    }
    out = KnockoutStage(document).apply_results(
        {"id": "f", "leg": 2, "goals1": 0, "goals2": 3}, settle=False
    )
    assert match_of(out, "f")["legs"][1] == {
        "team1": "Nacional",
        "goals1": 3,
        "team2": "Peñarol",
        "goals2": 0,
    }


def test_applied_document_still_renders():
    diagram = KnockoutStage(doc())
    diagram.apply_results({"id": "s1", "goals1": 2, "goals2": 1})
    assert diagram.render().startswith("<svg")


@pytest.mark.parametrize(
    "bad",
    [
        {"goals1": 1},  # neither ref nor id
        {"ref": 901, "id": "s1", "goals1": 1},  # both
        {"ref": 901, "leg": 2, "goals1": 1},  # leg goes with id
        {"id": "s1", "leg": 0, "goals1": 1},  # legs are 1-based
        {"id": "s1", "leg": "second", "goals1": 1},
        {"id": "ghost", "goals1": 1},  # unknown match
        {"ref": 999, "goals1": 1},  # unknown ref
        {"id": "s1", "team1": "X"},  # results carry no team names
        {"id": "s1", "goals1": -1},
        {"id": "s1", "goals1": "2"},
    ],
)
def test_bad_results_are_rejected(bad):
    with pytest.raises(StageError):
        KnockoutStage(doc()).apply_results(bad)


def test_duplicated_ref_is_ambiguous():
    document = doc()
    match_of(document, "s2")["legs"][1]["ref"] = 901
    with pytest.raises(StageError, match="more than one"):
        KnockoutStage(document).apply_results({"ref": 901, "goals1": 1, "goals2": 0})


# --- settling -----------------------------------------------------------------


def test_settle_writes_winner_and_advances_the_team():
    out = KnockoutStage(doc()).apply_results({"id": "s1", "goals1": 2, "goals2": 1})
    assert match_of(out, "s1")["winner"] == 1
    final = match_of(out, "f")
    assert final["team1"] == "Peñarol" and final["id1"] == 10


def test_settle_pushes_the_loser_into_a_third_place_match():
    # The loser of a settled match drops into any loserof side, mirroring the winner push.
    document = {
        "rounds": [
            {
                "name": "SF",
                "matches": [
                    {
                        "id": "sf1",
                        "team1": "France",
                        "id1": 1,
                        "team2": "Spain",
                        "id2": 2,
                    }
                ],
            },
            {"name": "Final", "matches": [{"id": "f", "winnerof1": "sf1"}]},
            {"name": "Third place", "matches": [{"id": "tp", "loserof1": "sf1"}]},
        ]
    }
    out = KnockoutStage(document).apply_results({"id": "sf1", "goals1": 2, "goals2": 1})
    assert match_of(out, "f")["team1"] == "France" and match_of(out, "f")["id1"] == 1
    tp = match_of(out, "tp")
    assert tp["team1"] == "Spain" and tp["id1"] == 2


def test_settle_decides_a_tie_by_penalties():
    out = KnockoutStage(doc()).apply_results(
        {"id": "s1", "goals1": 0, "goals2": 0, "pen1": 2, "pen2": 4}
    )
    assert match_of(out, "s1")["winner"] == 2
    assert match_of(out, "f")["team1"] == "Nacional"


def test_settle_aggregates_every_leg():
    out = KnockoutStage(doc()).apply_results(
        [
            {"id": "s1", "goals1": 0, "goals2": 2},
            {"id": "s1", "leg": 2, "goals1": 3, "goals2": 0},
        ]
    )
    assert match_of(out, "s1")["winner"] == 1


def test_settle_clears_a_no_longer_decided_match():
    document = doc()
    match_of(document, "s1")["winner"] = 1
    final = match_of(document, "f")
    final["team1"] = "Peñarol"
    final["id1"] = 10
    out = KnockoutStage(document).apply_results({"id": "s1", "goals1": 1, "goals2": 1})
    assert "winner" not in match_of(out, "s1")
    assert "team1" not in match_of(out, "f") and "id1" not in match_of(out, "f")


def test_reapplying_flips_winner_and_consumer():
    diagram = KnockoutStage(doc())
    diagram.apply_results({"id": "s1", "goals1": 2, "goals2": 1})
    out = diagram.apply_results({"id": "s1", "goals1": 0})
    assert match_of(out, "s1")["winner"] == 2
    final = match_of(out, "f")
    assert final["team1"] == "Nacional" and final["id1"] == 20


def test_settle_false_call_leaves_winner_alone():
    out = KnockoutStage(doc()).apply_results(
        {"id": "s1", "goals1": 2, "goals2": 1}, settle=False
    )
    assert "winner" not in match_of(out, "s1")


def test_settle_false_in_the_document_opts_the_match_out():
    document = doc()
    match_of(document, "s1")["settle"] = False
    out = KnockoutStage(document).apply_results({"id": "s1", "goals1": 2, "goals2": 1})
    assert "winner" not in match_of(out, "s1")


def test_settle_sees_what_get_match_would_show():
    class D(KnockoutStage):
        def get_match(self, ref):
            return (
                {"goals1": 5, "goals2": 0} if ref == 901 else {"goals1": 0, "goals2": 0}
            )

    out = D(doc()).apply_results({"ref": 902, "goals1": 0, "goals2": 0})
    assert match_of(out, "s2")["winner"] == 1
    # The host returned no team names, so nothing is advanced into the final's side 2.
    assert "team2" not in match_of(out, "f")


# --- schema -------------------------------------------------------------------


def test_schema_accepts_the_maintained_document_shapes():
    pytest.importorskip("jsonschema")
    document = KnockoutStage(doc()).apply_results(
        [
            {"id": "s1", "leg": 2, "goals1": 1, "goals2": 0},
            {"ref": 901, "goals1": 1, "goals2": 1, "pen1": 4, "pen2": 2},
        ]
    )
    validate_document(document)


def test_schema_rejects_settle_true():
    jsonschema = pytest.importorskip("jsonschema")
    document = doc()
    match_of(document, "s1")["settle"] = True
    with pytest.raises(jsonschema.ValidationError):
        validate_document(document)
