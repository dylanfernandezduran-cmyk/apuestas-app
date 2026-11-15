"""Aprendizaje del récord: segmentos, shrinkage, umbral de muestra, coherencia pick vs predicción."""
from server import learn, quality as Q, prediction as PRED, record as REC
from tests.test_prediccion import soc_model, game
from server import model as M


def _row(**kw):
    base = dict(sport="nba", market="total", selection="under", line=220.5, odds=-110,
                p_final=0.55, ev=4.0, conf_level="Media", status="GANADO", units=0.91,
                start_ts=1_700_000_000, type="main", open_odds=-110)
    base.update(kw)
    return base


def test_wilson_and_shrink_are_conservative():
    p, lo, hi = learn.wilson(20, 40)
    assert abs(p - 0.5) < 1e-9 and lo < 0.5 < hi
    # encoge un 80% de acierto con n chico hacia 50
    s = learn.shrink(80, 10, 50, n0=40)
    assert 50 < s < 80


def test_segment_block_requires_min_n_and_negative_ci():
    # 40 underdogs de tenis todos perdidos a -110 → ROI e acierto claramente negativos
    rows = [_row(sport="tenis", market="ml", selection="away", odds=150, ev=6, status="PERDIDO", units=-1,
                 start_ts=1_700_000_000 + i) for i in range(40)]
    # y 40 nba totals under ganados para contraste
    rows += [_row(sport="nba", market="total", selection="under", status="GANADO", units=0.91,
                  start_ts=1_700_000_000 + 100 + i) for i in range(40)]
    data = learn.build_segments(rows, min_n=30)
    actions = {s["label"]: s["action"] for s in data["segments"]}
    # el segmento tenis (o underdog) debe bloquearse; nba under se mantiene o es positivo
    blocked = [s for s in data["segments"] if s["action"] == "block"]
    assert blocked, actions
    assert any("tenis" in s["label"] or "underdog" in s["label"] for s in blocked)
    # n insuficiente no decide
    tiny = learn.build_segments(rows[:5], min_n=30)
    assert all(s["action"] == "insufficient" for s in tiny["segments"])


def test_feedback_blocks_matching_segment_only():
    bad = [_row(sport="tenis", market="ml", selection="away", odds=180, status="PERDIDO", units=-1,
                start_ts=1_700_000_000 + i) for i in range(40)]
    data = learn.build_segments(bad, min_n=30)
    fb = learn.feedback(_row(sport="tenis", market="ml", selection="away", odds=180, status="PENDIENTE"), data)
    assert fb["action"] == "block" and fb["reason"]
    # un segmento que no aplica no bloquea un nba under
    fb2 = learn.feedback(_row(sport="nba", market="total", selection="under", odds=-110, status="PENDIENTE"), data)
    assert fb2["action"] == "keep"


def test_similar_reports_n_and_hit():
    rows = [_row(status="GANADO", units=0.91, start_ts=1_700_000_000 + i) for i in range(20)]
    rows += [_row(status="PERDIDO", units=-1, start_ts=1_700_000_000 + 50 + i) for i in range(10)]
    data = learn.build_segments(rows, min_n=10)
    sim = learn.similar(_row(status="PENDIENTE"), data["segments"], min_n=10)
    assert sim and sim["n"] >= 10 and sim["hit"] is not None
    assert "No es una garantía" in (sim["note"] or "")


def test_ev_reconstructed_from_pfinal_and_odds_not_invented():
    # +100 con p_final 0.55 → EV +10%
    ev = learn.ev_of(dict(ev=None, p_final=0.55, odds=100))
    assert ev is not None and abs(ev - 10) < 0.05
    assert learn.ev_of(dict(ev=None, p_final=0.55, odds=None)) is None


def test_same_pick_requires_side_and_line():
    pred = dict(winner=dict(side="home", p=0.6), total=dict(side="over", line=22.5),
                spread=dict(side="home", line=-3.5), score=dict(home=24, away=20))
    assert Q.same_pick(pred, dict(market="Total", side="over", line=22.5))
    assert not Q.same_pick(pred, dict(market="Total", side="over", line=21.5))
    assert not Q.same_pick(pred, dict(market="Total", side="under", line=22.5))
    assert Q.same_pick(pred, dict(market="Spread", side="home", line=-3.5))
    assert not Q.same_pick(pred, dict(market="Spread", side="away", line=3.5))  # lado contrario
    # visitante +3.5 ≡ local -3.5, mismo lado away ≠ home
    assert not Q.same_pick(pred, dict(market="ML", side="away"))
    assert Q.same_pick(pred, dict(market="ML", side="home"))


def test_prediction_keeps_published_total_and_quality_drops_contradiction():
    mdl = soc_model(1.9, 0.8)  # local favorito, over 2.5 natural
    g = game()
    # pFinal: gana local. Un Over 2.5 publicado debe quedar Over 2.5 en la predicción.
    picks = dict(published=True, status="PICK",
                 lean=dict(market="Total", side="over", line=2.5, label="Over 2.5", status="PICK", ev=5, p_final=0.62))
    pred = PRED.build(g, mdl, None, "soccer", picks=picks, p_view=dict(winner=dict(side="home", p=0.6, probs={"home":0.6,"draw":0.2,"away":0.2}, src="pfinal")))
    assert pred["total"]["side"] == "over" and pred["total"]["line"] == 2.5
    assert pred["total"].get("aligned") == "pick"
    assert pred["winner"]["side"] == "home"


def test_extract_does_not_register_opposite_ml():
    g = dict(sport="nba", league="nba", id="1", state="pre",
             date="2099-01-01T20:00:00Z",
             home=dict(name="A", id="1"), away=dict(name="B", id="2"))
    pred = dict(winner=dict(side="home", p=0.7, src="pfinal"), score=dict(home=110, away=100))
    lean = dict(market="ML", side="away", label="B ML", price=150, p_final=0.3, ev=8)
    a = dict(game=g, pred=pred, picks=dict(published=True, lean=lean, confidence=dict(level="Alta"),
                                           candidates=[lean]))
    rows = REC.extract(a, now=1_000_000_000)  # start is 2099, now is past
    assert all(not (r["market"]=="ml" and r["selection"]=="away") for r in rows)


def test_walk_forward_does_not_overfit_tiny_train():
    rows = [_row(status="GANADO" if i % 2 == 0 else "PERDIDO",
                 units=0.91 if i % 2 == 0 else -1,
                 start_ts=1_700_000_000 + i * 86400) for i in range(10)]
    def decide(r, pred, train):
        return False, "train insuficiente" if len(train) < 30 else (True, None)
    out = learn.walk_forward(rows, {}, decide, week_secs=7*86400, min_train=30)
    # con pocas semanas y min_train=30, no debe inventar un filtro que "mejora" con n=10
    assert out["n_old"] == 10
    assert out["n_new"] == 0 or out["n_new"] <= out["n_old"]
