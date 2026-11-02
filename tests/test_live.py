"""En vivo: texto de estado en español, situación NFL/MLB y calificación PROVISIONAL (nunca final)."""
from server.live import status_es, situation, provisional

def S(state, name="STATUS_IN_PROGRESS", det="", per=0, clk=""):
    return dict(type=dict(state=state, name=name, shortDetail=det, detail=det), period=per, displayClock=clk)

def test_status_basketball_nfl_hockey():
    assert status_es("basketball", "nba", S("in", per=3, clk="5:32")) == "Q3 5:32"
    assert status_es("basketball", "nba", S("in", per=5, clk="1:10")) == "OT 1:10"
    assert status_es("hockey", "nhl", S("in", per=2, clk="12:01")) == "P2 12:01"
    assert status_es("football", "nfl", S("in", per=4, clk="2:00")) == "Q4 2:00"
    assert status_es("basketball", "nba", S("in", "STATUS_HALFTIME", per=2)) == "Descanso"
    assert status_es("basketball", "nba", S("in", "STATUS_END_PERIOD", per=1)) == "Fin Q1"

def test_status_soccer_baseball_tennis():
    assert status_es("soccer", "esp.1", S("in", clk="67'")) == "67'"
    assert status_es("baseball", "mlb", S("in", det="Top 5th")) == "Alta 5ª"
    assert status_es("baseball", "mlb", S("in", det="Bot 9th")) == "Baja 9ª"
    assert status_es("tennis", "atp", S("in", det="3rd")) == "Set 3"
    assert status_es("basketball", "nba", S("post", det="Final/OT")).startswith("Final")

def test_situation_nfl():
    s = situation("football", dict(shortDownDistanceText="3rd & 7", possession="12", isRedZone=True), {"12": "SEA"})
    assert "Posesión SEA" in s["text"] and "3º y 7" in s["text"] and s["red_zone"]
    assert situation("football", None) is None

def test_situation_mlb():
    s = situation("baseball", dict(outs=2, balls=3, strikes=1, onFirst=True, onThird=True,
                                   batter=dict(athlete=dict(displayName="J. Soto")), pitcher=dict(athlete=dict(displayName="G. Cole"))))
    assert "2 outs" in s["text"] and "cuenta 3-1" in s["text"] and "1ª y 3ª" in s["text"] and "al bat J. Soto" in s["text"]
    assert "bases vacías" in situation("baseball", dict(outs=0, balls=0, strikes=0))["text"]

def G(state="in", h=0, a=0, sport="futbol"):
    return dict(state=state, sport=sport, home=dict(score=h), away=dict(score=a))

def test_provisional_only_when_live_and_not_tennis():
    rows = [dict(market="ml", selection="home", line=None)]
    assert provisional(rows, G("pre"), "soccer") == {} and provisional(rows, G("post", 1, 0), "soccer") == {}
    assert provisional(rows, G("in", 1, 0, "tenis"), "tennis") == {}

def test_provisional_ml_spread_total():
    rows = [dict(market="ml", selection="home", line=None), dict(market="ml", selection="away", line=None), dict(market="ml", selection="draw", line=None),
            dict(market="total", selection="over", line=2.5), dict(market="total", selection="under", line=2.5), dict(market="spread", selection="home", line=-0.5)]
    p = provisional(rows, G("in", 2, 1), "soccer")
    assert p["ml.home"]["state"] == "ganando" and not p["ml.home"]["locked"]
    assert p["ml.away"]["state"] == "perdiendo" and p["ml.draw"]["state"] == "perdiendo"
    assert p["total.over"]["state"] == "ganando" and p["total.over"]["locked"]        # 3 goles > 2.5: ya no puede perder
    assert p["total.under"]["state"] == "perdiendo" and p["total.under"]["locked"]    # ya se pasó: no puede ganar
    assert p["spread.home"]["state"] == "ganando"
    assert p["ml.home"]["score"] == "1-2"

def test_provisional_soccer_draw_and_unlocked_under():
    p = provisional([dict(market="ml", selection="draw", line=None), dict(market="total", selection="under", line=2.5), dict(market="total", selection="over", line=2.5)], G("in", 1, 1), "soccer")
    assert p["ml.draw"]["state"] == "ganando"
    assert p["total.under"]["state"] == "ganando" and not p["total.under"]["locked"]
    assert p["total.over"]["state"] == "perdiendo" and not p["total.over"]["locked"]  # aún puede subir

def test_provisional_push():
    p = provisional([dict(market="spread", selection="home", line=-3.0)], G("in", 23, 20, "nfl"), "football")
    assert p["spread.home"]["state"] == "empatando"
