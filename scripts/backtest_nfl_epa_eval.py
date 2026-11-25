import json, math
from collections import defaultdict
G = json.load(open("games.json"))
Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
SIG, K, HFA0, HW = 13.5, 6, 1.8, 60
rows = []
for season in (2024, 2025, 2026):
    gl = [g for g in G if g["season"] == season]
    hist = []
    for day in sorted(set(g["date"] for g in gl)):
        tg = defaultdict(list)
        for g in hist: tg[g["home"]].append(g); tg[g["away"]].append(g)
        n = len(hist); hfa = (sum(g["hs"] - g["as_"] for g in hist) + HW * HFA0) / (n + HW)
        r = defaultdict(float)
        for _ in range(40):
            nr = {}
            for t, l in tg.items():
                s = 0
                for g in l:
                    s += (g["hs"] - g["as_"] - hfa + r[g["away"]]) if g["home"] == t else (g["as_"] - g["hs"] + hfa + r[g["home"]])
                nr[t] = s / len(l)
            m = sum(nr.values()) / len(nr) if nr else 0
            r = defaultdict(float, {t: v - m for t, v in nr.items()})
        rat = {t: r[t] * len(tg[t]) / (len(tg[t]) + K) for t in r}
        # EPA/jugada ofensiva y permitida (defensa), con ajuste por rival simple
        off = defaultdict(lambda: [0.0, 0]); de = defaultdict(lambda: [0.0, 0])
        for g in hist:
            for t, o in ((g["home"], g["away"]), (g["away"], g["home"])):
                e = g["epa"][t]; off[t][0] += e[0]; off[t][1] += e[1]; de[o][0] += e[0]; de[o][1] += e[1]
        def net(t):
            if not off[t][1] or not de[t][1]: return 0.0
            ng = len(tg[t])
            return (off[t][0] / off[t][1] - de[t][0] / de[t][1]) * ng / (ng + K)
        for g in [x for x in gl if x["date"] == day]:
            h, a = g["home"], g["away"]
            if g["st"] != "REG": continue
            rows.append(dict(season=season, week=g["week"], y=1.0 if g["hs"] > g["as_"] else (0.0 if g["hs"] < g["as_"] else None),
                             mu=rat.get(h, 0) - rat.get(a, 0) + hfa, dn=net(h) - net(a), nh=len(tg[h]), na=len(tg[a])))
        hist += [x for x in gl if x["date"] == day]
rows = [x for x in rows if x["y"] is not None and x["nh"] >= 2 and x["na"] >= 2]
def score(rs, c):
    b = ll = 0
    for x in rs:
        p = Phi((x["mu"] + c * x["dn"]) / SIG); p = min(max(p, 1e-6), 1 - 1e-6)
        b += (p - x["y"]) ** 2; ll += -(x["y"] * math.log(p) + (1 - x["y"]) * math.log(1 - p))
    return round(b / len(rs), 4), round(ll / len(rs), 4)
tr = [x for x in rows if x["season"] in (2024, 2025)]; te = [x for x in rows if x["season"] == 2026]
grid = [i * 2.0 for i in range(0, 41)]
best = min(grid, key=lambda c: score(tr, c)[1])
res = dict(n_train=len(tr), n_test=len(te), coef=best,
           train_base=score(tr, 0), train_epa=score(tr, best),
           test_base=score(te, 0), test_epa=score(te, best),
           test_2025_base=score([x for x in tr if x["season"] == 2025], 0))
# check también: entrenando sólo 2024 y probando 2025
t24 = [x for x in rows if x["season"] == 2024]; t25 = [x for x in rows if x["season"] == 2025]
b24 = min(grid, key=lambda c: score(t24, c)[1])
res["fold_2025"] = dict(coef=b24, base=score(t25, 0), epa=score(t25, b24))
print(json.dumps(res, indent=1)); json.dump(res, open("result.json", "w"), indent=1)
