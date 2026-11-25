import httpx, json, os, sys, concurrent.futures as cf
E="https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
c=httpx.Client(timeout=30)
teams=[t["team"]["id"] for t in c.get(E+"/teams",params={"limit":200}).json()["sports"][0]["leagues"][0]["teams"]]
games={}
def one(args):
    tid,season=args
    r=c.get(f"{E}/teams/{tid}/schedule",params={"season":season,"seasontype":2}); return r.json()
for season in (2026,2027):
    with cf.ThreadPoolExecutor(8) as ex:
        for d in ex.map(one,[(t,season) for t in teams]):
            for e in d.get("events") or []:
                comp=e["competitions"][0]
                if not comp["status"]["type"].get("completed"): continue
                h=next(x for x in comp["competitors"] if x["homeAway"]=="home"); a=next(x for x in comp["competitors"] if x["homeAway"]=="away")
                sc=lambda x: float((x.get("score") or {}).get("value")) if isinstance(x.get("score"),dict) else float(x.get("score"))
                try: hs,as_=sc(h),sc(a)
                except Exception: continue
                games[e["id"]]=dict(id=e["id"],date=e["date"],season=season,home=h["team"]["id"],away=a["team"]["id"],hs=hs,as_=as_,neutral=bool(comp.get("neutralSite")))
    print(season, sum(1 for g in games.values() if g["season"]==season))
json.dump(sorted(games.values(),key=lambda g:g["date"]),open("games.json","w"))
