from server import board as B, record as REC

def test_metrics_coherentes_mismo_signo():
    m = B.metrics(-105, 0.5023754258268024, 0.4891657638136511, 0.6542865389780412)
    assert m["p_implied"] == 51.2 and m["edge_pp"] == -1.0 and m["ev_pct"] == -1.9
    assert (m["edge_pp"] > 0) == (m["ev_pct"] > 0)
    assert m["divergence_high"] is True          # 65.4 vs 48.9 > 10 pp
    m2 = B.metrics(+150, 0.45, 0.40, 0.47)
    assert m2["ev_pct"] == 12.5 and m2["edge_pp"] == 5.0 and m2["divergence_high"] is False

def test_sin_cuota_no_es_pick_ni_cuenta_en_roi():
    assert B.metrics(None, 0.6) is None
    assert REC.profit("PERDIDO", None) is None and REC.profit("GANADO", None) is None
    assert REC.profit("PERDIDO", -110) == -1.0 and abs(REC.profit("GANADO", -110) - 0.9091) < 1e-3

def test_agg_misma_muestra():
    rows = [dict(status="GANADO", odds=-110), dict(status="PERDIDO", odds=-110), dict(status="PERDIDO", odds=None), dict(status="GANADO", odds=None)]
    a = B._agg(rows)
    assert a["W"] == 1 and a["L"] == 1 and a["n_unpriced"] == 2 and a["n_priced"] == 2 and a["hit_pct"] == 50.0
