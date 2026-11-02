"""Tenis: hándicap/total de JUEGOS (spread/total) y de SETS (sspread/stotal) bien separados, lados correctos, sin empate/1X2/DC."""
from server import market as MK, probs as PR

def q(typ, prices, period=0): return dict(type=typ, period=period, status="open", isAlternate=False, prices=prices)
P = lambda d, price, pts=None: dict(designation=d, price=price, **({"points": pts} if pts is not None else {}))

# Pinnacle: matchup principal = SETS; matchup relacionado "(Games)" = JUEGOS. Local (home) = favorito.
MAIN = [q("moneyline", [P("home", -250), P("away", 200)]),
        q("spread", [P("home", 130, -1.5), P("away", -160, 1.5)]),
        q("total", [P("over", -150, 2.5), P("under", 120, 2.5)])]
GAMES = [q("spread", [P("home", -110, -4.5), P("away", -110, 4.5)]),
         q("total", [P("over", -105, 22.5), P("under", -115, 22.5)])]

def test_games_markets_come_from_related_matchup_sets_from_main():
    b = MK._pin_entry(MAIN, GAMES)
    assert b["spread"]["home"] == dict(line=-4.5, price=-110) and b["spread"]["away"]["line"] == 4.5          # JUEGOS
    assert b["total"]["over"]["line"] == 22.5
    assert b["sspread"]["home"]["line"] == -1.5 and b["stotal"]["over"]["line"] == 2.5                       # SETS
    assert b["ml"] == dict(home=-250, away=200)

def test_flip_keeps_each_price_with_its_player():
    f = MK._flip_q(GAMES[0])
    by = {p["designation"]: p for p in f["prices"]}
    assert by["away"]["points"] == -4.5 and by["home"]["points"] == 4.5          # el -4.5 ahora es del otro jugador (con su mismo precio)
    assert by["away"]["price"] == -110

def game():
    return dict(sport="tenis", league="atp", id="1", state="pre", home=dict(id="1", name="Sinner"), away=dict(id="2", name="Rival"))

def mk_of(b):
    nv = MK.nv_of(b)
    return dict(books=[b], consensus_nv={}, sharp_nv=nv, ref=dict(spread_home=b["spread"]["home"]["line"], total=b["total"]["over"]["line"]))

def test_probs_tennis_titles_units_and_no_three_way():
    b = MK._pin_entry(MAIN, GAMES)
    pr = PR.build(game(), None, None, mk_of(b))
    keys = [m["key"] for m in pr["markets"]]
    assert keys == ["ml", "spread", "total", "sspread", "stotal"]            # sin dc
    m = {x["key"]: x for x in pr["markets"]}
    assert m["spread"]["title"] == "Hándicap de juegos" and m["spread"]["unit"] == "juegos"
    assert m["total"]["title"] == "Total de juegos" and m["total"]["unit"] == "juegos"
    assert m["sspread"]["title"] == "Hándicap de sets" and m["stotal"]["title"] == "Total de sets"
    assert [o["side"] for o in m["ml"]["outcomes"]] == ["home", "away"]      # sin empate
    labels = {o["key"]: o["label"] for k in ("spread", "total", "sspread", "stotal") for o in m[k]["outcomes"]}
    assert labels["spread.home"] == "Sinner -4.5 juegos" and labels["spread.away"] == "Rival +4.5 juegos"
    assert labels["total.over"] == "Over 22.5 juegos" and labels["total.under"] == "Under 22.5 juegos"
    assert labels["sspread.home"] == "Sinner -1.5 sets" and labels["stotal.under"] == "Under 2.5 sets"
    assert not any("gol" in l.lower() or "empate" in l.lower() for l in labels.values())
    # el favorito del ML (home, -250) lleva el hándicap NEGATIVO en juegos y en sets
    assert m["spread"]["outcomes"][0]["line"] < 0 and m["sspread"]["outcomes"][0]["line"] < 0

def test_brief_exposes_side_line_unit():
    pr = PR.build(game(), None, None, mk_of(MK._pin_entry(MAIN, GAMES)))
    br = {b["market"]: b for b in PR.brief(pr)}
    assert br["total"]["unit"] == "juegos" and "juegos" in br["total"]["label"] and br["stotal"]["unit"] == "sets"
    assert br["spread"]["side"] in ("home", "away") and br["spread"]["line"] is not None
