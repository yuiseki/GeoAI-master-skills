"""uvx --with pytest pytest test_dag_check.py

Small graphs whose answers are known by hand: T is the treatment, Y the outcome.
"""

import pytest

from dag_check import Dag, parse


def dag(text):
    return parse(text.splitlines())


def test_a_cycle_is_found_and_named():
    d = dag("A -> B\nB -> C\nC -> A")
    assert sorted(d.cycle()) == ["A", "B", "C"]
    assert dag("A -> B -> C").cycle() is None


def test_ancestors_and_descendants_follow_the_arrows():
    d = dag("L -> T -> M -> Y\nL -> Y")
    assert d.ancestors("Y") == {"L", "T", "M"}
    assert d.descendants("T") == {"M", "Y"}
    assert d.ancestors("L") == set()


def test_an_unadjusted_confounder_leaves_a_backdoor_path_open():
    d = dag("L -> T\nL -> Y\nT -> Y")
    assert d.roles("T", "Y")["L"] == "confounder"
    r = d.check("T", "Y", [])
    assert not r["valid"] and r["open_backdoor"] == [["T", "<-", "L", "->", "Y"]]
    assert d.check("T", "Y", ["L"])["valid"]


def test_adjusting_a_mediator_is_refused_for_the_total_effect():
    d = dag("T -> M -> Y")
    assert d.roles("T", "Y")["M"] == "mediator"
    assert d.check("T", "Y", [])["valid"]
    r = d.check("T", "Y", ["M"])
    assert not r["valid"] and r["post_treatment"] == ["M"]


def test_adjusting_a_collider_or_its_descendant_opens_a_path():
    d = dag("T -> C\nY -> C\nC -> D")
    roles = d.roles("T", "Y")
    assert roles["C"] == "collider" and roles["D"] == "descendant of a collider"
    assert d.check("T", "Y", [])["valid"]
    for z in ("C", "D"):
        r = d.check("T", "Y", [z])
        assert not r["valid"] and r["opened"] == [["T", "->", "C", "<-", "Y"]]


def test_a_pre_treatment_collider_m_bias():
    # C is measured before T and correlates with both, but adjusting it opens T <- U1 -> C <- U2 -> Y
    d = dag("latent: U1 U2\nU1 -> T\nU1 -> C\nU2 -> C\nU2 -> Y\nT -> Y")
    assert d.check("T", "Y", [])["valid"]
    r = d.check("T", "Y", ["C"])
    assert not r["valid"] and r["post_treatment"] == []
    assert r["open_backdoor"] == [["T", "<-", "U1", "->", "C", "<-", "U2", "->", "Y"]]
    assert d.adjustment_sets("T", "Y") == [[]]


def test_an_unmeasured_confounder_leaves_no_valid_set():
    d = dag("latent: U\nU -> T\nU -> Y\nT -> Y\nL -> T\nL -> Y")
    assert d.adjustment_sets("T", "Y") == []
    assert d.roles("T", "Y")["U"] == "confounder (unmeasured)"


def test_either_end_of_a_chain_blocks_the_same_backdoor_path():
    d = dag("A -> T\nA -> B\nB -> Y\nT -> Y")
    assert d.adjustment_sets("T", "Y") == [["A"], ["B"]]


def test_a_latent_variable_cannot_be_adjusted():
    d = dag("latent: U\nU -> T\nU -> Y\nT -> Y")
    with pytest.raises(ValueError, match="U"):
        d.check("T", "Y", ["U"])


def test_causes_of_only_one_side_are_named():
    d = dag("A -> T\nB -> Y\nT -> Y\nY -> E")
    roles = d.roles("T", "Y")
    assert roles["A"] == "cause of treatment only"
    assert roles["B"] == "cause of outcome only"
    assert roles["E"] == "descendant of the outcome"
    assert d.check("T", "Y", ["B"])["valid"]
    assert not d.check("T", "Y", ["E"])["valid"]


def test_a_cycle_stops_the_checks():
    with pytest.raises(ValueError, match="cycle"):
        dag("T -> Y\nY -> T").check("T", "Y", [])
