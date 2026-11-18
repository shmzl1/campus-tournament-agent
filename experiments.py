import json
from pathlib import Path
from workflow import save
from engine import solve,issues,diff,penalty
from sample import MATCHES
def load(name): return json.loads(Path(name).read_text("utf8"))
def keys(items):
    return {(k,tuple(sorted(s)),a,b) for k,s,a,b in items}
def normalize(rules):
    return keys([(r["kind"],r["subjects"],r["start"],r["end"]) for r in rules])
def measure():
    gold=load("reference.json")
    a=[]; b=[]
    for name,case in [("main","主赛事"),("supplement","补充通知"),("normal","正常对照"),("injected","人工注入")]:
        d=load("evidence/"+name+".json")
        attempts=[x for x in d["attempts"] if x["version"]==1]
        target=keys(gold["主赛事" if name=="injected" else case])
        first=normalize(attempts[0]["rules"]); final=normalize(d["versions"][0]["rules"] if d["versions"] else d["rules"])
        events=[]
        for e in d["events"]:
            if e["role"]=="change": break
            events.append(e)
        baseline=events[:next(i for i,e in enumerate(events) if e["role"]=="review")]
        a.append(dict(case=case,run=d["run_id"],first_missing=len(target-first),first_extra=len(first-target),corrected=len((target-first)&final)+len((first-target)-final),introduced=len((final-target)-first)+len((target&first)-final),remaining=len(target-final),final_extra=len(final-target),baseline_valid=not issues(attempts[0]["result"]["plan"],attempts[0]["rules"]),calls=[len(baseline),len(events)],seconds=[round(sum(e["seconds"] for e in batch),2) for batch in (baseline,events)]))
    for name in ["main","team","active","tied","impossible"]:
        d=load("evidence/"+name+".json")
        attempt=d["attempts"][-1]; rules=attempt["rules"]; old=d["versions"][0]["plan"]
        for mode,ref in [("从头",None),("低扰动",old)]:
            r=solve(rules,ref,3); plan=r["plan"]
            if plan and issues(plan,rules): raise ValueError("未通过公共校验")
            counts=list(map(len,diff(old,plan))) if plan else [None,None]
            b.append(dict(case=name,mode=mode,run=d["run_id"],status=r["status"],moved=counts[0],teams=counts[1],soft=penalty(plan,rules) if plan else None,seconds=r["seconds"],budget=r["budget"],plan=plan))
    return dict(A=a,B=b)
def tables(result):
    lines=["### A　独立原文复核（深度突破候选）","",
           "|案例|首轮漏/多|纠正|新引入的规则字段错误|最终遗漏|模型调用（基线→复核）|模型秒数（基线→复核）|",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for r in result["A"]:
        lines.append(f'|{r["case"]}|{r["first_missing"]}/{r["first_extra"]}|{r["corrected"]}|{r["introduced"]}|{r["remaining"]}|{r["calls"][0]} → {r["calls"][1]}|{r["seconds"][0]:.2f} → {r["seconds"][1]:.2f}|')
    lines+=["","按类型、对象及时间比较规则集合。人工注入行的最终规则表已修复，仍有三条待确认意见，未发布。字段统计不包含自由文本误报。耗时仅累计模型请求；首版比较不包含后续改期。",
            "","### B　已公布赛程的低扰动改期（方向突破候选）","",
            "|同一变更|移动场次（从头→低扰动）|通知队数|偏好罚值|求解秒数|两法状态|",
            "|---|---:|---:|---:|---:|---|"]
    names={"main":"二号场全程停用","team":"青禾13—14点请假","active":"星桥13—14点请假","tied":"二号场末时段停用","impossible":"双场全程维修"}
    for first,second in zip(result["B"][::2],result["B"][1::2]):
        def pair(k): return " → ".join("—" if r[k] is None else str(r[k]) for r in [first,second])
        lines.append(f'|{names[first["case"]]}|{pair("moved")}|{pair("teams")}|{pair("soft")}|{pair("seconds")}|{pair("status")}|')
    lines+=["","罚值为偏离理想开球时间的累计小时，越低越好。无解时没有移动数。青禾案例的两次离线求解均通过校验，该次在线复核输出结构错误，未发布。星桥案例是检查不同缺席对象后追加的场景，用于展示机制，不能据此估计平均收益。"]
    return "\n".join(lines)+"\n"
if __name__=="__main__":
    results=measure()
    save("evidence/results.json",results)
    Path("experiments.md").write_text(tables(results),encoding="utf8")
