"""从已归档的项目文件构建提交包。可在 checkout 或完整解压副本中执行。"""
import argparse
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 仅纳入课程交付物。新建的交互运行、浏览器缓存和真实凭据不在清单中。
FILES = {
    "项目源码": ".env.example agents.py app.py engine.py workflow.py sample.py requirements.txt Windows启动说明.md",
    "测试与实验/脚本": "tests.py experiments.py formal.py branches.py fault_pair.py verify_ui.py experiment_paths.py package_submission.py",
    "测试与实验/参考答案": "reference.json",
    "测试与实验/实验结果": "results.json tests.json experiments.md",
    "测试与实验/开发记录/pilot": "main.json normal.json supplement.json injected.json",
    "测试与实验/开发记录/prototype": "main.json normal.json supplement.json injected.json impossible.json ui-format-error.json",
    "测试与实验/运行记录": "main.json active.json conflict.json impossible.json injected.json normal.json pair_fault.json supplement.json team.json tied.json ui-59504551fc1f41df93a3846f426dae80.json",
    "报告附件": "演示脚本.md 课件要求对照.md",
    "报告附件/图片": "系统架构.png 协作过程.png 改期对照.png 双场停用.png",
    "报告附件/图源": "系统架构.svg 协作过程.svg",
}

def build(report, output):
    if report.parent != ROOT or not report.name.endswith("_系统设计.md"):
        raise ValueError("请选择项目顶层的正式署名报告")
    if output.suffix.lower() != ".zip":
        raise ValueError("输出应为 ZIP 文件")
    files = [report] + [ROOT / group / name for group, names in FILES.items() for name in names.split()]
    if not all(path.is_file() for path in files):
        raise FileNotFoundError([str(path) for path in files if not path.is_file()])
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as tmp:
        staging = Path(tmp.name)
    try:
        with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(staging) as archive:
            if archive.testzip() is not None:
                raise ValueError("提交包校验失败")
        staging.replace(output)
    finally:
        staging.unlink(missing_ok=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.report.resolve(), args.output.resolve())
