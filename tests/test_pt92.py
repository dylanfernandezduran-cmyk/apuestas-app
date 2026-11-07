"""pt92u: récord por día (CDMX), partido de tenis con cambio de jugador, líneas basura de una casa."""
import os, time, tempfile, importlib
os.environ["APUESTAS_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from server import history, record as REC, grading, market

def _ins(c, eid, ts, status, units=None, sport="nba"):
    c.execute("INSERT INTO picks(sport,league,eid,start_ts,home,away,market,selection,line,label,odds,type,created_at,status,units) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (sport, sport, eid, ts, "H", "A", "ml", "home", None, "H ML", -110, "main", ts - 99, status, units))

def test_record_by_day_cdmx():
    history._conn = None if hasattr(history, "_conn") else None
    REC.reset_for_tests()
    with history._lock:
        c = REC._c()
        # 2026-11-07 05:30 UTC = 6 nov 23:30 CDMX -> cuenta para el 6; 2026-11-07 06:30 UTC = 7 nov 00:30 CDMX
        t6 = 1894253400; t7 = t6 + 3600
        assert REC.cdmx_date(t6) == "2030-01-09" and REC.cdmx_date(t7) == "2030-01-10"
        _ins(c, "a", t6, "GANADO", 0.91); _ins(c, "b", t7, "PERDIDO", -1.0); _ins(c, "c", t7 + 60, "PENDIENTE", sport="nhl"); _ins(c, "d", t7 + 99, "ANULADO")
        c.commit()
    d6, d7 = REC.day("2030-01-09"), REC.day("2030-01-10")
    assert (d6["summary"]["W"], d6["summary"]["L"], d6["summary"]["units"]) == (1, 0, 0.91)
    assert (d7["summary"]["W"], d7["summary"]["L"], d7["summary"]["pending"], d7["summary"]["void"]) == (0, 1, 1, 1)
    assert set(d7["by_sport"]) == {"nba", "nhl"}
    days = {x["date"]: x for x in REC.days()}
    assert days["2030-01-09"]["W"] == 1 and days["2030-01-10"]["L"] == 1

def test_tennis_changed_players_void():
    comp = {"status": {"type": {"name": "STATUS_FINAL", "state": "post"}}, "competitors": [{"id": "10386", "winner": True}, {"id": "11396"}]}
    assert grading.parse_tennis_event(comp, "5309", "10386")["state"] == "void"

def test_drop_bad_total_line():
    bk = lambda i, ln: {"id": i, "kind": "book", "total": {"over": {"line": ln, "price": -110}, "under": {"line": ln, "price": -110}}}
    books = [bk("a", 226.5), bk("b", 226.5), bk("c", 17.5), bk("d", 225.5)]
    market._drop_bad_lines(books, None)
    assert "total" not in books[2] and all("total" in b for i, b in enumerate(books) if i != 2)

# ---------------- picks estrictos y coherentes
from server import strict as ST

def _c(market, side, edge, p, verdict="neutral"):
    return dict(market=market, side=side, edge=edge, p_final=p, label=f"{market} {side}", signals=dict(verdict=verdict), status="PICK")

def test_strict_one_official_and_gates():
    cands = [_c("ML", "home", 6.0, .66), _c("Spread", "home", 3.0, .58), _c("Total", "over", 1.0, .52), _c("ML", "away", 2.5, .56, "en_contra")]
    pk = ST.apply(dict(candidates=cands, confidence=dict(level="Media")), {})
    assert [c["label"] for c in pk["official"]] == ["ML home"] and pk["status"] == "PICK"
    assert "señales de mercado en contra" in cands[3]["why_not"] and any("edge" in w for w in cands[2]["why_not"])
    assert cands[0]["score"] > cands[1]["score"] and 0 <= cands[0]["score"] <= 100

def test_strict_second_pick_only_other_market_and_strong():
    cands = [_c("ML", "home", 8.0, .70, "a_favor"), _c("Total", "under", 7.0, .68, "a_favor")]
    pk = ST.apply(dict(candidates=cands, confidence=dict(level="Alta")), {})
    assert len(pk["official"]) == 2
    pk = ST.apply(dict(candidates=[_c("ML", "home", 8.0, .70, "a_favor"), _c("Spread", "home", 7.0, .68, "a_favor")], confidence=dict(level="Alta")), {})
    assert len(pk["official"]) == 1                                     # ML + hándicap del mismo lado: correlacionado, sólo uno

def test_strict_never_contradicts_prediction():
    cands = [_c("ML", "away", 4.0, .60), _c("Total", "over", 1.0, .51)]
    pk = ST.apply(dict(candidates=cands, confidence=dict(level="Media")), {})
    ST.finalize(pk, dict(winner=dict(side="home"), total=dict(side="over")))
    assert pk["official"] == [] and pk["status"] == "PASS"
    assert all(c["side"] != "away" for c in pk["considered"]) and (pk["lean"] is None or pk["lean"]["side"] != "away")

def test_strict_key_injury_blocks():
    pk = ST.apply(dict(candidates=[_c("ML", "home", 6.0, .65)], confidence=dict(level="Alta")), dict(key_injury=True))
    assert pk["official"] == [] and "jugador clave en duda" in pk["candidates"][0]["why_not"]

def test_strict_score_floor():
    pk = ST.apply(dict(candidates=[_c("ML", "home", 2.1, .555)], confidence=dict(level="Baja")), {})
    assert pk["official"] == [] and any("puntaje" in w for w in pk["candidates"][0]["why_not"])
