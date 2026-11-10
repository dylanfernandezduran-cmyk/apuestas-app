"""Ítems de revisión: QB titular fuera, divergencia alta, ranking por EV, CLV."""
import pytest
from server import model as M
from server import data as D
from server import record as R
from server.odds import am_to_dec

def _R(rh=2.0, ra=0.0, n=10, hfa=1.8):
    return dict(family="football", rating={"1": rh, "2": ra},
                off={"1": 22.0, "2": 22.0}, **{"def": {"1": 22.0, "2": 22.0}},
                n={"1": n, "2": n}, hfa=hfa, lg_pts=44.0)

def test_extra_margin_and_total_shift_nfl_model():
    base = M.margin_model(_R(), "1", "2")
    tot = M.margin_model(_R(), "1", "2", extra_total=-M.NFL_QB_OUT_TOTAL)
    qb = M.margin_model(_R(), "1", "2", extra_margin=-M.NFL_QB_OUT_MARGIN, extra_total=-M.NFL_QB_OUT_TOTAL)
    assert tot["exp_total"] == pytest.approx(base["exp_total"] - M.NFL_QB_OUT_TOTAL)
    assert qb["mu"] == pytest.approx(base["mu"] - M.NFL_QB_OUT_MARGIN)
    assert qb["p_home"] < base["p_home"]

def test_nfl_qb_out_home_starter_confirmed():
    lead = {"1": [dict(cat="Passing Yards", name="Kyler Murray", id="3139477", pos="QB")],
            "2": [dict(cat="Passing Yards", name="Josh Allen", id="2", pos="QB")]}
    inj = {"1": [dict(id="3139477", name="Kyler Murray", status="Out", pos="QB")], "2": []}
    r = D.nfl_qb_out("1", "2", inj, lead)
    assert r["applied"] and r["extra_margin"] == pytest.approx(-M.NFL_QB_OUT_MARGIN)
    assert r["extra_total"] == pytest.approx(-M.NFL_QB_OUT_TOTAL)
    assert "Kyler Murray" in r["notes"][0]

def test_nfl_qb_out_away_nets_with_home():
    lead = {"1": [dict(cat="Passing Yards", name="A", id="1", pos="QB")],
            "2": [dict(cat="Passing Yards", name="B", id="2", pos="QB")]}
    inj = {"1": [dict(id="1", name="A", status="Injured Reserve")],
           "2": [dict(id="2", name="B", status="Inactive")]}
    r = D.nfl_qb_out("1", "2", inj, lead)
    assert r["extra_margin"] == pytest.approx(0.0)  # ambos fuera: se anulan
    assert r["extra_total"] == pytest.approx(-2 * M.NFL_QB_OUT_TOTAL)

def test_nfl_qb_out_ignores_coachs_decision():
    lead = {"1": [dict(cat="Passing Yards", name="Backup", id="9", pos="QB")]}
    inj = {"1": [dict(id="9", name="Backup", status="Coach's Decision", pos="QB")]}
    r = D.nfl_qb_out("1", "2", inj, lead)
    assert not r["applied"] and r["extra_margin"] == 0

def test_cand_marks_high_divergence_and_apply_demotes_pick():
    c = M._cand("ML", "home", "Vikings ML", +164, 0.55, 0.38, 0.5)
    assert c["divergence_high"] is True and c["divergence"] > 10
    c["status"] = "PICK"
    M.apply_confidence([c], dict(level="Alta"))
    assert c["status"] == "REVISAR" and c.get("downgraded") and c.get("flag") == "Divergencia alta"
    assert c["edge_display"] is None
    # no se promociona a PICK aunque la confianza sea Alta
    assert c["status"] != "PICK"

def test_no_divergence_keeps_pick_when_confidence_ok():
    c = M._cand("ML", "home", "Home ML", -110, 0.54, 0.52, 0.5)
    assert not c["divergence_high"]
    c["status"] = "PICK"
    M.apply_confidence([c], dict(level="Media"))
    assert c["status"] == "PICK" and c["edge_display"] == c["edge"]

def test_rank_by_ev_and_confidence_not_raw_edge():
    a = dict(ev=1.0, edge=10, conf_level="Baja", divergence_high=False)
    b = dict(ev=5.0, edge=3, conf_level="Media", divergence_high=False)
    c = dict(ev=20.0, edge=15, conf_level="Alta", divergence_high=True)
    s = sorted([a, b, c], key=M.rank_key)
    assert s[0] is b and s[1] is a and s[2] is c

def test_clv_positive_when_close_shortens():
    # apertura +164 (dec 2.64), cierre +140 (dec 2.40) → positivo
    v = R.clv_pct(+164, +140)
    assert v == pytest.approx((am_to_dec(164) / am_to_dec(140) - 1) * 100)
    assert v > 0
    assert R.clv_pct(None, -110) is None
    assert R.clv_pct(-110, -110) == pytest.approx(0.0)

def test_summary_includes_clv(db):
    R.reset_for_tests()
    import time
    from server import history
    NOW = int(time.time())
    with history._lock:
        c = R._c()
        base = dict(sport="nfl", league="nfl", start_ts=NOW, home="A", away="B", home_id="1", away_id="2",
                    line=None, label="x", p_model=.5, p_final=.5, p_nv=.5, edge=0, basis="modelo",
                    created_at=NOW, source="live")
        def add(eid, typ, st, open_odds, close_odds, sel="home"):
            d = dict(base, eid=eid, type=typ, odds=close_odds, sport="nfl", league="nfl", market="ml", selection=sel, book="P")
            c.execute(f"INSERT INTO picks({R.COLS}) VALUES ({','.join('?'*22)})", tuple(d[k] for k in R.COLS.split(",")))
            c.execute("UPDATE picks SET status=?, units=?, open_odds=? WHERE eid=? AND league=?",
                      (st, R.profit(st, close_odds), open_odds, eid, "nfl"))
        add("c1", "main", "GANADO", +164, +140)
        add("c2", "main", "PERDIDO", -110, -110)
        c.commit()
    s = R.summary(typ="main")
    assert s["clv_n"] == 2
    assert s["clv_avg"] == pytest.approx(round((R.clv_pct(+164, +140) + 0.0) / 2, 2))
    assert s["graded"] == 2
