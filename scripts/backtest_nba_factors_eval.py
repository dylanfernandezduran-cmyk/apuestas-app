import json, math
import numpy as np
R=json.load(open("rows.json"))
Phi=lambda x:0.5*(1+math.erf(x/math.sqrt(2)))
tr=[r for r in R if r["date"]<"2026-02-15"]; te=[r for r in R if r["date"]>="2026-02-15"]
print("train",len(tr),"test",len(te))
def fit(feats, rows):
    X=np.array([[r[f] for f in feats] for r in rows]) if feats else np.zeros((len(rows),0))
    y=np.array([r["margin"]-r["base"] for r in rows])
    if not feats: return []
    c,*_=np.linalg.lstsq(X,y,rcond=None); return list(c)
def fit_sig(feats,c,rows):
    res=[r["margin"]-(r["base"]+sum(ci*r[f] for ci,f in zip(c,feats))) for r in rows]; return float(np.std(res))
def score(feats,c,sig,rows):
    b=ll=0
    for r in rows:
        mu=r["base"]+sum(ci*r[f] for ci,f in zip(c,feats)); p=min(max(Phi(mu/sig),1e-6),1-1e-6); y=r["y"]
        b+=(p-y)**2; ll+=-(y*math.log(p)+(1-y)*math.log(1-p))
    return b/len(rows), ll/len(rows)
# net rating replacement
def sc_net(rows,sig,w):
    b=ll=0
    for r in rows:
        mu=(1-w)*r["base"]+w*r["net"]; p=min(max(Phi(mu/sig),1e-6),1-1e-6); y=r["y"]; b+=(p-y)**2; ll+=-(y*math.log(p)+(1-y)*math.log(1-p))
    return b/len(rows),ll/len(rows)

print("---- sigma 12.5 fijo")
for feats in (["b2b"],["restd"],["form"],["miss"],["b2b","form","miss"],["b2b","miss"],["form","miss"]):
    c=fit(feats,tr); print(feats,[round(float(x),3) for x in c],score(feats,c,12.5,te))
# net blend + factors
print("---- pace for totals RMSE")
import statistics
for name,fn in (("lg",lambda r:None),):
    pass

base=score([],[],12.5,te); print("base sigma12.5",base)
c=[]; s=fit_sig([],c,tr); print("base fitted sigma",round(s,2),score([],[],s,te))
for f in ["b2b","restd","form","miss","prev"]:
    c=fit([f],tr); s=fit_sig([f],c,tr); print(f,[round(x,3) for x in c],round(s,2),score([f],c,s,te))
