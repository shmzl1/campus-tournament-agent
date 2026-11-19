"""真实模型端到端验收。通过 HTTP 表单操作独立本机端口，保存真实运行。"""
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.error import HTTPError
from experiment_paths import RUNS
import re, json
from app import Handler, ROOT
from sample import NOTICE,CHANGES,MATCHES
from workflow import save
def run():
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    base="http://127.0.0.1:"+str(server.server_port)
    def submit(page,action,**extra):
        forms=re.findall(r'<form method="post">(.*?)</form>',page,re.S)
        for form in forms:
            fields=dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">',form))
            if fields["action"]==action: break
        else: raise ValueError("页面没有操作 "+action)
        with urlopen(base+"/",urlencode(dict(fields,**extra)).encode(),timeout=200) as response:
            return response.geturl(),response.read().decode()
    try:
        page=urlopen(base).read().decode()
        checks=[]
        for act,args in [("new",dict(notice=NOTICE,pairs="\n".join(" ".join(p) for p in MATCHES.values()))),("plan",{}),("publish",{}),("change",dict(notice=CHANGES["场地停用"])),("publish",{})]:
            previous=page
            url,page=submit(page,act,**args)
            checks.append(act)
            if act=="publish":
                try: submit(previous,act)
                except HTTPError as exc: assert exc.code==409
                else: raise AssertionError("重复提交未被拦截")
        rid=parse_qs(urlsplit(url).query)["run"][0]
        data=json.loads((ROOT/"local"/(rid+".json")).read_text("utf8"))
        assert len(data["versions"])==2 and "需要通知的队伍名单" in page
        data["http_checks"]=checks
        save(RUNS/("ui-"+rid+".json"),data)
        print(rid)
    finally: server.shutdown();server.server_close()
if __name__=="__main__": run()
