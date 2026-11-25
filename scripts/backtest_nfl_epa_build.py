import csv, gzip, json, sys
csv.field_size_limit(10**9)
games = {}; te = {}
for y in (2024, 2025, 2026):
    with gzip.open(f"pbp_{y}.csv.gz", "rt", newline="") as f:
        for r in csv.DictReader(f):
            gid = r["game_id"]
            if gid not in games:
                games[gid] = dict(id=gid, season=int(r["season"]), week=int(r["week"]), date=r["game_date"], st=r["season_type"],
                                  home=r["home_team"], away=r["away_team"], hs=None, as_=None)
            if r.get("home_score") not in (None, ""): games[gid]["hs"] = float(r["home_score"]); games[gid]["as_"] = float(r["away_score"])
            if r["play_type"] in ("pass", "run") and r["epa"] not in ("", "NA") and r["posteam"]:
                k = (gid, r["posteam"]); a = te.setdefault(k, [0.0, 0, 0.0, 0])
                a[0] += float(r["epa"]); a[1] += 1
                if r["play_type"] == "pass": a[2] += float(r["epa"]); a[3] += 1
out = []
for gid, g in games.items():
    h = te.get((gid, g["home"])); a = te.get((gid, g["away"]))
    if not h or not a or g["hs"] is None: continue
    g["epa"] = {g["home"]: h, g["away"]: a}; out.append(g)
out.sort(key=lambda g: (g["date"], g["id"]))
json.dump(out, open("games.json", "w"))
print(len(out), {y: sum(1 for g in out if g["season"] == y) for y in (2024, 2025, 2026)})
