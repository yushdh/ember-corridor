# 手工潮钟线 · 首玩时长复核

阶段 4 的 5–10 分钟目标仍待真人验证。当前保留的是一份已知路线的自动输入样本，便于检查采集方式。默认随机潮图、原来的五室与战斗数值沿用上版。

## 给第一次试玩的人

解压 `dist/first-play/EmberCorridor-Windows-x64.zip`，双击「首次试玩.cmd」，根据游戏内提示游玩即可。想休息时按 Esc，任何时候都可以关闭窗口。若愿意分享结果，在资源管理器地址栏输入 `%LOCALAPPDATA%\EmberCorridor-Playtests`，取本次目录里的 `session.json`，附上是否第一次玩及最困惑的一个地方。每次双击会新建目录；在同一次启动中按 R 会保留本次试玩所学操作及解锁。没有网络上传。

## 如何读记录

从标题页开始游戏时启动单调时钟，第一次胜利或正常关窗时截止。每次过门、开关装配或暂停、死亡、重开及结束都会原子写入记录。若进程被强制结束，已有的 `in_progress` 仅代表截至最后一次状态变化的部分记录。标题直接退出标作 `closed_before_start`。

- `wall_ms` 是首次获得控制到结束的实际毫秒数，含死亡重试。首胜结果为 `won`，中途退出为 `closed`。提前退出是有用的观察，不应当作首胜时长。
- `play_ms` 是游戏正常运行的时间，含原地观察。`forge_ms`、`pause_ms`、`retry_wait_ms` 分别记录装配、暂停、死亡后等待。四者相加等于 `wall_ms`。切到其他应用前没暂停的时间会计入游戏运行时间。
- `rooms` 按尝试次数、房间列出游玩和装配的合计时间，死亡前的房间也会保存。首次试玩入口默认将样本标为 `unclassified`，是否为真人首次体验需要试玩者确认。

## 本次实际运行

基线包已复开经典路线、练习和三敌交锋。源码实机在独立新档中用原生按键走同一套手工五室。第一局门廊死亡，第二局经过装配和暂停后鸣钟。首胜累计 **67.468 秒**，其中游戏运行 66.375 秒、装配 0.499 秒、暂停 0.547 秒、死亡后等待 0.047 秒。第一局门廊占 9.078 秒，获胜局的结算面板显示 0:57。[输入样本](automated-session.json) · [门廊](room-1.png) · [装配画面](choice.png) · [暂停](pause.png) · [胜利](victory.png)

在 Windows 11 上将最终 ZIP 解压到项目外，用 EXE 打开独立试玩两次。一次移动、暂停后关窗，另一次在标题页关窗，两份报告独立生成；两次之间已有正式存档文件逐字节一致。[发行包关窗与存档核对](installed/first-play.json)

另实际打开已解压的「首次试玩.cmd」，从标题页关窗，生成一份零次尝试的记录。普通游戏入口也已复测，发行包用种子 17 走完五室、暂停、胜利及死亡重开，另成功启动练习、三敌交锋和经典模式。[归档校验](installed/distribution.json) · [正式入口运行记录](installed/installed.json)

## 开发复验

```powershell
.\.venv\Scripts\python.exe -m game --first-play
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe tools/verify_first_play.py build/first-play-check
.\.venv\Scripts\python.exe tools/build_windows.py --output-dir dist/first-play
.\.venv\Scripts\python.exe tools/verify_windows.py dist/first-play/EmberCorridor-Windows-x64.zip build/first-play-windows-check
```
