"""冻结 reference.json 后运行；模型仅接收 workflow 构造的可见输入。"""
import argparse, json
from experiment_paths import RUNS
from copy import deepcopy
from workflow import Event, save
from sample import CASES, CHANGES

def run(name,notice,inject=False):
    path=RUNS/(name+".json")
    if path.exists(): raise FileExistsError(path)
    e=Event(notice,path)
    try:
        e.extract()
        if inject:
            e.d["fault"]="人工注入故障测试：移除 shared 规则"
            e.d["rules"]=[r for r in e.d["rules"] if r["kind"]!="shared"]
        e.candidate()
        if e.d["status"]=="可公布": e.publish()
        if name=="main" and e.d["versions"]:
            e.candidate(CHANGES["场地停用"])
            if e.d["status"]=="可公布": e.publish()
    finally:
        e.persist()
        print(name,e.d["run_id"],e.d["status"],flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("case",choices=["main","supplement","normal","injected"])
    name=p.parse_args().case
    run(name,CASES[{"supplement":"补充通知","normal":"正常对照"}.get(name,"主赛事")],name=="injected")
