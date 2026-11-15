"""Regresión KC-ATL (nov 2026) + invariante de la pizarra + confianza PASS/EV."""
import json, time
from datetime import datetime, timezone
from server import record as R, history, prediction as PRED, quality as Q
from server import consistency as C

# 2026-11-15T18:00Z = 12:00 America/Mexico_City
KICK = 1_794_765_600
NOW = KICK - 3600  # 11:00 UTC / 05:00 CDMX, still pre
EID = "401873058"


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def kcatl_game(state="pre", start=KICK):
    return dict(sport="nfl", league="nfl", id=EID, state=state, date=iso(start),
                home=dict(id="1", name="Atlanta Falcons", short="Falcons", abbr="ATL"),
                away=dict(id="12", name="Kansas City Chiefs", short="Chiefs", abbr="KC"))


def kcatl_pred():
    return dict(
        winner=dict(side="away", p=0.608, probs=dict(home=0.392, away=0.608), src="pfinal"),
        score=dict(home=22, away=24, p=0.08),
        total=dict(side="under", line=47.5, p=0.52, label="Menos de 47.5", line_src="mercado"),
        spread=dict(side="home", line=3.0, p=0.51, label="Atlanta Falcons +3.0", line_src="mercado"),
    )


def kcatl_analysis(state="pre", start=KICK, published=False):
    pred = kcatl_pred()
    lean = dict(market="Spread", side="home", line=3.0, label="Atlanta Falcons +3.0",
                price=-110, p_final=0.49, p_model=0.50, p_nv=0.52, ev=-4.3, edge=-2, status="PASS")
    atl_ml = dict(market="ML", side="home", line=None, label="Atlanta Falcons ML",
                  price=150, p_final=0.403, ev=0.79, edge=1, status="LEAN")
    under = dict(market="Total", side="under", line=47.5, label="Under 47.5",
                 price=-110, p_final=0.52, ev=-3.9, status="LEAN")
    return dict(
        game=kcatl_game(state, start), pred=pred, odds=dict(book="ESPN BET"),
        picks=dict(lean=lean, published=published, status="PASS",
                   candidates=[atl_ml, lean, under], suggestions=[],
                   confidence=dict(level="Alta")),
    )


def _insert_stale(now=NOW, start=KICK):
    """Los tres picks de la captura: principal ATL ML, ATL +3.5, Under 45.5."""
    g = kcatl_game("pre", start)
    base = dict(sport="nfl", league="nfl", eid=EID, start_ts=start,
                home="Atlanta Falcons", away="Kansas City Chiefs",
                home_id="1", away_id="12", created_at=int(now), source="live",
                book="ESPN BET", p_model=0.5, p_final=0.4, p_nv=0.5, edge=0, basis="modelo")
    rows = [
        dict(base, market="ml", selection="home", line=None, label="Atlanta Falcons ML",
             odds=150, type="main"),
        dict(base, market="spread", selection="home", line=3.5, label="ATL +3.5",
             odds=-110, type="suggestion"),
        dict(base, market="total", selection="under", line=45.5, label="Under 45.5",
             odds=-110, type="suggestion"),
    ]
    assert R.record_rows(rows) == 3
    # apertura
    with history._lock:
        c = R._c()
        c.execute("UPDATE picks SET open_line=line, open_odds=odds, state='ACTUALIZADO' WHERE eid=?", (EID,))
        c.commit()


def test_kcatl_stale_pending_reconciled_before_kickoff(db):
    PRED.save(kcatl_game(), kcatl_pred(), now=NOW)
    _insert_stale()
    before = C.pending_mismatches(now=NOW, since_ts=KICK - 10, only_open=True)
    assert len(before) == 3
    reasons = sorted((x["reason"], x["market"]) for x in before)
    assert ("lado", "ml") in reasons
    assert ("línea", "spread") in reasons
    assert ("línea", "total") in reasons

    a = kcatl_analysis()
    # published=False (PASS): no se inventa un principal nuevo; se reconcilia lo viejo
    n = R.record_analysis(a, now=NOW)
    assert n == 0
    rows = {r["market"]: r for r in R.game_rows("nfl", EID)}
    assert rows["ml"]["status"] == "ANULADO" and rows["ml"]["state"] in ("CANCELADO", "CONTRADICE")
    assert rows["spread"]["status"] == "PENDIENTE" and rows["spread"]["line"] == 3.0
    assert rows["spread"]["state"] == "ACTUALIZADO"
    assert rows["total"]["status"] == "PENDIENTE" and rows["total"]["line"] == 47.5
    assert rows["total"]["state"] == "ACTUALIZADO"
    after = C.pending_mismatches(now=NOW, since_ts=KICK - 10, only_open=True)
    assert after == []


