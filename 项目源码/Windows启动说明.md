# Windows 启动与验收

在解压后含有署名报告的目录打开 PowerShell。Python 3.13 已验证，应用和离线测试只用标准库。

```powershell
python ".\项目源码\app.py"
```

在浏览器打开 http://127.0.0.1:8765/ 。点击“场地停用”，或直接打开 http://127.0.0.1:8765/?replay=main ，即可离线查看两版赛程和通知名单。回放读取同级“测试与实验/运行记录”，请整体解压三个目录。按 Ctrl+C 停止服务。

在另一个 PowerShell 从同一根目录运行：

```powershell
python -m unittest discover -s ".\测试与实验\脚本" -p "tests.py" -v
```

正常结果为 26 项且全部通过。赛事输入和模型参数见本目录的 sample.py 与 .env.example。真实请求读取进程环境变量 DEEPSEEK_API_KEY；模型默认 deepseek-flash，可用 DEEPSEEK_MODEL 指定，TOURNAMENT_MAX_ROUNDS 默认 3。交互式运行保存到项目源码/local。配置表里的变量名可作参考，程序不自动读取 .env 文件。

从根目录重新打包时，用署名报告和输出 ZIP 路径作为两个参数：

```powershell
$report = Get-ChildItem -File '*_系统设计.md' | Select-Object -First 1
python ".\测试与实验\脚本\package_submission.py" $report.FullName ([IO.Path]::ChangeExtension($report.FullName, '.zip'))
```
