"""榆园杯单日排程。单位为午夜起算分钟，所有区间左闭右开。"""
from itertools import combinations, product
from time import perf_counter
from sample import MATCHES, VENUES

SLOTS = list(product(range(780, 1080, 60), VENUES))

def clash(a, b, gap=0):
    return a < b + 60 + gap and b < a + 60 + gap

def issues(plan, rules, complete=True,matches=MATCHES):
    errors = []
    def add(rule, ids, why):
        errors.append(dict(rule=rule, matches=ids, reason=why))
    if complete and set(plan) != set(matches):
        add("B3", sorted(set(matches)^set(plan)), "对阵集合不完整")
    for m,(t,v) in plan.items():
        if m not in matches or (t,v) not in SLOTS:
            add("B1", [m], "开球或场地超出范围")
            continue
        for r in rules:
            if r["kind"]=="blocked" and set(r["subjects"]) & {*matches[m],v} and t < r["end"] and r["start"] < t+60:
                add(r["id"], [m], r["quote"])
    for a,b in combinations(plan,2):
        if a not in matches or b not in matches: continue
        t,v=plan[a]
        u,w=plan[b]
        if v==w and clash(t,u): add("B3",[a,b],"同一场地重复占用")
        if set(matches[a]) & set(matches[b]) and clash(t,u,60):
            add("B2",[a,b],"同队重叠或休息不足")
        for r in rules:
            if r["kind"]=="shared" and clash(t,u):
                x,y=r["subjects"]
                if (x in matches[a] and y in matches[b]) or (y in matches[a] and x in matches[b]):
                    add(r["id"],[a,b],r["quote"])
    return errors

def diff(old,new,matches=MATCHES):
    if set(old)!=set(new): raise ValueError("改期必须保留全部比赛")
    moved=[m for m in old if tuple(old[m])!=tuple(new[m])]
    return moved, sorted({team for m in moved for team in matches[m]})

def penalty(plan,rules,matches=MATCHES):
    return sum((1020-t if r["kind"]=="late" else t-780)//60
               for m,(t,v) in plan.items() for r in rules
               if r["kind"] in ("early","late") and set(matches[m]) & set(r["subjects"]))

def solve(rules,old=None,budget=3,matches=MATCHES,reconsider=None):
    start=perf_counter()
    best=score=None
    nodes=0
    timeout=False
    options={m:[p for p in SLOTS if not issues({m:p},rules,False,matches)] for m in matches}
    def visit(part):
        nonlocal nodes,best,score,timeout
        if perf_counter()-start>=budget:
            timeout=True
            return
        nodes+=1
        if len(part)==len(matches):
            moved,teams=diff(old,part,matches) if old else ([],[])
            cost=(len(moved),len(teams),penalty(part,rules,matches),sum(t for t,v in part.values()))
            if reconsider:
                cost+=(sum(tuple(part[m])==tuple(slot) for m,slot in reconsider.items()),)
            if score is None or cost<score: best,score=part.copy(),cost
            return
        m=list(matches)[len(part)]
        for p in options[m]:
            part[m]=p
            if not issues(part,rules,False,matches): visit(part)
            del part[m]
            if timeout: break
    visit({})
    return dict(status=("FEASIBLE" if best else "UNKNOWN") if timeout else ("OPTIMAL" if best else "INFEASIBLE"),
                plan=best,score=score,nodes=nodes,seconds=round(perf_counter()-start,4),budget=budget,
                empty_domains=[m for m in options if not options[m]])
