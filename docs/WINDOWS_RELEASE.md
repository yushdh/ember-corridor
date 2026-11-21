余烬回廊 · Windows x64 试玩版

第一次体验手工五室，可双击同目录的「首次试玩.cmd」。每次启动使用独立新档，直接按游戏内提示游玩即可。胜利或中途关闭窗口后，可在资源管理器输入 %LOCALAPPDATA%\EmberCorridor-Playtests，打开最近一次的目录查看 session.json。记录仅保存在本机；需要离席时请按 Esc 暂停。

将整个 ZIP 解压到一个可读目录，保留 EmberCorridor.exe 旁的 _internal 目录。双击 EmberCorridor.exe，在标题页按 Enter 开始。运行时可离线，无需单独安装 Python。需要支持 OpenGL 3.3 的显卡驱动和微软雅黑、等线或黑体中的一种系统字体。

A / D 移动，Space 跳跃，K 翻滚，J 近战，1 / 2 切武器，持短刃按住 L 后松开可施放蓄焰斩，Q 释放潮印，E 开匣、开门或扳动机关。
Esc 打开暂停菜单。操作说明页支持改键，设置页支持调节震动、闪光、音量和粒子密度。胜利或死亡后按 R 重新出发。关闭窗口退出。

默认开始一条随机五室路线。在解压目录的 PowerShell 中运行 .\EmberCorridor.exe --seed 17 可重走固定种子；--classic 进入经典路线，--practice 练习移动，--skirmish 进入三敌交锋。

永久炉谱、教学记录、绑定及反馈设置位于 %LOCALAPPDATA%\EmberCorridor。需要迁移时请关闭游戏并复制整个存档目录。局内进度在重开时重置。

在悬空栈板上，按住 S 再按空格或近乎同时按下两键即可下穿。守卫头顶短槽显示剩余生命，体型越大，槽越宽。

美术与音效的逐项来源见 _internal\assets\manifest.json。近战混音使用 Kenney 和 artisticdude 的 CC0 采样，出处见 licenses\武器拟音.txt。运行库许可也在 licenses 目录，中文字体使用本机安装版本。

安装自检（可选）：.\EmberCorridor.exe --verify-install .\验收结果
请指定尚不存在的输出目录。该模式使用临时存档，向游戏窗口发送按键并实走五室、胜负重开，完成后输出窗口截图与 installed.json；遇到游戏内检查错误会输出 error.txt。请保持窗口打开直至自动退出。

性能复验（可选）：.\EmberCorridor.exe --profile-render .\timing.json
该模式用临时存档运行固定的双敌蓄焰斩场景，结束后写入帧间隔和更新提交耗时。输出位置请选自己可写的目录。
