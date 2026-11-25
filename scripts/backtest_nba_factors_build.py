import json, math
from collections import defaultdict
from datetime import datetime
G=json.load(open("games.json")); B=json.load(open("box.json"))
Phi=lambda x:0.5*(1+math.erf(x/math.sqrt(2)))
SIG=12.5; K=12; HFA0=2.3; HW=25
def d(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def poss(t):
    try:
        fgm,fga=map(float,t["fg"].split("-")); ftm,fta=map(float,t["ft"].split("-")); o=float(t["oreb"]); tv=float(t["tov"])
        return fga-o+tv+0.44*fta
    except Exception: return None
def mins(x):
    try: return float(x)
    except Exception: return 0.0
rows=[]
for season in (2026,2027):
    gl=[g for g in G if g["season"]==season]
    hist=[]  # previous games this season
    last=defaultdict(lambda:None)
    pstats=defaultdict(lambda: defaultdict(lambda:[0,0.0]))  # team->player->[games,min]
    prev_rating={}
    if season==2027: prev_rating=final_rating
    i=0
    dates=sorted(set(g["date"][:10] for g in gl))
    for day in dates:
        today=[g for g in gl if g["date"][:10]==day]
        # ratings from hist
        tg=defaultdict(list)
        for g in hist: tg[g["home"]].append(g); tg[g["away"]].append(g)
        nn=len(hist); hm=sum(g["hs"]-g["as_"] for g in hist)
        hfa=(hm+HW*HFA0)/(nn+HW)
        r=defaultdict(float)
        for _ in range(25):
            nr={}
            for t,l in tg.items():
                s=0
                for g in l:
                    if g["home"]==t: s+=g["hs"]-g["as_"]-hfa+r[g["away"]]
                    else: s+=g["as_"]-g["hs"]+hfa+r[g["home"]]
                nr[t]=s/len(l)
            m=sum(nr.values())/len(nr) if nr else 0
            r=defaultdict(float,{t:v-m for t,v in nr.items()})
        rat={t:r[t]*len(tg[t])/(len(tg[t])+K) for t in r}
        # net rating per 100 poss + pace
        off=defaultdict(lambda:[0.0,0.0]); de=defaultdict(lambda:[0.0,0.0]); pc=defaultdict(list)
        for g in hist:
            bx=B.get(g["id"],{}).get("team",{})
            ph,pa=poss(bx.get(g["home"],{})) if bx.get(g["home"]) else None, poss(bx.get(g["away"],{})) if bx.get(g["away"]) else None
            if not ph or not pa: continue
            p=(ph+pa)/2
            off[g["home"]][0]+=g["hs"];off[g["home"]][1]+=p; de[g["home"]][0]+=g["as_"];de[g["home"]][1]+=p
            off[g["away"]][0]+=g["as_"];off[g["away"]][1]+=p; de[g["away"]][0]+=g["hs"];de[g["away"]][1]+=p
            pc[g["home"]].append(p); pc[g["away"]].append(p)
        lgp=sum(sum(v) for v in pc.values())/max(1,sum(len(v) for v in pc.values())) if pc else 99
        def net(t):
            n=len(pc[t]);
            if not n: return 0.0
            o=off[t][0]/off[t][1]*100; dd=de[t][0]/de[t][1]*100
            return (o-dd)*n/(n+K)
        def pace(t):
            n=len(pc[t]); return ((sum(pc[t]) if n else 0)+K*lgp)/(n+K)
        def form(t):
            l=[g for g in tg[t]][-10:]
            if len(l)<3: return 0.0
            s=0
            for g in l:
                if g["home"]==t: s+=g["hs"]-g["as_"]-hfa+rat.get(g["away"],0)
                else: s+=g["as_"]-g["hs"]+hfa+rat.get(g["home"],0)
            return s/len(l)-rat.get(t,0)
        def missing(t,g):
            pl=B.get(g["id"],{}).get("players",{}).get(t)
            if pl is None: return None
            played={x["id"] for x in pl if not x["dnp"] and mins(x["min"])>0}
            m=0.0
            for pid,(ng,mn) in pstats[t].items():
                if ng>=5 and mn/ng>=20 and pid not in played: m+=(mn/ng)/48
            return m
        for g in today:
            h,a=g["home"],g["away"]
            if len(tg[h])<5 or len(tg[a])<5: continue
            rh,ra=rat.get(h,0),rat.get(a,0)
            def rest(t):
                l=last[t]
                return min(4,(d(g["date"])-d(l)).days) if l else 4
            rsh,rsa=rest(h),rest(a)
            mh,ma=missing(h,g),missing(a,g)
            rows.append(dict(id=g["id"],season=season,date=g["date"],y=1 if g["hs"]>g["as_"] else 0,margin=g["hs"]-g["as_"],total=g["hs"]+g["as_"],
              base=rh-ra+hfa, hfa=hfa, b2b=(1 if rsh<=1 else 0)-(1 if rsa<=1 else 0), restd=rsh-rsa,
              form=form(h)-form(a), net=(net(h)-net(a))*((pace(h)+pace(a))/2)/100+hfa,
              miss=(mh or 0)-(ma or 0), miss_ok=mh is not None and ma is not None,
              prev=(prev_rating.get(h,0)-prev_rating.get(a,0)), ng=min(len(tg[h]),len(tg[a])),
              pace=(pace(h)+pace(a))/2, lgp=lgp))
        for g in today:
            hist.append(g); last[g["home"]]=g["date"]; last[g["away"]]=g["date"]
            for t in (g["home"],g["away"]):
                for x in B.get(g["id"],{}).get("players",{}).get(t,[]):
                    if not x["dnp"] and mins(x["min"])>0:
                        s=pstats[t][x["id"]]; s[0]+=1; s[1]+=mins(x["min"])
    final_rating=dict(rat)
json.dump(rows,open("rows.json","w")); print(len(rows))
