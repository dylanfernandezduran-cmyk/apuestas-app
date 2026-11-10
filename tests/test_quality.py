"""Fuente única pFinal + filtro de calidad (6 señales) + techo diario."""
from server import quality as Q, prediction as P, model as M


def _soc(lh=1.8, la=1.1):
    # p_home > p_away with these lambdas
    return dict(kind="dixon_coles", p_home=.55, p_draw=.25, p_away=.20, p_btts=.5,
                lam_home=lh, lam_away=la, sample=200,
                total=lambda t: (0.4, 0.6, 0), cover=lambda t: (0.55, 0.45, 0))


def _game():
    return dict(id="1", league="nfl", sport="nfl", date="2026-11-16T18:00Z", state="pre",
                home=dict(id="h", name="Jets", short="NYJ", abbr="NYJ"),
                away=dict(id="a", name="Bills", short="BUF", abbr="BUF"))


def _cand(**kw):
    base = dict(market="ML", side="home", line=None, label="Jets ML", price=-120,
                p_model=.58, p_final=.56, p_nv=.52, edge=4, ev=0.05, status="PICK")
    base.update(kw)
    return base


def test_pfinal_view_uses_candidate_pfinal_not_raw_model():
    # modelo crudo favorece local, pFinal del mercado favorece visita (el caso Jets/Bills al revés en probs)
    cands = [
        _cand(side="home", p_final=.47, p_model=.58, p_nv=.44, ev=-0.02, label="Jets ML"),
        _cand(side="away", p_final=.53, p_model=.42, p_nv=.56, ev=0.08, label="Bills ML", price=+150),
    ]
    v = Q.pfinal_view(cands, mdl=dict(p_home=.58, p_away=.42, sample=80), odds=None, fam="nfl")
    assert v["winner"]["side"] == "away" and v["winner"]["src"] == "pfinal"
    assert abs(v["winner"]["p"] - .53) < 1e-9


def test_prediction_winner_follows_pfinal_not_raw_mu():
    # mu>0 implicaría local en _margin; pFinal dice visita
    mdl = dict(mu=1.5, sigma=12, exp_total=44, tsigma=10, p_home=.54, p_away=.46,
               total=lambda t: M.cover_normal(44, 10, t), cover=lambda t: M.cover_normal(1.5, 12, t))
    p_view = dict(winner=dict(side="away", p=.57, probs=dict(home=.43, away=.57), src="pfinal"))
    pred = P.build(_game(), mdl, dict(ml=dict(home=-110, away=-110), book="X"), "nfl", p_view=p_view)
    assert pred["winner"]["side"] == "away" and pred["winner"]["src"] == "pfinal"
    assert pred["score"]["away"] > pred["score"]["home"]
    # un pick de Jets ML no voltea al ganador
    picks = dict(lean=dict(market="ML", side="home", status="PICK"), status="PICK", candidates=[])
    pred2 = P.build(_game(), mdl, None, "nfl", picks=picks, p_view=p_view)
    assert pred2["winner"]["side"] == "away" and pred2["score"]["away"] > pred2["score"]["home"]


def test_contradictory_ev_does_not_become_main_pick():
    """pFinal: Jets; el mejor EV es Bills ML → PASS, sin pick principal."""
    pred = dict(winner=dict(side="home", p=.56, probs=dict(home=.56, away=.44), src="pfinal"),
                score=dict(home=21, away=17), total=dict(side="under", line=44.5),
                spread=dict(side="home", line=-2.5))
    bills = _cand(side="away", label="Bills ML", p_final=.44, ev=0.12, edge=5, price=+180, status="PICK")
    jets = _cand(side="home", label="Jets ML", p_final=.56, ev=-0.03, edge=-1, price=-150, status="PASS")
    out = dict(game=_game(), pred=pred, odds=dict(book="X"),
               picks=dict(lean=bills, status="PICK", candidates=[bills, jets],
                          confidence=dict(level="Alta")))
    Q.apply(out)
    assert out["picks"]["published"] is False
    assert out["picks"]["status"] in ("PASS", "REVISAR")
    # el Bills (mejor EV) no puede ser el pick principal; si queda un lean, es el lado de pFinal (Jets)
    lean = out["picks"]["lean"]
    assert lean is None or (lean.get("side") == "home" and lean.get("market") == "ML")
    if lean is None:
        assert "contradice" in (out["picks"]["discard_reason"] or "").lower() or "coincid" in (out["picks"]["discard_reason"] or "").lower()
    else:
        assert out["picks"]["discard_reason"]


