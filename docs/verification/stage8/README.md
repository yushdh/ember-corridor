# Windows x64 发行候选验收 · 2026-11-21

本机交付文件位于项目根目录的 `dist/EmberCorridor-Windows-x64.zip`。ZIP 为 25,035,217 字节，解压后约 48.4 MiB。解压整包，双击 `EmberCorridor.exe` 即可开始；请保留相邻的 `_internal` 目录。[玩家说明](../../WINDOWS_RELEASE.md) · [归档 SHA-256 与启动记录](distribution.json)

## 发行包走查

在项目目录外新建带空格的中文临时目录，校验 ZIP 的 CRC 后解压。游戏工作目录为另一个空目录，子进程 PATH 只含 Windows 和 System32，移除了虚拟环境及 Python 路径，使用隔离的 LOCALAPPDATA。源码版与发行版共用游戏入口。中文从本机字体加载。游戏的 57 项清单资源均与源码逐字节相同，包内附来源清单和运行库许可说明。

- 普通 EXE 以种子 17 启动两次。通过 Win32 窗口消息开始、移动、暂停和调节音量。首次把音量 2 调为 3，退出后重新启动，再调一档得到 0。两次均保存移动教学记录，正常关闭返回 0。
- 同一解压包的自检入口使用正式窗口、正常速度和原生按键，从标题走过五室，验证绞盘、潮印、探潮叉手、守钟人、敲钟、死亡和两次重开。截图取自最终窗口缓冲。音频通过 XAudio2 播放，记录到音效实例的播放状态。扬声器外放听感未验证。[标题](start.png) · [双闸涵洞](room-4.png) · [暂停](pause.png) · [胜利](victory.png) · [死亡](death.png) · [包内记录](installed.json)
- 移动练习、三敌交锋和经典路线分别检查独立启动、输入记录和退出；经典路线同时核对手工五室顺序。[其他入口](modes.json)

## 性能条件

Windows 11 x64，GeForce RTX 5060 Laptop GPU，Python 3.12.14，Arcade 3.3.3。窗口 1280×720，世界 640×360，开启垂直同步。固定种子 17，门廊双敌近距离蓄焰斩，四项反馈全开，窗口内粒子峰值 10。九轮各 96 帧，第一轮预热并取四张像素指纹；其余轮次每轮前两帧排除，得到 752 个无截图读回计时帧。呈现间隔以相邻两次交换完成的时间计算；更新和绘制提交计时截止于交换前。

| 同一场景 | 平均 FPS | 呈现间隔 P95 / P99 | 更新及绘制提交 P95 |
| --- | ---: | ---: | ---: |
| [优化前源码](before.json) | 59.62 | 17.66 / 18.00 ms | 4.76 ms |
| [优化后源码](after.json) | 59.59 | 17.60 / 18.16 ms | 4.20 ms |
| [解压后的 EXE](packaged-timing.json) | 59.51 | 17.47 / 17.70 ms | 0.93 ms |

耐力槽原先每帧逐条绘制底槽、填充和刻度，现按 127 个可能的填充宽度缓存纹理，每帧一次绘制。景层位置只在镜头或震动位置变化时更新，环境动画仍按逻辑步推进。源码前后更新与绘制提交 P95 减少约 11.7%，呈现间隔 P99 增加约 0.15 ms；三次运行的四个关键帧哈希逐一相同。打包进程的提交耗时单独列出，计时不包含 GPU 完成等待。

## 反复死亡与过门

另外在源码窗口用隔离存档切换五个房间，经过实际伤害入口注入接触，运行受击和死亡时钟，然后按 R 重开，共 40 轮。80 个旧战斗场景和行者对象均可回收。各采样点均有 9 个窗口事件处理器，回到首室后活动音效、粒子和弩弹均为 0。第 5 至 40 次采样中工作集为 209.64–215.73 MiB；私有内存最高采样 787.50 MiB，第 40 次为 599.55 MiB。首次遍历五室时有明显内存增长，显存占用和数小时运行仍待实测。[Windows 进程内存记录](soak.json)

## 本轮发现

首包能通关，但 Arcade 在 EXE 中报出版本 0.0.0。检查归档发现上游打包钩子输出了 `arcade/VERSION/VERSION`，运行库读取的是 `arcade/VERSION` 文件。构建步骤校正该路径、逐字节检查版本文件，并附带 Arcade 发行元数据；自检同时核对两种读取结果。

本轮保留上轮已验收的设置、引导和独立耐力规则。自动路线用于复核操作、掉血、过门和重开。真人首玩通关时长、耐力的多局平衡、Windows 10、低配显卡以及无开发环境的干净机器尚未验证。

## 复验命令

在项目根目录运行以下 PowerShell 命令。构建依赖单列在 `requirements-build.txt` 中，玩家无需安装。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe tools/build_windows.py
.\.venv\Scripts\python.exe tools/verify_windows.py dist/EmberCorridor-Windows-x64.zip build/local-verification
.\.venv\Scripts\python.exe tools/profile_stage8.py build/source-timing.json
.\.venv\Scripts\python.exe tools/soak_stage8.py
```
