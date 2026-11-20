# 盐炉渡口 · 视觉与打击感复验

[并排动作回放（无声）](comparison.gif) · [同机位静帧](comparison.png) · [完整交锋回放（无声）](live/combat.gif)

## 同场景截图

截图取自游戏窗口的 1280×720 帧缓冲。三段固定输入依次展示移动、弯刃连击、石台落锤。第三段把三名原有敌人放到同一平台，便于复现重锤命中和两种敌人预警重叠的情况。七对图片中角色位置、朝向、基础镜头、攻击步数、三敌状态与生命逐项相同。命中震动的方向和幅度参与最终画面。

| 时刻 | 修改前 | 修改后 |
| --- | --- | --- |
| 奔跑收腿 | [原图](before/run.png) | [原图](after/run.png) |
| 起跳屈膝 | [原图](before/jump.png) | [原图](after/jump.png) |
| 翻滚团身 | [原图](before/roll.png) | [原图](after/roll.png) |
| 横斩起手 | [原图](before/windup.png) | [原图](after/windup.png) |
| 横斩命中 | [原图](before/cut.png) | [原图](after/cut.png) |
| 突刺后摇 | [原图](before/recover.png) | [原图](after/recover.png) |
| 重锤命中、弩手与重卫预警 | [原图](before/heavy-warning.png) | [原图](after/heavy-warning.png) |

## 实机观察与改动

- 收腿时前后腿曾叠成同一块暗色。重绘近侧护胫、脚踝位置与远腿剪影，拉开收膝和伸展姿势。突出的面甲眉棱、向后的雾蓝披肩和向前的琥珀弯刃区分朝向。翻滚八帧使用不同的头、膝、腕和披肩位置，弯刃与持锤翻滚的可见高度均不超过 42 逻辑像素。
- 横斩先上举，落锤先后坐，打出时前膝承重。四招共用有效帧定义。测试在两个方向把敌人放到每张武器姿势的端点，核验有效帧伤害、单次去重、非有效帧无伤害，以及图集中挂点、武器尖端和刀光可见性。实际三连击仍把钩手生命依次打到 46、27、0。
- 旧重锤截图中火花盖住持锤手。现在接触闪点落在目标受击框表面，碎屑沿打击方向散出，受击亮帧保留面甲边线。弯刃留下暖弧或直刺，锤弧用冷青色。空挥、击中瞬态和金属余音分层合成，重击加强低频。Windows 音频播放器实际报告 11 种短音播放，扬声器听感未验证。
- 水轮与预警曾挤在同一区域。现已压低轮毂亮边，加入远处炉顶、中景烟汽和炉窗火舌、近岸水纹与岸灯光晕。满档时，预警用短钩、准星和双折线区分。第一版瞄准线压到持锤手，最终版将刻线放到主角之后，徽记留在最上层。敌人贴得很近时，后排身体仍会被遮住。

## 帧耗时

Windows 11 build 26300，RTX 5060 Laptop，OpenGL 4.6，Python 3.12.14，Arcade 3.3.3。窗口 1280×720，逻辑画布 640×360，整数最近邻 2 倍，开启垂直同步，窗口调度目标 60 Hz。震动、闪光、音量、粒子均为 3 档。每个绘制帧推进两步 120 Hz 游戏逻辑。采图和预热各 288 帧后，三段场景各重复三次，每版计时 864 帧，计时段关闭截图与回读。

| 实测 | 修改前 | 修改后 |
| --- | ---: | ---: |
| 平均帧率 | 59.61 FPS | 59.63 FPS |
| 平均呈现间隔 | 16.77 ms | 16.77 ms |
| P95 / P99 | 17.80 / 18.74 ms | 17.64 / 18.55 ms |
| 最长呈现间隔 | 21.36 ms | 19.26 ms |
| CPU 更新与绘制提交，平均 / P95 | 2.85 / 5.47 ms | 2.53 / 3.35 ms |
| 同屏粒子峰值 / 弩弹峰值 | 33 / 1 | 13 / 1 |

呈现间隔取连续两次窗口交换完成的墙钟差，含垂直同步与调度等待。CPU 列从推进输入计时至绘制提交结束。GPU 独立耗时、显示器扫描延迟、长时间运行和其他设备未验证。[修改前逐帧数据](before/report.json) · [修改后逐帧数据](after/report.json)

## 回归与复验

20 项单元测试通过。可见窗口以原生键盘消息完成清场、死亡、两次重开、暂停反馈调节，以及 1280×720、1366×768、1920×1080 三种尺寸的像素块检查。练习路线滚过低梁、抵达高台并返回；首次运行方向长按中断，修正验证脚本后通过。24 组独立移动播放检查记录了双武器双朝向六个动作的所有帧，固定交锋回放另记录了四招刀光及环境循环的实际使用帧。[交锋](live/combat.json) · [练习路线](practice/route.json) · [移动播放帧](cycles.json)

在项目根目录运行下列命令即可复验。新结果写入独立目录，便于保留本轮基线。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\visual_replay.py docs\verification\visual-rerun
.\.venv\Scripts\python.exe tools\verify_walk_cycles.py docs\verification\visual-rerun\cycles.json
.\.venv\Scripts\python.exe tools\verify_stage3.py --output docs\verification\visual-rerun\live
.\.venv\Scripts\python.exe tools\verify_stage2.py --output docs\verification\visual-rerun\practice
```