def test_kcatl_started_picks_are_not_rewritten(db):
    PRED.save(kcatl_game(), kcatl_pred(), now=NOW)
    _insert_stale(now=NOW, start=KICK)
    # el juego ya empezó
    a = kcatl_analysis(state="in")
    R.record_analysis(a, now=KICK + 120)
    rows = {r["market"]: r for r in R.game_rows("nfl", EID)}
    assert rows["ml"]["status"] == "PENDIENTE" and rows["ml"]["selection"] == "home" and rows["ml"]["odds"] == 150
    assert rows["spread"]["line"] == 3.5
    assert rows["total"]["line"] == 45.5
    locked = C.pending_mismatches(now=KICK + 120, since_ts=KICK - 10, only_open=False)
    open_ = C.pending_mismatches(now=KICK + 120, since_ts=KICK - 10, only_open=True)
    assert len(locked) == 3 and open_ == []


def test_kcatl_actualizado_is_rechecked(db):
    """Tras un ACTUALIZADO a la línea de la predicción, el lado contrario sigue cancelándose."""
    PRED.save(kcatl_game(), kcatl_pred(), now=NOW)
    _insert_stale()
    # un refresh intermedio que mueve la línea del total a 47.5 vía extract no aplica (PASS);
    # enforce_pred debe dejar Under 47.5 y cancelar ATL ML.
    R.record_analysis(kcatl_analysis(), now=NOW + 60)
    # segundo refresh (como un ACTUALIZADO posterior)
    R.record_analysis(kcatl_analysis(), now=NOW + 120)
    assert C.pending_mismatches(now=NOW + 120, since_ts=KICK - 10, only_open=True) == []
    ml = next(r for r in R.game_rows("nfl", EID) if r["market"] == "ml")
    assert ml["status"] == "ANULADO"


def test_confidence_not_alta_on_pass_or_neg_ev():
    a = kcatl_analysis()
    Q.apply(a)
    assert a["picks"]["status"] == "PASS"
    assert a["picks"]["confidence"]["level"] != "Alta"
    assert a["picks"]["confidence"]["level"] == "no aplica"
    # ev negativo también, aunque el status fuera PICK
    assert C.clamp_display_confidence(dict(level="Alta"), "PICK", -4.3)["level"] == "no aplica"
    assert C.clamp_display_confidence(dict(level="Alta"), "PICK", 5.0)["level"] == "Alta"


def test_modelo_distinguishes_pick_pfinal_from_winner():
    pred = kcatl_pred()
    lean = dict(market="Spread", side="home", line=3.0, p_final=0.49, p_model=0.50, p_nv=0.52, ev=-4.3)
    sig = Q._modelo(lean, pred)
    detail = sig["detail"]
    assert "pFinal del pick 49.0%" in detail
    assert "ganador (mismo pFinal del juego): away (60.8%)" in detail
    assert "pFinal 49.0%" not in detail.split("del pick")[0]  # no va suelto al inicio
    assert not C.analysis_winner_conflict(detail, pred)
    # el wording viejo sí se detecta
    legacy = "pFinal 49.0% · modelo 50.0% · mercado s/vig 52.0% · ganador pFinal: away (60.8%)"
    assert C.analysis_winner_conflict(legacy, pred)


def test_pred_winner_is_pfinal_source():
    pred = kcatl_pred()
    assert pred["winner"]["side"] == "away" and pred["winner"]["src"] == "pfinal"
    assert pred["score"]["away"] == 24 and pred["score"]["home"] == 22
    assert pred["total"]["side"] == "under" and pred["total"]["line"] == 47.5
    assert pred["spread"]["side"] == "home" and pred["spread"]["line"] == 3.0