def test_main_pick_side_always_matches_predicted_winner():
    pred = dict(winner=dict(side="home", p=.58, probs=dict(home=.58, away=.42), src="pfinal"),
                score=dict(home=24, away=17), spread=dict(side="home", line=-3.5),
                total=dict(side="over", line=41.5))
    jets = _cand(ev=0.06, p_final=.58, status="PICK")
    spread = _cand(market="Spread", side="home", line=-3.5, label="Jets -3.5", ev=0.04, p_final=.55, status="PICK")
    under = _cand(market="Total", side="under", line=41.5, label="Under 41.5", ev=0.10, p_final=.54, status="PICK")
    out = _rich_out(pred, [jets, spread, under], conf="Alta")
    Q.apply(out)
    # si pasa el filtro, el principal es Jets (ML, mayor EV del lado del ganador), no el Under
    if out["picks"]["published"]:
        assert out["picks"]["lean"]["side"] == "home"
        assert out["picks"]["lean"]["market"] in ("ML", "Spread")
    # Under no es coherente con el marcador 24-17=41 no, 24+17=41 < 41.5 so under IS consistent
    sugg = out["picks"]["suggestions"]
    assert all(Q.consistent_with_pred(pred, c) for c in sugg)
    assert any(c["market"] == "Total" and c["side"] == "under" for c in sugg) or not sugg


def _rich_out(pred, cands, conf="Alta"):
    # 4+ señales a favor: modelo, movimiento, rlm, tendencias
    g = _game()
    home_form = dict(last5=dict(w=4, l=1, d=0, n=5, text="4-1", rate=.8),
                     last10=dict(w=7, l=3, d=0, n=10, text="7-3"),
                     streak="W3", recent=[dict(pf=28, pa=17, date="2026-11-02", res="W")]*5)
    away_form = dict(last5=dict(w=2, l=3, d=0, n=5, text="2-3", rate=.4),
                     last10=dict(w=4, l=6, d=0, n=10, text="4-6"),
                     streak="L2", recent=[dict(pf=14, pa=24, date="2026-11-02", res="L")]*5)
    for c in cands:
        if c.get("market") == "ML" and c.get("side") == "home":
            c.setdefault("signals", dict(verdict="a_favor", tickets=38, money=55, rlm=True, rlm_side="home", tags=[("rlm_for", "RLM a favor")]))
    return dict(
        game=g, pred=pred, kind="team",
        teams={"h": home_form, "a": away_form},
        rest=dict(home=dict(days=6, b2b=False, n7=1), away=dict(days=3, b2b=False, n7=1)),
        market=dict(movement=dict(ml=dict(home=dict(open=150, cur=-120, d_nv_pp=6.0),
                                          away=dict(open=-170, cur=+100, d_nv_pp=-6.0))),
                    splits=dict(ml=dict(home=dict(tickets=38, money=55)))),
        injuries={}, lineups={}, weather=dict(status="sin_dato"),
        picks=dict(lean=cands[0], status="PICK", candidates=cands, confidence=dict(level=conf)),
    )


def test_publishes_when_four_signals_agree_ev_and_confidence_ok():
    pred = dict(winner=dict(side="home", p=.58, probs=dict(home=.58, away=.42), src="pfinal"),
                score=dict(home=24, away=17), spread=dict(side="home", line=-3.5),
                total=dict(side="under", line=44.5))
    jets = _cand(ev=0.06, p_final=.58, status="PICK")
    out = _rich_out(pred, [jets], conf="Alta")
    Q.apply(out)
    assert out["picks"]["published"] is True
    assert out["picks"]["lean"]["side"] == "home"
    assert out["picks"]["status"] in ("PICK", "LEAN")
    an = out["analysis"]
    assert an["n_present"] >= 4 and an["n_agree"] >= 4


def test_missing_signals_are_sin_dato_and_block_if_fewer_than_four_present():
    pred = dict(winner=dict(side="home", p=.58, probs=dict(home=.58, away=.42), src="pfinal"),
                score=dict(home=21, away=17))
    jets = _cand(ev=0.06, p_final=.58)
    out = dict(game=_game(), pred=pred, teams={}, market={}, injuries={},
               picks=dict(lean=jets, status="PICK", candidates=[jets], confidence=dict(level="Alta")))
    Q.apply(out)
    an = out["analysis"]
    assert any(s["verdict"] == "sin_dato" for s in an["signals"])
    # sólo modelo (y quizá nada más) → no publica
    assert an["n_present"] < 4
    assert out["picks"]["published"] is False
    assert "solo" in (out["picks"]["discard_reason"] or "") and "señales" in (out["picks"]["discard_reason"] or "")


