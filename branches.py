"""以同一已公布 V1 派生独立的真实变更运行。"""
import json,sys,uuid
from pathlib import Path
from sample import CHANGES
from workflow import Event
if __name__=="__main__":
    name=sys.argv[1]
    notices={"team":CHANGES["球队请假"],"impossible":CHANGES["无可用空档"],"tied":"二号场地 17:00 至 18:00 停用。","active":"星桥队 13:00 至 14:00 无法参赛。"}
    text=notices[name]
    if name=="impossible": text="场馆负责人已确认今日维修：一号场地13:00至18:00停用。二号场地13:00至18:00停用。停用时段在原开放窗口内扣除。对阵、休息与比赛时长照旧。"
    d=json.loads(Path("evidence/main.json").read_text("utf8"))
    path=Path("evidence")/(name+".json")
    if path.exists(): raise FileExistsError(path)
    e=Event(d["notice"],path)
    v=d["versions"][0]
    e.d.update(parent=d["run_id"],versions=[v],rules=v["rules"],status="已公布")
    try:
        e.candidate(text)
        if e.d["status"]=="可公布": e.publish()
    finally: e.persist()