def test_slate_invariant_zero_open_mismatches(db):
    """Pizarra de varios deportes: tras reconciliar, cero desajustes pendientes abiertos."""
    PRED.save(kcatl_game(), kcatl_pred(), now=NOW)
    _insert_stale()
    # un NBA limpio (coincide)
    nba_start = KICK + 7200
    nba = dict(sport="nba", league="nba", eid="99", start_ts=nba_start,
               home="Utah Jazz", away="Portland Trail Blazers", home_id="26", away_id="22",
               created_at=NOW, source="live", book="X", p_model=.6, p_final=.58, p_nv=.55,
               edge=3, basis="modelo", market="ml", selection="home", line=None,
               label="Utah ML", odds=-110, type="main")
    assert R.record_rows([nba]) == 1
    PRED.save(dict(sport="nba", league="nba", id="99", state="pre", date=iso(nba_start),
                   home=dict(id="26", name="Utah Jazz"), away=dict(id="22", name="Portland Trail Blazers")),
              dict(winner=dict(side="home", p=.58, src="pfinal"), score=dict(home=110, away=100)),
              now=NOW)
    # un tenis con ML que contradice + un sspread que NO debe contar (mercado de sets)
    ten_start = KICK + 10800
    ten_rows = [
        dict(sport="tenis", league="atp", eid="187506", start_ts=ten_start,
             home="Ben Shelton", away="Arthur Fils", home_id="s", away_id="f",
             created_at=NOW, source="live", book="X", p_model=.6, p_final=.4, p_nv=.5,
             edge=0, basis="modelo", market="ml", selection="away", line=None,
             label="Arthur Fils ML", odds=150, type="main"),
        dict(sport="tenis", league="atp", eid="187506", start_ts=ten_start,
             home="Ben Shelton", away="Arthur Fils", home_id="s", away_id="f",
             created_at=NOW, source="live", book="X", p_model=.5, p_final=.5, p_nv=.5,
             edge=0, basis="modelo", market="sspread", selection="away", line=1.5,
             label="Arthur Fils +1.5 sets", odds=-110, type="suggestion"),
    ]
    assert R.record_rows(ten_rows) == 2
    PRED.save(dict(sport="tenis", league="atp", id="187506", state="pre", date=iso(ten_start),
                   home=dict(id="s", name="Ben Shelton"), away=dict(id="f", name="Arthur Fils")),
              dict(winner=dict(side="home", p=.60, src="pfinal"),
                   total=dict(side="under", line=25.5),
                   spread=dict(side="away", line=-2.0),
                   score=dict(home=2, away=0)),
              now=NOW)

    before = C.pending_mismatches(now=NOW, since_ts=KICK - 10, only_open=True)
    # 3 KC-ATL + 1 tenis ML; el sspread se omite
    assert len(before) == 4
    assert not any(x["market"] == "sspread" for x in before)

    # reconcilia toda la pizarra abierta (como el ciclo de grade)
    r = R.reconcile_open_to_pred(now=NOW)
    assert r["cancelled"] >= 2  # ATL ML + Fils ML
    after = C.pending_mismatches(now=NOW, since_ts=KICK - 10, only_open=True)
    assert after == [], after
    # el sspread de sets sigue pendiente (no se tocó)
    ss = next(x for x in R.game_rows("atp", "187506") if x["market"] == "sspread")
    assert ss["status"] == "PENDIENTE" and ss["line"] == 1.5


def test_chat_consistency_flags_and_single_winner():
    a = kcatl_analysis()
    a["record"] = [
        dict(market="ml", selection="home", line=None, label="Atlanta Falcons ML", status="PENDIENTE"),
        dict(market="spread", selection="home", line=3.5, label="ATL +3.5", status="PENDIENTE"),
        dict(market="total", selection="under", line=45.5, label="Under 45.5", status="PENDIENTE"),
    ]
    a["picks"]["analysis"] = dict(signals=[Q._modelo(a["picks"]["lean"], a["pred"])])
    cons = C.chat_consistency(a)
    assert cons["ganador_pfinal"]["side"] == "away"
    assert abs(cons["ganador_pfinal"]["p"] - 0.608) < 1e-9
    assert cons["contradicciones"]  # ATL ML y líneas
    # análisis ya usa el wording nuevo: no se marca pred_vs_analisis
    items = C.audit_from_analysis(a)
    types = {x["type"] for x in items}
    assert "pred_vs_registered" in types
    assert "pred_vs_analisis" not in types
    # confianza Alta + PASS en el objeto crudo (antes de apply) sí se audita
    assert "confidence_vs_pass_ev" in types


def test_compare_pred_vs_picks_uses_real_rows_only(db):
    """No inventa cuotas: sin `lines` el hit% cuenta y el ROI de predicciones queda sin precio."""
    with history._lock:
        c = history._open()
        PRED._c()  # asegura tabla
        payload = json.dumps(dict(winner=dict(side="home", p=.6),
                                  total=dict(side="under", line=47.5),
                                  spread=dict(side="home", line=3.0)))
        c.execute("INSERT INTO predictions(sport,league,eid,start_ts,home,away,home_id,away_id,payload,created_at,updated_at,status,r_ml,r_total,r_spread) "
                  "VALUES('nfl','nfl','1',?,?,?,?,?,?,?,?,'GRADED','GANADO','PERDIDO','GANADO')",
                  (KICK, "ATL", "KC", "1", "12", payload, NOW, NOW))
        c.execute("INSERT INTO picks(sport,league,eid,start_ts,home,away,market,selection,odds,type,status,units,created_at) "
                  "VALUES('nfl','nfl','2',?,'ATL','KC','ml','away',150,'main','PERDIDO',-1,?)",
                  (KICK, NOW))
        c.commit()
    out = C.compare_pred_vs_picks()
    pr = out["predictions"]["overall"]
    mn = out["mains"]["overall"]
    assert pr["hit"] == 2 and pr["miss"] == 1 and pr["n_priced"] == 0 and pr["roi"] is None
    assert mn["hit"] == 0 and mn["miss"] == 1 and mn["units"] == -1 and abs(mn["roi"] + 100) < 1e-9