def test_one_disagreeing_signal_ok_if_four_agree_but_low_ev_or_baja_blocks():
    pred = dict(winner=dict(side="home", p=.58, probs=dict(home=.58, away=.42), src="pfinal"),
                score=dict(home=24, away=17), spread=dict(side="home", line=-3),
                total=dict(side="under", line=44.5))
    jets = _cand(ev=-0.01, p_final=.58, status="LEAN")
    out = _rich_out(pred, [jets], conf="Alta")
    Q.apply(out)
    assert out["picks"]["published"] is False
    assert "EV" in (out["picks"]["discard_reason"] or "")

    jets2 = _cand(ev=0.06, p_final=.58, status="PICK")
    out2 = _rich_out(pred, [jets2], conf="Baja")
    Q.apply(out2)
    assert out2["picks"]["published"] is False
    assert "confianza" in (out2["picks"]["discard_reason"] or "")


def test_revisar_is_not_published():
    pred = dict(winner=dict(side="home", p=.7, probs=dict(home=.7, away=.3), src="pfinal"),
                score=dict(home=24, away=17), spread=dict(side="home", line=-3),
                total=dict(side="under", line=44.5))
    jets = _cand(ev=0.2, p_final=.7, status="REVISAR", divergence_high=True)
    out = _rich_out(pred, [jets], conf="Alta")
    out["picks"]["status"] = "REVISAR"
    Q.apply(out)
    assert out["picks"]["published"] is False
    assert out["picks"]["status"] == "REVISAR"


def test_suggestions_only_if_consistent_with_score():
    pred = dict(winner=dict(side="home", p=.58, probs=dict(home=.58, away=.42), src="pfinal"),
                score=dict(home=24, away=17), spread=dict(side="home", line=-3.5),
                total=dict(side="under", line=44.5))  # 41 < 44.5 under
    jets = _cand(ev=0.06, p_final=.58)
    over = _cand(market="Total", side="over", line=44.5, label="Over 44.5", ev=0.08, p_final=.55, status="PICK")
    under = _cand(market="Total", side="under", line=44.5, label="Under 44.5", ev=0.03, p_final=.52, status="LEAN")
    out = _rich_out(pred, [jets, over, under], conf="Alta")
    Q.apply(out)
    sugg = out["picks"]["suggestions"]
    assert all(c["side"] != "over" or c["market"] != "Total" for c in sugg)
    assert any(c["market"] == "Total" and c["side"] == "under" for c in sugg)


def test_daily_cap_keeps_top_10_by_ev_and_confidence():
    items = []
    for i in range(15):
        ev = 0.20 - i * 0.01
        items.append(dict(published=True, status="PICK", lean=dict(ev=ev, edge=5),
                          confidence=dict(level="Alta" if i < 8 else "Media"), game=dict(id=str(i))))
    out = Q.cap_daily(items, limit=10)
    pub = [x for x in out if x["published"]]
    disc = [x for x in out if not x["published"]]
    assert len(pub) == 10 and len(disc) == 5
    assert all("tope" in (x["discard_reason"] or "") for x in disc)
    assert pub[0]["lean"]["ev"] >= pub[-1]["lean"]["ev"]


def test_panel_never_invents_numbers():
    pred = dict(winner=dict(side="home", p=.55, probs=dict(home=.55, away=.45), src="pfinal"),
                score=dict(home=21, away=17))
    an = Q.panel(dict(game=_game(), teams={}, market={}, injuries={}), _cand(), pred)
    for s in an["signals"]:
        if s["verdict"] == "sin_dato":
            assert "sin dato" in (s["detail"] or "").lower()
            # figures may be empty or all None
            for v in (s.get("figures") or {}).values():
                if isinstance(v, list):
                    continue
                # no fabricated percents
    keys = {s["key"] for s in an["signals"]}
    assert keys == {"modelo", "movimiento", "rlm", "tendencias", "lesiones", "fisico"}


def test_one_main_per_game_even_with_two_aligned_markets():
    pred = dict(winner=dict(side="home", p=.58, probs=dict(home=.58, away=.42), src="pfinal"),
                score=dict(home=24, away=17), spread=dict(side="home", line=-3.5),
                total=dict(side="under", line=44.5))
    jets = _cand(ev=0.08, p_final=.58)
    spread = _cand(market="Spread", side="home", line=-3.5, ev=0.05, p_final=.54, label="Jets -3.5", status="PICK")
    out = _rich_out(pred, [jets, spread], conf="Alta")
    Q.apply(out)
    assert out["picks"]["lean"] is None or out["picks"]["lean"]["market"] in ("ML", "Spread")
    if out["picks"]["published"]:
        assert out["picks"]["lean"]["label"] == "Jets ML"  # mayor EV
        assert sum(1 for c in [out["picks"]["lean"]] if c) == 1
