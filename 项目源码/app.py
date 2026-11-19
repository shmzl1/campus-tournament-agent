"""离线回放与本机组织者工作台。启动 python app.py。"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
from pathlib import Path
from threading import RLock
import json,re,html,secrets
from sample import NOTICE,BASE,CHANGES,VENUES,MATCHES,TEAMS
from workflow import Event
from engine import penalty

ROOT=Path(__file__).resolve().parent
REPLAY_DIR=ROOT.parent/"测试与实验"/"运行记录"
LOCK=RLock()
TOKEN=secrets.token_urlsafe(24)
STYLE="""*{box-sizing:border-box}body{margin:0;background:#f4f6f2;color:#18372d;font:16px/1.55 'Microsoft YaHei',sans-serif}header{background:#123f32;color:white;padding:18px max(5%,calc((100% - 1180px)/2));font-weight:700;white-space:nowrap}main{max-width:1220px;margin:auto;padding:24px}h1{font-size:32px;margin:4px 0}h2{font-size:21px;margin:8px 0 14px}p{margin:6px 0}section,article{background:white;border:1px solid #d3ded6;border-radius:12px;padding:17px 22px;margin:14px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair article{margin:0}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:6px 10px;border-bottom:1px solid #dfe7df}th{font-size:13px;color:#527063;background:#edf3ef}.move{background:#fff0c9}small{color:#5d7469}summary{cursor:pointer}button,a.btn{background:#14624c;color:white;border:0;padding:9px 15px;font:inherit;border-radius:7px;text-decoration:none;cursor:pointer;margin:5px 6px 0 0}a{color:#14624c}textarea{width:100%;min-height:70px;padding:9px;font:inherit;border:1px solid #a7bdb0;border-radius:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere}.tag{color:#805719;font-weight:bold}form{margin:10px 0}@media(max-width:780px){.pair{grid-template-columns:1fr}main{padding:12px}}"""
def esc(s): return html.escape(str(s),quote=True)
def parse_matches(raw):
    if not raw.strip(): return MATCHES.copy()
    pairs={}
    for line in raw.strip().splitlines():
        names=line.strip().split()
        if len(names)!=2 or names[0]==names[1] or not set(names)<=set(TEAMS):
            raise ValueError("每行输入两支不同的样例队名，用空格分隔")
        pairs[f"M{len(pairs)+1:02d}"]=names
    if len(pairs)>10: raise ValueError("单日最多录入10场")
    return pairs
def clock(t): return f"{t//60:02d}:{t%60:02d}"
def shell(body):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>榆园杯 · 赛程工作台</title><style>'+STYLE+'</style><header>榆园杯　/　校园赛事工作台</header><main>'+body+'</main></html>'
def grid(v,title,moved,attempt,matches):
    rows=""
    for t in range(780,1080,60):
        cells=""
        for venue in VENUES:
            m=next((m for m,p in v["plan"].items() if tuple(p)==(t,venue)),None)
            if not m: cells+="<td>—</td>"; continue
            quotes=[r["quote"] for r in v["rules"] if set(r["subjects"]) & {*matches[m],venue}]
            detail="；".join(list(BASE.values())+quotes)
            cells+=f'<td class="{("move" if m in moved else "")}"><details><summary>{m}　{esc(" · ".join(matches[m]))}</summary>{esc(detail)}<p>第{attempt.get("round","?")}轮复核问题 {len(attempt.get("review",[]))} 项</p></details></td>'
        rows+=f"<tr><th>{clock(t)}</th>{cells}</tr>"
    return f"<article><h2>{title}</h2><table><tr><th>开球</th><th>一号场地</th><th>二号场地</th></tr>{rows}</table></article>"
def form(action,d,extra,label):
    fields=dict(action=action,token=TOKEN,run=d.get("run_id",""),rev=d.get("rev",0))
    return '<form method="post">'+''.join(f'<input type="hidden" name="{k}" value="{esc(v)}">' for k,v in fields.items())+extra+f'<button>{label}</button></form>'
def review_history(d):
    rows=[]
    for a in d["attempts"]:
        problems=a.get("review")
        verdict="未取得复核结论" if problems is None else ("通过" if not problems else "退回修订")
        notes="；".join(i.get("quote","")+" "+i["reason"] for i in problems or [])
        rows.append(f'<tr><td>V{a["version"]} · 第{a["round"]}轮</td><td>{esc(a["result"]["status"])}</td><td>{verdict}</td><td>{esc(notes)}</td></tr>')
    return '<section><h2>逐轮复核</h2><table><tr><th>候选</th><th>求解状态</th><th>处置</th><th>原文与退回依据</th></tr>'+''.join(rows)+'</table></section>'
def render(d=None,replay=False):
    if not d:
        return shell('<h1>校园赛事赛程编排与临时改期助手</h1><p>榆园杯 · 虚构单日赛事　8 支队伍 / 2 块场地 / 5 场固定对阵</p><section><h2>赛事通知</h2><p>'+esc(" ".join(BASE.values()))+'</p>'+form("new",{},'<label>对阵清单（每行两队，用空格分隔）</label><textarea name="pairs">'+"\n".join(" ".join(pair) for pair in MATCHES.values())+'</textarea><label>赛事通知和队长反馈</label><textarea required name="notice">'+NOTICE+'</textarea>' ,"提取规则 · 真实模型")+'</section><section><h2>历史回放</h2>'+''.join(f'<a class="btn" href="/?replay={k}">{v}</a>' for k,v in [("main","场地停用"),("impossible","无可用空档"),("pair_fault","遗漏规则修订")])+'</section>')
    matches=d.get("matches",MATCHES)
    parts=[f'<small>{"历史回放" if replay else "真实运行"}　/　虚构赛事　·　{esc(d["run_id"])}</small><h1>{esc(d["status"])} · 榆园杯赛程</h1>']
    vs=d["versions"]+([d["candidate"]] if d.get("candidate") else [])
    if vs:
        latest=vs[-1]
        parts+=['<p>'+esc(latest["change"] or d["notice"])+'</p><div class="pair">']
        for v in vs[-2:]:
            a=next((a for a in reversed(d["attempts"]) if a["version"]==v["version"] and a["result"]["plan"]==v["plan"]),{})
            parts.append(grid(v,("已公布" if v in d["versions"] else "候选")+"版本 V"+str(v["version"]),latest["moved"],a,matches))
        parts.append("</div>")
        if latest["change"] and len(vs)>1:
            old=vs[-2]["plan"]
            rows=""
            for m in latest["moved"]:
                t,v=old[m]; u,w=latest["plan"][m]
                reason=latest["change"] if m in latest["direct"] else "为满足全局约束联动调整"
                rows+=f'<tr><td>{m}　{esc(" · ".join(matches[m]))}</td><td>{clock(t)} {esc(v)} → {clock(u)} {esc(w)}</td><td>{esc(reason)}</td></tr>'
            parts.append(f'<section><h2>变更清单　·　{len(latest["moved"])} 场</h2><table>{rows}</table><p>需要通知的队伍名单　<strong>{esc("、".join(latest["teams"]) or "无")}</strong></p><small>直接受影响　{esc("、".join(latest["direct"]) or "无")}　｜　{("已证明最少改动" if latest["solver"]=="OPTIMAL" else "找到可行方案")}</small></section>')
    if d.get("feedback"):
        parts.append("<section><h2>需要处理的反馈</h2>"+esc("；".join(x if isinstance(x,str) else x.get("reason","") for x in d["feedback"]))+"</section>")
    if d["status"] in ("已证明无解","超时未找到方案"):
        a=d["attempts"][-1]
        parts.append("<section><h2>"+esc(a["change"])+"</h2>无可选场地时段的场次："+esc("、".join(a["result"]["empty_domains"]) or "需联合检查各场次冲突"))
        if a.get("relaxation_trial"): parts.append("<p>试算撤回此次限制："+esc(a["relaxation_trial"]["result"]["status"])+"。请组织者协调资源，原版仍可查阅。</p>")
        parts.append("</section>")
    if vs:
        soft=[r for r in vs[-1]["rules"] if r["kind"] in ("early","late")]
        parts.append("<p>软偏好　"+esc("；".join(r["quote"]+"（距理想开球累计 "+str(penalty(vs[-1]["plan"],[r],matches))+" 小时）" for r in soft) or "无")+"</p>")
    parts.append('<section><h2>原文与规则</h2><p>'+esc(d["notice"])+'</p>'+''.join('<p>'+esc(r["id"]+" · "+r["quote"])+'</p>' for r in d["rules"])+''.join('<p class="tag">待确认　'+esc(p)+'</p>' for p in d["pending"])+'</section>')
    if not replay:
        if d["status"]=="待确认" and not d["pending"]: parts.append(form("plan",d,"","确认规则并编排"))
        if d["status"]=="可公布": parts.append(form("publish",d,"","公布此版本"))
        if d["versions"]: parts.append(form("change",d,'<textarea required name="notice">'+CHANGES["场地停用"]+'</textarea>',"提交临时通知并复核"))
        elif d["pending"] or d["status"] not in ("待确认","可公布"): parts.append(form("new",d,'<textarea required name="notice">'+esc(d["notice"])+'</textarea>',"澄清并新建运行"))
    if d["attempts"]: parts.append(review_history(d))
    parts.append('<section><details><summary>查看逐轮交接、工具结果和复核记录</summary><pre>'+esc(json.dumps(d,ensure_ascii=False,indent=2))+'</pre></details></section><a href="/">返回赛事选择</a>')
    return shell("".join(parts))
class Handler(BaseHTTPRequestHandler):
    def page(self,body,status=200):
        raw=body.encode()
        self.send_response(status); self.send_header("Content-Type","text/html;charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        q=parse_qs(urlsplit(self.path).query)
        path=None
        if "replay" in q and q["replay"][0] in ("main","injected","impossible","pair_fault"): path=REPLAY_DIR/(q["replay"][0]+".json")
        if "run" in q and re.fullmatch("[a-f0-9]{32}",q["run"][0]): path=ROOT/"local"/(q["run"][0]+".json")
        if path and not path.exists(): return self.page(shell("运行不存在"),404)
        self.page(render(json.loads(path.read_text("utf8")) if path else None,"replay" in q))
    def do_POST(self):
        length=int(self.headers.get("Content-Length",0))
        if length>32000: return self.page("通知太长",413)
        q={k:v[0] for k,v in parse_qs(self.rfile.read(length).decode()).items()}
        if q.get("token")!=TOKEN: return self.page("请刷新页面",403)
        with LOCK:
            try:
                if q["action"]=="new":
                    e=Event(q["notice"],matches=parse_matches(q.get("pairs",""))); e.path=ROOT/"local"/(e.d["run_id"]+".json"); e.extract()
                else:
                    if not re.fullmatch("[0-9a-f]{32}",q["run"]): raise ValueError("无效赛事")
                    path=ROOT/"local"/(q["run"]+".json")
                    e=Event("",path); e.d=json.loads(path.read_text("utf8"))
                    if int(q["rev"])!=e.d.get("rev",0): raise ValueError("页面已过期，请刷新后重试")
                    if q["action"]=="publish": e.publish()
                    elif q["action"]=="plan": e.candidate()
                    elif q["action"]=="change": e.candidate(q["notice"])
                    else: raise ValueError("未知操作")
            except RuntimeError:
                pass
            except (KeyError,ValueError,FileNotFoundError) as err: return self.page(shell(esc(err)),409)
            e.d["rev"]=e.d.get("rev",0)+1; e.persist()
            self.send_response(303); self.send_header("Location","/?run="+e.d["run_id"]); self.end_headers()
if __name__=="__main__":
    print("http://127.0.0.1:8765",flush=True)
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()
