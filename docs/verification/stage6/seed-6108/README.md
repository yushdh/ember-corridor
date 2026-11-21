# 随机潮图 6108 · 踏台、扳绞盘与出口

这份种子在已有实机行程中没有记录。生成器第一次即得到有效布局。与种子 17 相比，双闸从第四室移到第二室，泵房改为东西两座泵台，西侧绞盘从第二室移到第四室。

## 连续战斗路线

Windows 11、RTX 5060 Laptop，1280×720 游戏窗口、640×360 逻辑画布。用独立存档从标题开始，以 Win32 键盘消息移动、跳跃、翻滚、战斗和交互。全程没有改血、传送或跳过守卫。下表高度为游戏世界内的逻辑像素，以人物脚底为准。

| 地点 | 在实际游戏窗口观察到的结果 |
| --- | --- |
| 退潮门廊 | 桥墩高度 139，落地后从东门进入双闸涵洞。[桥墩](gate-landing-2.png) |
| 双闸涵洞 | 西闸、东闸下均记录到翻滚姿态。角色头顶高 136，两闸底面分别高 140 和 141，过第二闸后可以继续前进。[西闸](sluice-twins-under-1.png) · [东闸](sluice-twins-under-3.png) |
| 东西泵台 | 先落在西泵台 147，再落在东泵台 154，随后从东门进入吊廊。[西泵台](pump-landing-1.png) · [东泵台](pump-landing-3.png) |
| 西侧绞盘 | 从高 143 的西阶座登上高 197 的绞盘吊台。角色在吊台上按 E，窗口出现“绞盘已开启”，清场后能从东门进入熔庭。[西阶座](gallery-west-landing-1.png) · [登台](gallery-west-landing-2.png) · [绞盘已开](winch-open.png) |
| 潮钟熔庭 | 击败守钟人后在东端鸣钟。结算显示种子 6108、击破 10、行程 0:59。游戏内原始计时为 59.375 秒。[结算](victory.png) |

前四次过门后脚底坐标均为下一室入口 (75, 94)，第五次交互进入胜利结算。随后按 R 重开，在门廊死亡，再按 R；两次均读回同一模板序列。[逐门坐标、承重面和运行记录](run.json)

## 侧台补测

连续战斗路线没有记录到下面四块板的落点。补测时载入同一种子的对应房间，把守卫设为清场状态，从各自的正常入口开始，以键盘回调和 120 Hz 正式物理步行、起跳，一直到角色脚底落在指定承重面。

| 落点 | 起跳 → 着地高度 | 截图 |
| --- | --- | --- |
| 门廊盐栈 | 地面 94 → 151 | [盐栈](gate-side.png) |
| 双闸中继栈 | 地面 94 → 147 | [中继栈](sluice-twins-side.png) |
| 泵房索桥 | 西泵台 147 → 188 | [索桥](pump-side.png) |
| 吊廊横渡板 | 地面 94 → 162 | [横渡板](gallery-west-side.png) |

本轮 53 项测试通过。重新生成种子 0–4095，每个种子分别生成两次，结果一致，覆盖 48 种排列，回退次数为 0。其他种子的逐局实战、侧台在敌人干扰下的成功率以及真人首玩时长仍未验证。[四次起跳与落点](side-platforms.json)

## 重走这张潮图

在已解压的 Windows 包目录运行 `.\EmberCorridor.exe --seed 6108`。本机从公开的炉件预览版 ZIP 启动了这个普通入口，进入门廊后核对了写盘的种子和五个模板；上面的全程验收在源码游戏窗口执行。[Windows 试玩包](https://github.com/yushdh/ember-corridor/raw/refs/tags/playtest-forge-preview/EmberCorridor-Windows-x64.zip) · [EXE 启动核对](windows-launch.json)

源码与开发复验可在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m game --seed 6108
.\.venv\Scripts\python.exe tools/verify_stage6.py --seed 6108 --output build/seed-6108
.\.venv\Scripts\python.exe tools/verify_side_platforms.py --seed 6108 --output build/seed-6108
```
