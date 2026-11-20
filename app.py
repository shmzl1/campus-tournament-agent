from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from html import escape
from pathlib import Path
import base64,csv,json,re,secrets
from audit import ROOT,audit,save
from reporting import evidence_text,markdown

TOKEN=secrets.token_urlsafe(32)
EXAMPLES=ROOT/"examples"
LOCAL=ROOT/"local"
STYLE="""*{box-sizing:border-box}body{margin:0;background:#f5f4f0;color:#192e39;font:16px/1.65 'Microsoft YaHei',sans-serif}header{border-bottom:1px solid #cbd3d1;background:#173b42;color:white;padding:13px 6%;font-weight:bold}main{max-width:1080px;margin:auto;padding:25px}h1{margin:0;font-size:32px}h2{font-size:21px;margin:8px 0}h3{font-size:17px;margin:8px 0}section{background:white;border:1px solid #d3dbd9;border-radius:9px;padding:16px 21px;margin:12px 0}a{color:#17685b}textarea{width:100%;font:inherit;min-height:180px;padding:10px}button,.btn{display:inline-block;background:#176257;color:white;padding:8px 15px;border-radius:5px;border:0;text-decoration:none;font:inherit;margin:4px 8px 4px 0}button:disabled{opacity:.55}table{width:100%;border-collapse:collapse}td,th{padding:6px 8px;text-align:left;border-bottom:1px solid #dfe5e3}th{background:#eef3f1}small{color:#475d68}p{margin:5px 0}.bad{color:#8d4227}.good{color:#175f4a}.warn{color:#80601a}summary{cursor:pointer}.note{background:#f6f1e6;padding:7px 12px;border-left:3px solid #ad8334;margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}.links{display:flex;flex-wrap:wrap;gap:12px}"""
def h(v):return escape(str(v),quote=True)
def shell(body):return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>数据结论审查与复现</title><style>'+STYLE+'</style><header>数据结论审查与复现系统</header><main>'+body+'</main></html>'
def home():
    sample=(EXAMPLES/"claims.txt").read_text("utf8")
    return shell("""<h1>这句话有数据支持吗？</h1><p>上传 UTF-8 CSV，粘贴需要核查的结论。每行保留为一条原句。</p>
<section><form id="audit"><h2>数据与原句</h2><input type="file" accept=".csv,text/csv" id="csv"><p><small>留空使用虚构转化样例。上传上限 1 MB。模型接收字段、类别示例、原句及汇总结果。</small></p><label for="claims">分析结论</label><textarea id="claims" required>"""+h(sample)+"""</textarea><button>开始真实审查</button><span id="status" role="status"></span></form></section>
<section><h2>实验回放</h2><div class="links"><a href="/view?case=multi">自然运行 · 四角色</a><a href="/view?case=injected">人工注入 · 总体代替分组</a><a href="/view?case=single">单角色对照</a><a href="/sample.csv">下载样例 CSV</a></div></section>
<script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();const btn=e.target.querySelector('button'),status=document.querySelector('#status');btn.disabled=true;status.textContent='审查中，请等待计算与复核…';try{const file=document.querySelector('#csv').files[0];if(file&&file.size>1048576)throw Error('CSV 超过 1 MB');const bytes=file?new Uint8Array(await file.arrayBuffer()):null;let bin='';if(bytes)for(const x of bytes)bin+=String.fromCharCode(x);const rsp=await fetch('/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:'TOKEN_VALUE',csv:file?btoa(bin):null,claims:document.querySelector('#claims').value})});const out=await rsp.json();if(!rsp.ok)throw Error(out.error);location.href=out.url}catch(err){status.textContent=err.message;btn.disabled=false}};</script>""".replace("TOKEN_VALUE",TOKEN))
def render(d,query):
    archived=query.startswith("case=")
    parts=[f'<small>{"历史回放" if archived else "实际运行"}　/　{h(d["mode"])}　/　{h(d["run_id"])}</small><h1>逐句审查结果</h1><p>{h(d["status"])}　·　{d["row_count"]} 行 CSV　·　{len(d["events"])} 次模型请求</p>']
    if d.get("injection"):parts.append('<p class="note">'+h(d["injection"])+'。首轮展示的是实际执行的错误口径。</p>')
    if d.get("error"):parts.append('<p class="bad">'+h(d["error"])+'</p>')
    if d.get("unresolved"):parts.append('<p class="note">达到上限或异议重复，请人工核查。</p>')
    parts.append(f'<div><a class="btn" href="/export.md?{query}">下载审查报告</a><a class="btn" href="/export.json?{query}">下载复算记录</a></div>')
    final={i["source"]:i for i in d.get("items",[])}
    for sentence in d["sentences"]:
        n=sentence["source"];i=final.get(n)
        parts.append(f'<section><small>原句 {n}</small><h2>{h(sentence["text"])}</h2>')
        if i:
            cls={"数据支持":"good","与数据矛盾":"bad","证据不足":"warn"}[i["verdict"]]
            parts.append(f'<h3 class="{cls}">{h(i["verdict"])}</h3><p>{h(i["reason"])}</p><p>修订建议　{h(i["suggestion"])}</p>')
        for step in d["rounds"]:
            atoms={a["id"]:a for a in step["atoms"] if a["source"]==n}
            parts.append(f'<h3>第 {step["round"]} 轮计算　·　当轮判定：{h(step["locked"][n-1])}</h3><table><tr><th>待检验主张</th><th>实际计算依据</th></tr>')
            for q,r in zip(step["executed"],step["results"]):
                if q["id"] not in atoms:continue
                parts.append('<tr><td>'+h(atoms[q["id"]]["claim"])+'</td><td>'+'<br>'.join(h(x) for x in evidence_text(q,r))+'</td></tr>')
            parts.append('</table>')
            for issue in step.get("review",[]):
                if issue["id"] in atoms:parts.append('<p class="note">退回'+h(issue["target"])+'　'+h(issue["reason"])+'。'+h(issue["fix"])+'</p>')
            checks=[i for i in step.get('program_checks',[]) if i['id'] in atoms]
            if checks:parts.append('<small>范围校验：'+h('、'.join(i['id'] for i in checks))+' 的计算口径与主张不一致。</small>')
        parts.append('</section>')
    parts.append('<details><summary>查看角色输入输出、请求、用量和逐轮结果</summary><pre>'+h(json.dumps(d,ensure_ascii=False,indent=2))+'</pre></details><p><a href="/">返回上传页面</a></p>')
    return shell("".join(parts))
