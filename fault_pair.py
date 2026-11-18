"""独立机制试验。预设的人工答案是 shared(海棠,石榴)，不传入模型。"""
from formal import run
if __name__=="__main__":
    run("pair_fault","海棠队和石榴队共用守门员，禁止同时比赛。",True)
