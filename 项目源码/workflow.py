import json, os, uuid
from copy import deepcopy
from pathlib import Path
import agents
from sample import BASE, MATCHES, TEAMS, VENUES
from engine import solve, issues, diff, penalty

def save(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
    os.replace(tmp,path)

class Event:
    def __init__(self,notice,path=None,matches=None):
        self.path=path
        self.d=dict(matches=matches if matches is not None else MATCHES,run_id=uuid.uuid4().hex,notice=notice,events=[],attempts=[],versions=[],status="新赛事",rules=[],pending=[],feedback=[])
    def persist(self):
        if self.path: save(self.path,self.d)
    def ask(self,role,n,**extra):
        data=dict(notice=self.d["notice"],base=BASE,teams=TEAMS,venues=VENUES,matches=self.d.get("matches",MATCHES),**extra)
        try:
            try: return agents.call(role,deepcopy(data),self.d["events"],n)
            except RuntimeError:
                last=self.d["events"][-1] if self.d["events"] else {}
                if last.get("status")!="failed" or last.get("error") not in ("KeyError","ValueError","JSONDecodeError","TypeError"): raise
                data["format_feedback"]={"previous":last.get("visible"),"message":"上次结构校验失败。按系统提示严格返回全部字段，复核工具调用必须有 tool=validate 与 issues；盲读清单必须有 rules 与 pending。"}
                return agents.call(role,deepcopy(data),self.d["events"],n)
        except RuntimeError:
            self.d["status"]="调用失败"
            raise
        finally: self.persist()
    def extract(self,feedback=None,n=1):
        out=self.ask("rules",n,feedback=feedback or [],previous=self.d["rules"])
        self.d.update(rules=out["rules"],pending=out["pending"],status="待确认")
        self.persist()
    def candidate(self,change="",max_rounds=None):
        if max_rounds is None: max_rounds=int(os.getenv("TOURNAMENT_MAX_ROUNDS","3"))
        if not 1<=max_rounds<=10: raise ValueError("轮数须在1至10之间")
        d=self.d
        matches=d.get("matches",MATCHES)
        old=d["versions"][-1]["plan"] if d["versions"] else None
        if bool(old)!=bool(change): raise ValueError("请选择与当前版本一致的操作")
        if d["pending"]: raise ValueError("请澄清待确认事项后重新提取")
        if not change and d["status"]!="待确认": raise ValueError("候选已生成或须重新提取")
        d.update(candidate=None,feedback=[],status="复核中")
        previous=None
        seen=set()
        for n in range(1,max_rounds+1):
            rules=deepcopy(d["rules"])
            args=dict(rules=rules,feedback=d["feedback"],previous=previous)
            if change:
                out=self.ask("change",n,change=change,published=old,prior_notices=[v["change"] for v in d["versions"] if v["change"]],**args)
                if out["pending"]:
                    d.update(status="变更待澄清",feedback=out["pending"])
                    trial_rules=rules+out["rules"]
                    d["attempts"].append(dict(round=n,version=len(d["versions"])+1,change=change,rules=trial_rules,tool="待确认通知条件试算",result=solve(trial_rules,old,matches=matches)))
                    break
                if len(d["versions"])>1:
                    for r in out["rules"]: r["id"]=f'V{len(d["versions"])+1}-'+r["id"]
                rules+=out["rules"]
            else: self.ask("schedule",n,**args)
            reconsider={}
            if previous:
                for item in d["feedback"]:
                    if item.get("target") in ("schedule","change"):
                        for m in item.get("matches",[]):
                            if m in matches: reconsider[m]=previous["result"]["plan"][m]
            result=solve(rules,old,matches=matches,reconsider=reconsider)
            attempt=dict(round=n,version=len(d["versions"])+1,change=change,rules=rules,tool="reschedule" if change else "solve",result=result)
            d["attempts"].append(attempt)
            plan=result["plan"]
            if plan is None:
                d.update(status="已证明无解" if result["status"]=="INFEASIBLE" else "超时未找到方案")
                if change and result["status"]=="INFEASIBLE":
                    trial=solve(d["rules"],old,matches=matches)
                    attempt["relaxation_trial"]=dict(option="请组织者考虑撤回本次新增限制或另行协调场地",result=trial)
                break
            validation=issues(plan,rules,matches=matches)
            direct=sorted({m for i in issues(old,out["rules"],matches=matches) for m in i["matches"]}) if change else []
            inventory=self.ask("review",n,mode="blind_inventory",change="",instruction="只根据原始赛事通知独立重建规则表。输出 JSON {rules,pending}。")
            review=self.ask("review",n,change=change,prior_notices=[v["change"] for v in d["versions"] if v["change"]],rules=rules,candidate=plan,published=old,validation=validation,previous_feedback=d["feedback"],independent_inventory=inventory)
            problems=review["issues"][:]
            def key(r): return (r["kind"],tuple(sorted(r["subjects"])),r["start"],r["end"])
            observed={key(r) for r in rules}
            for r in inventory["rules"]:
                if key(r) not in observed:
                    problems.append(dict(target="rules",rule=r["id"],quote=r["quote"],matches=[m for m,teams in matches.items() if set(teams)&set(r["subjects"])],reason="独立原文清单中的规则未进入排程"))
            for item in inventory["pending"]:
                problems.append(dict(target="rules",rule="待确认",reason=item))
            if change and set(out["direct"])!=set(direct):
                problems.append(dict(target="change",reason="直接受影响场次与程序核对不符",expected=direct))
            problems+= [dict(target="change" if change else "schedule",**i) for i in validation]
            attempt.update(validation=validation,review=problems,direct=direct)
            if not problems:
                d["feedback"]=[]
                moved,teams=diff(old,plan,matches) if change else ([],[])
                d.update(status="可公布",candidate=dict(version=len(d["versions"])+1,plan=plan,rules=rules,change=change,direct=direct,moved=moved,teams=teams,soft_penalty=penalty(plan,rules,matches),solver=result["status"]))
                break
            d["feedback"]=problems
            signature=json.dumps([rules,plan,[(p["target"],p.get("rule"),p.get("matches")) for p in problems]],sort_keys=True)
            if signature in seen: d["status"]="无进展，待组织者处理"; break
            seen.add(signature)
            previous=deepcopy(attempt)
            if any(i["target"]=="rules" for i in problems):
                before=d["rules"]
                self.extract(problems,n+1)
                if d["pending"] or d["rules"]!=before and change:
                    if change:
                        attempt["proposed_rules"]=d["rules"]
                        attempt["clarifications"]=d["pending"]
                        d["rules"]=before
                        d["feedback"]=problems+d["pending"]
                        d["pending"]=[]
                    d["status"]="规则已修订，待确认"; break
            d["status"]="达到轮数上限，待组织者处理"
        self.persist()
    def publish(self):
        d=self.d
        if d["status"]!="可公布" or not d.get("candidate"): raise ValueError("仅可公布已复核的新版本")
        v=deepcopy(d["candidate"])
        d["versions"].append(v)
        d.update(status="已公布",candidate=None,rules=v["rules"])
        self.persist()
