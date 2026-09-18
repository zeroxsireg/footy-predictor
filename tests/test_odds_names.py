"""Player-name normalisation/matching (core.odds_names)."""

import pytest

from core.odds_names import match_player_name, names_match, normalize_player_name


@pytest.mark.parametrize("raw, expected", [
    ("L. Martínez", "l martinez"),
    ("Hakan Çalhanoğlu", "hakan calhanoglu"),
    ("Martin Ødegaard", "martin odegaard"),
    ("S. Milinković-Savić", "s milinkovic savic"),
    ("  De   Vrij ", "de vrij"),
    ("", ""),
])
def test_normalize(raw, expected):
    assert normalize_player_name(raw) == expected


@pytest.mark.parametrize("a, b", [
    ("L. Martinez", "Lautaro Martínez"),
    ("Martinez L.", "Lautaro Martinez"),
    ("S. de Vrij", "Stefan de Vrij"),
    ("S. Milinkovic-Savic", "Sergej Milinkovic Savic"),
    ("L. Martinez", "Lucas Martinez Quarta"),      # composite surname, partial
    ("N. Barella", "Nicolò Barella"),
    ("Lautaro Martinez", "Lautaro Javier Martinez"),
])
def test_names_match_positive(a, b):
    assert names_match(a, b)


@pytest.mark.parametrize("a, b", [
    ("L. Martinez", "Marcus Thuram"),
    ("L. Martinez", "Federico Martinez"),          # wrong initial
    ("M. de Vrij", "Stefan de Vrij"),
    ("L. Martinez", "Martinez"),                   # mononym: not enough evidence
    ("", "Lautaro Martinez"),
])
def test_names_match_negative(a, b):
    assert not names_match(a, b)


def test_match_prefers_exact_and_rejects_ambiguity():
    assert match_player_name("Lautaro Martinez", ["Lautaro Martinez", "L. Martinez"]) == "Lautaro Martinez"
    assert match_player_name("L. Martinez", ["Lautaro Martinez", "Lisandro Martinez"]) is None
    assert match_player_name("L. Martinez", ["Lautaro Martinez", "Marcus Thuram"]) == "Lautaro Martinez"
