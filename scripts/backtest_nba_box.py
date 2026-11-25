import httpx, json, os, concurrent.futures as cf
E="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
games=json.load(open("games.json"))
out=json.load(open("box.json")) if os.path.exists("box.json") else {}
c=httpx.Client(timeout=30)
def stat(lst,name):
    for s in lst:
        if s.get("name")==name or s.get("abbreviation")==name: return s.get("displayValue")
def one(g):
    try:
        d=c.get(E,params={"event":g["id"]}).json()
    except Exception as e: return g["id"],None
    res={}
    for t in (d.get("boxscore") or {}).get("teams") or []:
        st=t.get("statistics") or []
        res[t["team"]["id"]]=dict(fg=stat(st,"fieldGoalsMade-fieldGoalsAttempted"),ft=stat(st,"freeThrowsMade-freeThrowsAttempted"),
            oreb=stat(st,"offensiveRebounds"),tov=stat(st,"turnovers") or stat(st,"totalTurnovers"))
    pl={}
    for t in (d.get("boxscore") or {}).get("players") or []:
        tid=t["team"]["id"]; rows=[]
        for sg in t.get("statistics") or []:
            keys=sg.get("keys") or sg.get("labels") or []
            for a in sg.get("athletes") or []:
                ath=a.get("athlete") or {}
                stats=dict(zip(keys,a.get("stats") or []))
                rows.append(dict(id=ath.get("id"),dnp=bool(a.get("didNotPlay")),min=stats.get("minutes"),pm=stats.get("plusMinus"),pts=stats.get("points")))
        pl[tid]=rows
    return g["id"],dict(team=res,players=pl)
todo=[g for g in games if g["id"] not in out]
with cf.ThreadPoolExecutor(12) as ex:
    for i,(gid,r) in enumerate(ex.map(one,todo)):
        if r: out[gid]=r
        if i%200==0: print(i,flush=True); json.dump(out,open("box.json","w"))
json.dump(out,open("box.json","w")); print("done",len(out))