class Handler(BaseHTTPRequestHandler):
    def reply(self,data,typ,status=200,filename=None):
        if isinstance(data,str):data=data.encode()
        self.send_response(status);self.send_header("Content-Type",typ)
        if filename:self.send_header("Content-Disposition",'attachment; filename="'+filename+'"')
        self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        u=urlsplit(self.path);q=parse_qs(u.query)
        if u.path=="/":return self.reply(home(),"text/html;charset=utf-8")
        if u.path=="/sample.csv":return self.reply((EXAMPLES/"conversion.csv").read_bytes(),"text/csv;charset=utf-8",filename="conversion.csv")
        if u.path not in ("/view","/export.md","/export.json"):return self.reply("不存在","text/plain;charset=utf-8",404)
        if q.get("case",[""])[0] in ("single","multi","injected"):
            key=q["case"][0];path=ROOT/"evidence"/(key+".json");query="case="+key
        elif re.fullmatch("[a-f0-9]{32}",q.get("run",[""])[0]):
            key=q["run"][0];path=LOCAL/(key+".json");query="run="+key
        else:return self.reply("无效运行","text/plain;charset=utf-8",404)
        if not path.is_file():return self.reply("未找到记录","text/plain;charset=utf-8",404)
        d=json.loads(path.read_text("utf8"))
        if u.path=="/export.json":return self.reply(path.read_bytes(),"application/json",filename=key+".json")
        if u.path=="/export.md":return self.reply(markdown(d),"text/markdown;charset=utf-8",filename=key+".md")
        self.reply(render(d,query),"text/html;charset=utf-8")
    def do_POST(self):
        try:
            length=int(self.headers.get("Content-Length",0))
            if self.path!="/audit" or not 0<length<1550000:raise ValueError("请求路径或大小错误")
            q=json.loads(self.rfile.read(length))
            if q.get("token")!=TOKEN:raise ValueError("请重新打开首页")
            raw=(EXAMPLES/"conversion.csv").read_bytes() if q["csv"] is None else base64.b64decode(q["csv"],validate=True)
            lines=[s.strip() for s in q["claims"].splitlines() if s.strip()]
            d=audit(raw,lines);save(LOCAL/(d["run_id"]+".json"),d)
            self.reply(json.dumps({"url":"/view?run="+d["run_id"]}),"application/json")
        except (ValueError,KeyError,TypeError,UnicodeError,csv.Error) as err:self.reply(json.dumps({"error":str(err)},ensure_ascii=False),"application/json;charset=utf-8",400)
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--port",type=int,default=8766);args=p.parse_args()
    print(f"http://127.0.0.1:{args.port}/",flush=True)
    ThreadingHTTPServer(("127.0.0.1",args.port),Handler).serve_forever()
