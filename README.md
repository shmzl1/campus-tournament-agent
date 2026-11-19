# 校园赛事赛程编排与临时改期助手

组织者在浏览器输入对阵和自然语言通知，确认规则后公布赛程。公布后，系统识别受临时变更影响的比赛，比较新旧版本并生成需要通知的队伍名单。榆园杯、参赛队和通知均为虚构样例。

![二号场停用后的比赛差异](报告附件/图片/改期对照.png)

## 启动与测试

从仓库根目录或完整解压目录执行。Python 3.13 已验证，无第三方运行依赖。

```powershell
python ".\项目源码\app.py"
```

打开 http://127.0.0.1:8765/ 或直接进入 http://127.0.0.1:8765/?replay=main 。在另一窗口运行 26 项离线测试：

```powershell
python -m unittest discover -s ".\测试与实验\脚本" -p "tests.py" -v
```

## 项目内容

- [公开结课报告](report.md)与[Windows 启动说明](项目源码/Windows启动说明.md)
- [实验对照表](测试与实验/实验结果/experiments.md)、[正式运行记录](测试与实验/运行记录)、[开发期记录](测试与实验/开发记录)
- [演示脚本](报告附件/演示脚本.md)、[课件要求对照](报告附件/课件要求对照.md)、[可编辑 SVG 图源](报告附件/图源)

离线复算用 `python ".\测试与实验\脚本\experiments.py"`，结果写入“测试与实验/实验结果/复算”，耗时随机器变化。真实模型验证脚本 verify_ui.py、formal.py、branches.py 和 fault_pair.py 位于同一脚本目录，调用会产生 API 费用。formal.py 与 branches.py 拒绝覆盖同名运行。可在单独副本内备份运行记录目录，然后重跑 main、supplement、normal、injected 首版，接着运行 fault_pair.py 和 branches.py 的各变更案例。模型重复采样可能返回不同意见。

本项目使用 Codex 辅助开发。接口与运行依赖参考 [DeepSeek 官方文档](https://api-docs.deepseek.com/) 与 [Python 标准库](https://docs.python.org/3/library/)。
