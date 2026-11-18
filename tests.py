import json, unittest
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
from engine import solve,issues,diff,penalty,clash
from workflow import Event
from agents import validate_output
from app import render
from sample import MATCHES,VENUES
def read(name):
    return json.loads((Path(__file__).parent/"evidence"/(name+".json")).read_text("utf8"))
class TournamentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main=read("main"); cls.v1,cls.v2=cls.main["versions"]
    def test_first(self):
        self.assertFalse(issues(self.v1["plan"],self.v1["rules"]))
    def test_all_roles(self):
        self.assertEqual({e["role"] for e in self.main["events"]},{"rules","schedule","review","change"})
    def test_boundary(self):
        self.assertFalse(clash(780,840)); self.assertTrue(clash(780,839))
        self.assertFalse(clash(780,900,60)); self.assertTrue(clash(780,899,60))
    def test_closed_and_team(self):
        p={"M03":(900,VENUES[0])}
        self.assertTrue(issues(p,self.v1["rules"],False)); p["M03"]=(960,VENUES[0])
        self.assertFalse(issues(p,self.v1["rules"],False))
    def test_overlap(self):
        self.assertTrue(issues({"M01":(780,VENUES[0]),"M02":(780,VENUES[0])},[],False))
    def test_shared(self):
        self.assertTrue(issues({"M03":(960,VENUES[0]),"M04":(960,VENUES[1])},self.v1["rules"],False))
    def test_duration_window(self):
        self.assertTrue(issues({"M01":(1080,VENUES[0])},[],False))
    def test_soft_conflict(self):
        r=self.v1["rules"]+[dict(id="X",kind="blocked",subjects=["白鹭"],start=1020,end=1080,quote="白鹭末场缺席")]
        sol=solve(r); self.assertEqual(sol["status"],"OPTIMAL"); self.assertGreater(penalty(sol["plan"],r),0)
    def test_unknown(self): self.assertEqual(solve([],budget=0)["status"],"UNKNOWN")
    def test_impossible(self):
        a=read("impossible")["attempts"][-1]
        self.assertEqual(a["result"]["status"],"INFEASIBLE"); self.assertEqual(set(a["result"]["empty_domains"]),set(MATCHES))
        self.assertIn(a["relaxation_trial"]["result"]["status"],("OPTIMAL","FEASIBLE"))
    def test_preserved(self): self.assertEqual(read("impossible")["versions"],[self.v1])
    def test_change(self):
        self.assertFalse(issues(self.v2["plan"],self.v2["rules"]))
        self.assertEqual(diff(self.v1["plan"],self.v2["plan"]),(["M04"],["石榴","飞萤"]))
    def test_no_deletion(self):
        with self.assertRaises(ValueError): diff(self.v1["plan"],{})
        self.assertTrue(issues({},[]))
    def test_duplicate_publish(self):
        e=Event(""); e.d=deepcopy(self.main)
        with self.assertRaises(ValueError): e.publish()
        self.assertEqual(len(e.d["versions"]),2)
    def test_injected(self):
        d=read("pair_fault"); a,b=d["attempts"][:2]
        self.assertTrue(any(i["target"]=="rules" and "守门员" in i.get("quote","") for i in a["review"]))
        self.assertNotEqual(a["result"]["plan"]["M04"],b["result"]["plan"]["M04"])
    def test_format_failure(self):
        with self.assertRaises((ValueError,KeyError)): validate_output("rules",{"rules":[]},{"notice":"x"})
    def test_transport_failure(self):
        e=Event("虚构")
        with patch("agents.urlopen",side_effect=OSError),patch.dict("os.environ",DEEPSEEK_API_KEY="offline-test"):
            with self.assertRaises(RuntimeError): e.extract()
        self.assertEqual(e.d["status"],"调用失败");self.assertEqual(e.d["events"][0]["status"],"failed")
    def test_failure_never_publishes(self):
        e=Event("");e.d=deepcopy(self.main)
        with patch("agents.call",side_effect=RuntimeError):
            with self.assertRaises(RuntimeError): e.candidate("维修")
        self.assertEqual(e.d["versions"],self.main["versions"])
    def test_replay(self):
        page=render(self.main,True)
        for s in ["历史回放","已公布版本 V1","已公布版本 V2","14:00","石榴","需要通知的队伍名单"]: self.assertIn(s,page)
    def test_pending(self):
        e=Event("互相矛盾的要求");e.d["pending"]=["请确定可用时段"]
        with self.assertRaises(ValueError): e.candidate()
    def test_custom_fixture(self):
        from app import parse_matches
        pairs=parse_matches("白鹭 云杉\n云杉 石榴")
        result=solve([],matches=pairs)
        self.assertEqual(set(result["plan"]),{"M01","M02"})
        self.assertFalse(issues(result["plan"],[],matches=pairs))
        self.assertGreaterEqual(abs(result["plan"]["M01"][0]-result["plan"]["M02"][0]),120)
    def test_conflicting_notice(self):
        d=read("conflict");self.assertTrue(d["pending"]); self.assertFalse(d["versions"])
        self.assertIn("13",str(d["pending"]));self.assertIn("16",str(d["pending"]))
    def test_one_move_lower_bound(self):
        # 独立手工下界：旧表使用了停用场地；只改一场即可达到下界。
        count=sum(v=="二号场地" for _,v in self.v1["plan"].values())
        self.assertEqual(count,1)
        self.assertEqual(sum(self.v1["plan"][m]!=p for m,p in self.v2["plan"].items()),count)
        self.assertFalse(issues(self.v2["plan"],self.v2["rules"]))
    def test_revise_specific_match(self):
        matches={"M01":["青禾","白鹭"]}
        first=solve([],matches=matches)
        revised=solve([],matches=matches,reconsider=first["plan"])
        self.assertNotEqual(first["plan"]["M01"],revised["plan"]["M01"])
        self.assertEqual(first["score"],revised["score"][:4])
    def test_no_progress(self):
        e=Event("示例"); e.d["status"]="待确认"
        def fixed(role,n,**kw):
            if kw.get("mode"): return {"rules":[],"pending":[]}
            return {"issues":[dict(target="schedule",rule="B1",matches=["M01"],reason="重复分歧",quote="示例")]} if role=="review" else {}
        with patch.object(e,"ask",side_effect=fixed): e.candidate(max_rounds=3)
        self.assertIn("无进展",e.d["status"])
        self.assertEqual(e.d["attempts"][0]["result"]["plan"],e.d["attempts"][-1]["result"]["plan"])
        self.assertNotEqual(e.d["status"],"可公布")
    def test_one_round_limit(self):
        e=Event("示例");e.d["status"]="待确认"
        def unresolved(role,n,**kw):
            if kw.get("mode"): return {"rules":[],"pending":[]}
            return {"issues":[dict(target="schedule",reason="需要核对")]} if role=="review" else {}
        with patch.object(e,"ask",side_effect=unresolved): e.candidate(max_rounds=1)
        self.assertIn("上限",e.d["status"])
if __name__=="__main__": unittest.main(verbosity=2)
