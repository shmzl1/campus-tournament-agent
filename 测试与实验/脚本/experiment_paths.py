"""脚本既可由 unittest 发现，也可从任意工作目录直接执行。"""
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
SOURCE = SUITE.parent / "项目源码"
sys.path.insert(0, str(SOURCE))
RUNS = SUITE / "运行记录"
RESULTS = SUITE / "实验结果"
REFERENCE = SUITE / "参考答案" / "reference.json"
