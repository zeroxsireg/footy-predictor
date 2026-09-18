"""Tests for core.player_candidates (pure, no network)."""

from datetime import datetime, timezone

from core.contracts import FixtureRef
from core.player_candidates import rank_booking_candidates

FX = FixtureRef(1, datetime(2026, 9, 20, tzinfo=timezone.utc), "Home", "Away", 10, 20, 135, 2026)


def _p(pid, pos="Defender", apps=30, yellows=9, minutes=2500, fouls=50):
    return {"id": pid, "name": f"P{pid}", "position": pos, "appearances": apps,
            "yellow_cards": yellows, "fouls_committed": fouls, "minutes": minutes}


SQUADS = {10: [_p(1), _p(2, yellows=1), _p(3, "Goalkeeper", yellows=5), _p(4, "Attacker", yellows=2)],
          20: [_p(11, "Midfielder"), _p(12, yellows=0, apps=2, minutes=100)]}
XI = {10: [{"id": 1, "start_share": 1.0}, {"id": 2, "start_share": 0.9}, {"id": 3, "start_share": 1.0}],
      20: [{"id": 11, "start_share": 0.8}]}


def _by_id(cands):
    return {c.player_id: c for c in cands}


def test_sorted_and_product_and_goalkeepers_excluded():
    cands = rank_booking_candidates(FX, SQUADS, XI)
    assert [c.p_booked for c in cands] == sorted((c.p_booked for c in cands), reverse=True)
    assert 3 not in _by_id(cands)
    for c in cands:
        assert abs(c.p_booked - c.p_booked_given_plays * c.start_prob) < 1e-12
    assert cands[0].player_id == 1 and "9 gialli in 30 pres." in cands[0].note


def test_player_not_in_squad_is_never_included():
    xi = {10: XI[10] + [{"id": 99, "name": "Gone", "start_share": 1.0}], 20: XI[20]}
    assert 99 not in _by_id(rank_booking_candidates(FX, SQUADS, xi))


def test_absent_from_probable_xi_small_but_nonzero():
    c = _by_id(rank_booking_candidates(FX, SQUADS, XI))[4]
    assert 0.0 < c.start_prob <= 0.10
    assert c.start_prob < _by_id(rank_booking_candidates(FX, SQUADS, XI))[1].start_prob


def test_official_lineups_override_probable_xi():
    cands = _by_id(rank_booking_candidates(FX, SQUADS, XI, official_lineups={10: [{"id": 4}, {"id": 2}]}))
    assert cands[4].start_prob == 1.0 and cands[2].start_prob == 1.0
    assert 1 not in cands                       # not in official XI -> 0 -> dropped
    assert cands[11].start_prob == 0.8          # team 20 has no official lineup: probable XI


def test_referee_strictness_scales_probability_and_top_n():
    base = _by_id(rank_booking_candidates(FX, SQUADS, XI))[1]
    strict = _by_id(rank_booking_candidates(FX, SQUADS, XI, referee_strictness=1.5))[1]
    assert strict.p_booked_given_plays > base.p_booked_given_plays * 1.3
    assert "arbitro x1.50" in strict.note
    assert len(rank_booking_candidates(FX, SQUADS, XI, top_n=2)) == 2


def test_zero_minutes_absent_player_gets_floor_not_zero():
    squads = {10: [_p(1), _p(5, minutes=0, apps=4, yellows=1)], 20: []}
    c = _by_id(rank_booking_candidates(FX, squads, {10: [{"id": 1, "start_share": 1.0}]}))[5]
    assert c.start_prob == 0.02
