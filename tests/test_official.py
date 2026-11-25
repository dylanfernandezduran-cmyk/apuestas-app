"""Probabilidad oficial NRNM: una sola probabilidad por mercado; la distribución calibrada la reproduce."""
from server import official as OFF, model as M

def _mdl(mu=5.354653979939256, T=224.9974897608667, sg=12.5, ts=18.0):
    from server.odds import norm_cdf
    ph = 1 - norm_cdf(-mu / sg)
    return dict(kind="margen", mu=mu, sigma=sg, tsigma=ts, exp_total=T, p_home=ph, p_away=1 - ph, p_draw=None, n_home=17, n_away=18, sample=.85,
                cover=lambda t: M.cover_normal(mu, sg, t), total=lambda t: M.cover_normal(T, ts, t))

def _cands(mdl):
    nv = dict(ml=dict(home=0.617381798305548, away=0.382618201694452), spread=dict(home=.4817, away=.5183), total=dict(over=.5043, under=.4957))
    odds = dict(ml=dict(home=-180, away=151), spread=dict(home=dict(line=-4.5, price=-102), away=dict(line=4.5, price=-119)),
                total=dict(over=dict(line=219.5, price=-112), under=dict(line=219.5, price=-108)), nv=nv)
    return M.build_candidates(mdl, odds, "New York Knicks", "Cleveland Cavaliers")

def test_knicks_official_and_calibrated_distribution():
    mdl = _mdl(); cs = _cands(mdl)
    cal, info = OFF.calibrate(mdl, cs, "basketball"); OFF.apply(cs, cal, "basketball")
    ml = {c["side"]: c for c in cs if c["market"] == "ML"}
    assert abs(ml["home"]["p_final"] - 0.6215) < 0.0005          # 8.5% × 66.6% + 91.5% × 61.7%
    assert abs(ml["home"]["ev"] - (-3.32)) < 0.05
    assert abs(cal["p_home"] - ml["home"]["p_final"]) < 1e-6      # la distribución reproduce la prob. oficial
    ov = next(c for c in cs if c["market"] == "Total" and c["side"] == "over")
    assert abs(cal["total"](219.5)[0] - ov["p_final"]) < 1e-6
    sp = next(c for c in cs if c["market"] == "Spread" and c["side"] == "home")
    assert abs(sp["p_final"] - cal["cover"](4.5)[0]) < 1e-9 and sp.get("p_src") == "calibrada"
    assert 3.5 < info["exp_margin"] < 4.2                          # margen calibrado < 4.5 => Cavs +4.5 más probable
    assert sp["p_final"] < 0.5

def test_soccer_calibration_matches_1x2():
    mdl = M.soccer_model(dict(att={1: 1.2, 2: .9}, **{"def": {1: .9, 2: 1.1}}, lg_home=1.5, lg_away=1.1, n={1: 20, 2: 20}), 1, 2)
    cs = [dict(market="ML", side="home", p_final=.50), dict(market="ML", side="away", p_final=.24), dict(market="ML", side="draw", p_final=.26)]
    cal, info = OFF.calibrate(mdl, cs, "soccer")
    assert abs(cal["p_home"] - .50) < 1e-3 and abs(cal["p_away"] - .24) < 1e-3
