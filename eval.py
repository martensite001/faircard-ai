"""평가: dev(32)에서 τ 결정 → 동결된 test(40, SHA-256 기록)에서 규칙 단독 vs 하이브리드 비교.
지표: 문장 단위 micro P/R/F1 (정답 라벨 일치 기준), 부트스트랩 95% CI(2,000회, seed=42)."""
import json, random, sys
from faircard.engine import classify
def load(p): return [json.loads(l) for l in open(p, encoding="utf-8")]
def score(data, use_rag, tau=0.45):
    tp=fp=fn=0; rows=[]
    for d in data:
        pred={r for r,_,_ in classify(d["s"], use_rag, tau)}; y=d["y"]
        t=int(bool(y) and y in pred); f_p=len(pred-{y}); f_n=int(bool(y) and y not in pred)
        tp+=t; fp+=f_p; fn+=f_n; rows.append((t,f_p,f_n))
    return prf(tp,fp,fn), rows
def prf(tp,fp,fn):
    P=tp/(tp+fp) if tp+fp else 0; R=tp/(tp+fn) if tp+fn else 0
    return {"TP":tp,"FP":fp,"FN":fn,"P":round(P,3),"R":round(R,3),"F1":round(2*P*R/(P+R),3) if P+R else 0}
def boot(rows, B=2000, seed=42):
    rng=random.Random(seed); f=[]
    for _ in range(B):
        s=[rows[rng.randrange(len(rows))] for _ in rows]; m=prf(*map(sum,zip(*s))); f.append(m["F1"])
    f.sort(); return [round(f[int(.025*B)],3), round(f[int(.975*B)],3)]
dev, test = load("data/dev.jsonl"), load("data/test_heldout.jsonl")
grid={t:score(dev,True,t)[0]["F1"] for t in [0.20,0.25,0.30,0.35,0.40,0.45]}
best=max(grid, key=lambda t:(grid[t], t))
res={"tau_grid_dev":grid,"tau_selected":best}
for name,data in [("dev",dev),("test",test)]:
    for mode,rag in [("rule_only",False),("hybrid",True)]:
        m,rows=score(data,rag,best); m["F1_CI95"]=boot(rows); res[f"{name}_{mode}"]=m
errs=[]
for d in test:
    pred={r for r,_,_ in classify(d["s"],True,best)}
    if (d["y"] and d["y"] not in pred) or (pred-{d["y"]}): errs.append({"s":d["s"],"y":d["y"],"pred":sorted(pred)})
res["test_hybrid_errors"]=errs
json.dump(res,open("out/eval_result.json","w"),ensure_ascii=False,indent=1)
print(json.dumps({k:v for k,v in res.items() if k!="test_hybrid_errors"},ensure_ascii=False,indent=1)); print("errors:",len(errs))
for e in errs: print(e)
