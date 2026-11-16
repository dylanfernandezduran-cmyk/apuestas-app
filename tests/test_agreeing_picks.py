"""Picks que concuerdan: predicción NRNM + picks registrados (mismo mercado/lado/línea)."""
import json, time
from datetime import datetime, timezone
from server import record as R, history, prediction as PRED
from server import consistency as C
from server import chat as CHAT

# 2026-11-15 20:00Z = 14:00 CDMX (aún no empieza si now es 19:00Z)
KICK = 1_794_772_800  # 2026-11-15T20:00Z
NOW = 1_794_769_200   # 2026-11-15T19:00Z = 13:00 CDMX
DAY = "2026-11-15"


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _save_pred(league, eid, sport, home, away, pred, start, now=NOW, hid="1", aid="2"):
    PRED.save(
        dict(sport=sport, league=league, id=eid, state="pre", date=iso(start),
             home=dict(id=hid, name=home), away=dict(id=aid, name=away)),
        pred, now=now,
    )


def _row(sport, league, eid, start, home, away, market, selection, line, label, typ="main",
         odds=-110, ev=3.2, conf="Media", p_final=0.54, hid="1", aid="2", book="ESPN BET"):
    return dict(sport=sport, league=league, eid=str(eid), start_ts=start,
                home=home, away=away, home_id=hid, away_id=aid, created_at=NOW, source="live",
                book=book, p_model=0.55, p_final=p_final, p_nv=0.52, edge=2, ev=ev,
                basis="modelo", market=market, selection=selection, line=line, label=label,
                odds=odds, type=typ, conf_level=conf)


def test_intent_detects_spanish_phrases():
    assert CHAT.agreeing_intent("dame los picks que concuerdan")
    assert CHAT.agreeing_intent("Picks que coinciden")
    assert CHAT.agreeing_intent("concuerdan predicción y pick")
    assert CHAT.agreeing_intent("quiero los que coinciden con la prediccion y los registrados")
    assert not CHAT.agreeing_intent("mejores picks de hoy")
    assert not CHAT.agreeing_intent("cuál es el récord")
    assert not CHAT.agreeing_intent("lesiones de los Chiefs")


def test_only_matching_side_and_line_are_listed(db):
    pred = dict(
        winner=dict(side="away", p=0.58, src="pfinal"),
        score=dict(home=21, away=24),
        total=dict(side="under", line=47.5, label="Menos de 47.5"),
        spread=dict(side="home", line=3.0, label="ATL +3.0"),
    )
    _save_pred("nfl", "A", "nfl", "Atlanta Falcons", "Kansas City Chiefs", pred, KICK)
    rows = [
        _row("nfl", "nfl", "A", KICK, "Atlanta Falcons", "Kansas City Chiefs",
             "total", "under", 47.5, "Under 47.5", typ="main", ev=4.1, conf="Alta", odds=-105),
        _row("nfl", "nfl", "A", KICK, "Atlanta Falcons", "Kansas City Chiefs",
             "spread", "home", 3.0, "ATL +3", typ="suggestion", ev=1.2, conf="Media"),
        # no: lado contrario
        _row("nfl", "nfl", "A", KICK, "Atlanta Falcons", "Kansas City Chiefs",
             "ml", "home", None, "Atlanta Falcons ML", typ="suggestion", ev=8.0, conf="Alta", odds=150),
        # no: misma cara, línea distinta
        _row("nfl", "nfl", "A", KICK, "Atlanta Falcons", "Kansas City Chiefs",
             "total", "under", 45.5, "Under 45.5", typ="suggestion", ev=6.0, conf="Alta"),
    ]
    # unique constraint is (league,eid,market,selection) — two unders can't both insert
    # so the 45.5 under would collide with 47.5 under. Use a second game for the line miss.
    assert R.record_rows(rows[:3]) == 3
    _save_pred("nfl", "B", "nfl", "Dallas Cowboys", "San Francisco 49ers",
               dict(winner=dict(side="away", p=0.55, src="pfinal"),
                    total=dict(side="under", line=47.5), score=dict(home=20, away=24)),
               KICK + 60)
    assert R.record_rows([_row("nfl", "nfl", "B", KICK + 60, "Dallas Cowboys", "San Francisco 49ers",
                               "total", "under", 45.5, "Under 45.5", ev=6.0, conf="Alta")]) == 1

    rep = C.agreeing_picks(now=NOW, date=DAY, include_live=False)
    labels = [it["pick"] for it in rep["items"]]
    assert "Under 47.5" in labels and "ATL +3" in labels
    assert "Atlanta Falcons ML" not in labels
    assert "Under 45.5" not in labels
    assert rep["n"] == 2
    # orden: mayor EV primero (4.1 then 1.2)
    assert labels[0] == "Under 47.5" and labels[1] == "ATL +3"
    u = rep["items"][0]
    assert u["game"] == "Kansas City Chiefs @ Atlanta Falcons"
    assert u["sport"] == "nfl" and u["type"] == "main"
    assert u["odds_txt"] == "-105" and u["book"] == "ESPN BET"
    assert abs(u["p_final"] - 0.54) < 1e-9 and abs(u["ev"] - 4.1) < 1e-9
    assert u["confidence"] == "Alta"
    assert u["live"] is False
    assert "CDMX" in (u["kickoff_cdmx"] or "")
    assert u["href"] == "#/juego/nfl/A"
    txt = C.format_agreeing_text(rep)
    assert "Under 47.5" in txt and "ATL +3" in txt
    assert "no garantiza" in txt.lower() or "no es una garantía" in txt.lower() or "no una garantía" in txt.lower()
    assert "Atlanta Falcons ML" not in txt


