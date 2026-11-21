# 手工五室 · 初始短刃与吊廊折返

**待真人验收**　截至 2026-11-21，有 0 份经玩家确认的首次体验记录。5–10 分钟的体验目标、玩家在东门能否自行找到绞盘仍待观察。下列窗口回放和计时的来源均为自动输入。

## 实际走法

从独立新档的标题页按 Enter，保持初始短刃，配合潮印清场。走过前四室所有炉料匣，装配时间为零。第四室先清掉三名守卫，走到东门按 E，确认门仍锁着。在暂停页重读目标后，向西登上压舱座，从台座跳上吊台扳绞盘，再回东门进入第五室。末室躲过守钟人的低扫和喷潮，经过半血变相，击破后在东端鸣钟。随后从胜利页重开，在第一室死亡，再从死亡页重开。

| 现场 | 游戏窗口画面 |
| --- | --- |
| 第四室东门，修改前后 | [原来的门边提示](locked-door-before.png) · [新增折返方向与台座](installed/locked-door.png) |
| 暂停、找台座与扳绞盘 | [暂停目标](installed/locked-objective.png) · [站上西侧台座](installed/west-step.png) · [绞盘已开](installed/valve-open.png) |
| 五室首尾与两次重开 | [胜利截图](installed/victory.png) · [次局死亡](installed/death.png) · [全程抽帧回放，无声、加速](installed/route.gif) |

发行包在独立中文目录解压，启动时 PATH 中没有 Python。真实窗口为 1280×720，逻辑画布为 640×360。按键通过 Windows 消息送入游戏，人物位置、血量、装配和机关状态均由游戏更新。验收程序记录到被拒绝的交互、之后的台座落脚和开闸事件，并检查五个房间的顺序、首胜、暂停计时和重开。[逐事件记录](installed/run.json) · [首胜及各室用时](installed/first-victory.json) · [发行包运行与声音](installed/installed.json) · [文件大小与 SHA-256](installed/distribution.json)

## 试玩与复验

最终 EXE 首次从获得控制到鸣钟共 70.047 秒，含暂停 0.297 秒，结算显示五室贯通、击破 10、行程 1:09。首次胜利记录到鸣钟为止，随后两次重开见运行报告。52 项单元测试通过。另在 RTX 5060 Laptop 上采集双敌场景 752 帧，平均 59.56 FPS，呈现间隔 P95 为 17.43 ms。[帧耗时原始数据](installed/packaged-timing.json) · [其他入口检查](installed/modes.json) · [试玩档隔离记录](installed/first-play.json)

第一次玩可下载并完整解压 Windows ZIP，双击「首次试玩.cmd」。可随时退出或按 Esc 暂停。若愿意反馈，取本次启动在 `%LOCALAPPDATA%\EmberCorridor-Playtests` 中生成的 `session.json`，附上是否首次游玩及最困惑的一处。记录保存在本机。[Windows 试玩包](https://github.com/yushdh/ember-corridor/raw/refs/tags/playtest-stage4-detour/EmberCorridor-Windows-x64.zip)

开发者可在项目根目录复验。输出目录请使用单独的测试目录。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe tools/verify_stage4.py --blade-detour --output build/classic-blade
.\.venv\Scripts\python.exe tools/build_windows.py --output-dir dist/stage4-detour
.\.venv\Scripts\python.exe tools/verify_windows.py dist/stage4-detour/EmberCorridor-Windows-x64.zip build/classic-installed --blade-detour
```
