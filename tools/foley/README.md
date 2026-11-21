# 余烬回廊 · 近战采样来源

Kenney 的 [Impact Sounds](https://kenney.nl/assets/impact-sounds) 提供金属、木材及钝击声。artisticdude 的 [RPG Sound Pack](https://opengameart.org/content/rpg-sound-pack) 提供两段挥动声。两个原音包均为 CC0。游戏按动作单独剪辑、变速并混合采样。

本目录保存了 22,050 Hz、单声道、16 位 PCM 输入。运行项目的 `python tools/forge_audio.py` 可离线重建游戏内 WAV。Windows 包仅需混合后的成品。

本次取样使用[固定版本的镜像](https://github.com/Mcamento8/open-game-sfx-index/tree/34bbe8b525b5ceff3804915ea745532af11f6055/audio)。下表是转码前原文件的 Git blob，可用于核对来源。

| 原文件 | Git blob |
| --- | --- |
| impactMetal_light_002.ogg | c18f397662e730412a137a6759d53abcd9202e30 |
| impactMetal_light_003.ogg | 59b6c25ad862d74a46db05dcf65833ffed9759d7 |
| impactPunch_medium_000.ogg | d8e0b890ae019533ec190dd2d1decce249ea556e |
| impactPunch_heavy_001.ogg | 6655951d3bb43d8b06bd23b8ae60580fd7584406 |
| impactMetal_heavy_000.ogg | d4432f48b6ff5b4a501045ef0b8068963ef5530d |
| impactWood_heavy_001.ogg | 1ec513e8064c2f6148078daad7a7b4da65a49538 |
| swing.wav | 796b3e9ff97ff5464c0ff53307c2c8a4e94faa17 |
| swing2.wav | 6d9c38e781a2e687a1ff3040f1c1de4ac525bc36 |