def test_empty_does_not_invent(db):
    rep = C.agreeing_picks(now=NOW, date=DAY, include_live=True)
    assert rep["n"] == 0 and rep["items"] == []
    txt = C.format_agreeing_text(rep)
    assert "no hay picks" in txt.lower()
    assert "no invento" in txt.lower()
    r = CHAT.agreeing_reply(now=NOW, date=DAY)
    assert r["agreeing"] is True and r["llm"] is False and r["n"] == 0
    assert "no invento" in r["text"].lower()


def test_include_live_optional_and_skips_graded(db):
    pred = dict(winner=dict(side="away", p=0.6, src="pfinal"), score=dict(home=1, away=2))
    started = NOW - 1800  # already kicked off, same CDMX day
    _save_pred("nba", "L1", "nba", "Utah Jazz", "Lakers", pred, started, now=started - 3600)
    assert R.record_rows([_row("nba", "nba", "L1", started, "Utah Jazz", "Lakers",
                               "ml", "away", None, "Lakers ML", ev=2.0, conf="Media", odds=130)]) == 1
    pre = C.agreeing_picks(now=NOW, date=DAY, include_live=False)
    assert pre["n"] == 0
    live = C.agreeing_picks(now=NOW, date=DAY, include_live=True)
    assert live["n"] == 1 and live["items"][0]["live"] is True and live["items"][0]["pick"] == "Lakers ML"
    # un pick ya calificado no entra
    with history._lock:
        c = R._c()
        c.execute("UPDATE picks SET status='GANADO' WHERE eid='L1'")
        c.commit()
    assert C.agreeing_picks(now=NOW, date=DAY, include_live=True)["n"] == 0


def test_tennis_set_markets_excluded_unless_pred_covers(db):
    start = KICK + 300
    pred = dict(
        winner=dict(side="home", p=0.6, src="pfinal"),
        total=dict(side="under", line=25.5),
        spread=dict(side="away", line=-2.0),
        score=dict(home=2, away=0),
    )
    _save_pred("atp", "187506", "tenis", "Ben Shelton", "Arthur Fils", pred, start, hid="s", aid="f")
    rows = [
        _row("tenis", "atp", "187506", start, "Ben Shelton", "Arthur Fils",
             "ml", "home", None, "Ben Shelton ML", typ="main", ev=1.5, hid="s", aid="f"),
        _row("tenis", "atp", "187506", start, "Ben Shelton", "Arthur Fils",
             "sspread", "away", 1.5, "Arthur Fils +1.5 sets", typ="suggestion", ev=9.9, hid="s", aid="f"),
        _row("tenis", "atp", "187506", start, "Ben Shelton", "Arthur Fils",
             "stotal", "under", 2.5, "Under 2.5 sets", typ="suggestion", ev=8.8, hid="s", aid="f"),
        _row("tenis", "atp", "187506", start, "Ben Shelton", "Arthur Fils",
             "total", "under", 25.5, "Under 25.5 juegos", typ="suggestion", ev=2.2, hid="s", aid="f"),
    ]
    assert R.record_rows(rows) == 4
    labels = [it["pick"] for it in C.agreeing_picks(now=NOW, date=DAY, include_live=False)["items"]]
    assert "Ben Shelton ML" in labels and "Under 25.5 juegos" in labels
    assert "Arthur Fils +1.5 sets" not in labels
    assert "Under 2.5 sets" not in labels
    # fútbol: local primero
    assert any(it["game"].startswith("Ben Shelton vs") for it in C.agreeing_picks(now=NOW, date=DAY)["items"])


def test_sorts_by_ev_then_confidence(db):
    pred = dict(winner=dict(side="home", p=0.62, src="pfinal"), score=dict(home=110, away=100))
    _save_pred("nba", "10", "nba", "Celtics", "Heat", pred, KICK)
    # same EV, Alta should beat Media; higher EV first
    rows = [
        _row("nba", "nba", "10", KICK, "Celtics", "Heat", "ml", "home", None, "Celtics ML A", typ="main", ev=3.0, conf="Media"),
    ]
    # unique (league,eid,market,selection) — need different games for two MLs of same side
    assert R.record_rows(rows) == 1
    pred2 = dict(winner=dict(side="home", p=0.62, src="pfinal"), score=dict(home=110, away=100))
    _save_pred("nba", "11", "nba", "Bucks", "Hawks", pred2, KICK)
    assert R.record_rows([_row("nba", "nba", "11", KICK, "Bucks", "Hawks",
                               "ml", "home", None, "Bucks ML", ev=5.0, conf="Baja")]) == 1
    pred3 = dict(winner=dict(side="home", p=0.62, src="pfinal"), score=dict(home=110, away=100))
    _save_pred("nba", "12", "nba", "Knicks", "Nets", pred3, KICK)
    assert R.record_rows([_row("nba", "nba", "12", KICK, "Knicks", "Nets",
                               "ml", "home", None, "Knicks ML", ev=3.0, conf="Alta")]) == 1
    labels = [it["pick"] for it in C.agreeing_picks(now=NOW, date=DAY, include_live=False)["items"]]
    assert labels == ["Bucks ML", "Knicks ML", "Celtics ML A"]


def test_tomorrow_is_not_included(db):
    tomorrow = KICK + 86400
    pred = dict(winner=dict(side="home", p=0.6, src="pfinal"), score=dict(home=2, away=1))
    _save_pred("nfl", "Z", "nfl", "Ravens", "Chargers", pred, tomorrow)
    assert R.record_rows([_row("nfl", "nfl", "Z", tomorrow, "Ravens", "Chargers",
                               "ml", "home", None, "Ravens ML", ev=7.0)]) == 1
    assert C.agreeing_picks(now=NOW, date=DAY, include_live=True)["n"] == 0
