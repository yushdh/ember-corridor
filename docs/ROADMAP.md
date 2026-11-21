# 开发路线

每轮只推进一个可验收阶段。完整要求和操作约定保存在 [项目原始规范](PROJECT_BRIEF.md)。

| 阶段 | 内容 | 验收门槛 | 状态 |
| --- | --- | --- | --- |
| 1 | 工程与美术样板 | Windows 启动、左右移动、正常视距下辨认角色、整数缩放、真实截图 | 已验证 |
| 2 | 移动与碰撞 | 变高跳跃、落地、单向平台、按键缓冲、离地宽容、翻滚、镜头；墙角、头顶和高速碰撞通过实机检查 | 已验证，见[往返记录](verification/stage2/route.json) |
| 3 | 战斗核心 | 两种武器、三类敌人、攻击窗口、命中去重、中断与反馈同步 | 本机已验证。已完成视觉与打击感专项复验，见[同机位对照](verification/visual/RESULTS.md)与[交锋记录](verification/visual/live/combat.json) |
| 4 | 首个完整关卡 | 4–6 个手工房间、一个主动技能、Boss、完整动作和音效；从开始到胜利或死亡重开 | 本机已走通短刃跳过四匣、吊廊锁门折返、扳绞盘、鸣钟及胜负重开。已确认的真人首玩记录为 0 份，5–10 分钟体验目标待验收。[本轮实机](verification/stage4-detour/README.md) · [首玩记录口径](verification/stage4-first-play/README.md) |
| 5 | 装备、构筑与存档 | 局内选择与永久解锁形成循环，存档版本、备份与损坏处理可验证 | 本机通过。新增确认前的炉件收益与损失预览，复核四组实际战斗数值、新档首匣和取消操作。[炉件预览验收](verification/forge-preview/README.md) · [原有装配与重开记录](verification/stage5/route.json) |
| 6 | 模板随机关卡 | 记录种子，复现布局，按真实移动能力检查路径及必要目标，提供备用布局 | 已实走种子 17、6108 及故障注入后的备用路线。6108 留存两次穿闸、泵台及绞盘落脚、四次过门和鸣钟的记录，并补测四块侧台。4096 个生成样本覆盖 48 种布局。[6108 实机验收](verification/stage6/seed-6108/README.md) · [生成与回退](verification/stage6/README.md) |
| 7 | 内容扩展 | 每批引入有玩法差异的区域、武器或敌人，复核既有流程 | [探潮叉手](verification/stage7/README.md)与[回链绞工](verification/return-chain/README.md)已分别通过本机交锋。已复验[双敌交叉预警](verification/crossfire/README.md)，以及[蓄焰斩、命中火花、收招翻滚和反击](verification/flame-crossfire/README.md)。 |
| 8 | 优化与发行 | 依据性能数据调整体验，目标 Windows 发行包完成实测 | Windows 11 x64 本机通过。最终 ZIP 在项目外解压，普通启动、设置读回、五室、音频、胜负重开及 752 帧性能采样已验证。Windows 10、低配及真人首玩待复核。[发行验收](verification/stage8/README.md) |
