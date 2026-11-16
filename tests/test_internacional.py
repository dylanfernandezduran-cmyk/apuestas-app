"""Liga de Naciones y ventanas internacionales: están en la lista y reutilizan el modelo de fútbol."""
from server.config import LEAGUES, SPORTS
from server.market import AN_SLUG, PIN_SPORT, PIN_NAME, pin_wanted_names, pin_league_ids, odds_ttl
import os

INTL = ("uefa.nations", "concacaf.nations.league", "fifa.friendly")

def test_nations_league_y_amistosos_en_futbol():
    assert LEAGUES["uefa.nations"]["path"] == "soccer/uefa.nations"
    assert LEAGUES["uefa.nations"]["name"] == "Liga de Naciones UEFA"
    assert LEAGUES["concacaf.nations.league"]["path"] == "soccer/concacaf.nations.league"
    assert LEAGUES["fifa.friendly"]["path"] == "soccer/fifa.friendly"
    for k in INTL:
        cfg = LEAGUES[k]
        assert cfg["family"] == "soccer" and cfg["sport"] == "futbol" and cfg.get("intl") is True
    fut = next(s for s in SPORTS if s["key"] == "futbol")
    for k in INTL:
        assert k in fut["leagues"]

def test_cuotas_pinnacle_y_action_network_mapeadas():
    for k in INTL:
        assert AN_SLUG[k] == "soccer"
        assert PIN_SPORT[k] == 29
    names = pin_wanted_names("uefa.nations")
    assert names == ["UEFA - Nations League A", "UEFA - Nations League B", "UEFA - Nations League C", "UEFA - Nations League D"]
    ls = [{"id": 1, "name": "UEFA - Nations League A"}, {"id": 2, "name": "UEFA - Nations League C"}, {"id": 3, "name": "UEFA - Champions League"}]
    assert pin_league_ids(ls, names) == [1, 2]
    assert PIN_NAME["fifa.friendly"] == "International - Friendlies"
    assert PIN_NAME["concacaf.nations.league"] == "CONCACAF - Nations League"

def test_odds_ttl_floor_no_baja_el_base():
    os.environ.pop("ODDS_TTL_FLOOR", None)
    assert odds_ttl(240) == 240
    os.environ["ODDS_TTL_FLOOR"] = "600"
    try:
        assert odds_ttl(240) == 600 and odds_ttl(3600) == 3600
    finally:
        os.environ.pop("ODDS_TTL_FLOOR", None)
