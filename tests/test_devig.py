import pytest

from core.devig import power, proportional, shin


@pytest.mark.parametrize("fn", [proportional, shin, power])
def test_sums_to_one(fn):
    assert sum(fn([1.5, 3.6, 6.5])) == pytest.approx(1.0, abs=1e-9)
    assert sum(fn([1.9, 1.95])) == pytest.approx(1.0, abs=1e-9)


def test_no_overround_identical_to_proportional():
    odds = [2.0, 4.0, 4.0]
    assert shin(odds) == pytest.approx(proportional(odds))


def test_shin_favourite_up_outsider_down():
    odds = [1.5, 3.6, 6.5]
    s, p = shin(odds), proportional(odds)
    assert s[0] > p[0]
    assert s[2] < p[2]


def test_symmetric_two_way():
    assert shin([1.9, 1.9]) == pytest.approx([0.5, 0.5])


def test_shin_fallback_on_absurd_overround_still_sums_one():
    r = shin([1.01, 1.01, 1.01])
    assert sum(r) == pytest.approx(1.0)


def test_invalid_odds_rejected():
    with pytest.raises(ValueError):
        shin([1.0, 2.0])
