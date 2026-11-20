"""Pause-page input, binding display and the unobtrusive lower tutorial strip."""
from functools import lru_cache

import arcade

from .guidance import ACTIONS, DEFAULT_KEYS, KEY_NAMES, LESSONS, key_label
from .ui import panel, blit, label, FOAM, PALE, GOLD

K = arcade.key
PHYSICAL = {getattr(K, name): name for name in KEY_NAMES}


class Controls:
    def __init__(self, store):
        self.store = store
        self.page = "pause"
        self.focus = 0
        self.parent_focus = 0
        self.selected = 0
        self.listening = False
        self.message = ""
        self.configure(store.data.bindings)

    def configure(self, names):
        self.names = tuple(names)
        self.labels = {action: key_label(name) for (action, _, _), name in zip(ACTIONS, names)}
        self.mapping = {
            getattr(K, name): getattr(K, default) for name, default in zip(names, DEFAULT_KEYS)
        }

    def gameplay_key(self, physical):
        # An unbound old default must stop acting after a remap.
        return self.mapping.get(physical, None if physical in PHYSICAL else physical)

    def help_key(self, key):
        if self.listening:
            if key == K.ESCAPE:
                self.listening = False
            elif key not in PHYSICAL:
                self.message = "请选择字母、数字、方向键或空格"
            elif PHYSICAL[key] in self.names and self.names[self.selected] != PHYSICAL[key]:
                self.message = "这个键已用于其他动作"
            else:
                names = list(self.names)
                names[self.selected] = PHYSICAL[key]
                self.configure(names)
                self.store.update(bindings=names)
                self.listening = False
                self.message = ""
            return True
        self.message = ""
        if key in (K.ESCAPE, K.F5):
            return False
        if key in (K.UP, K.DOWN):
            self.selected = (self.selected + (1 if key == K.DOWN else -1)) % len(ACTIONS)
        elif key in (K.ENTER, K.RETURN):
            self.listening = True
        return True

    def open_menu(self, page):
        self.page = page
        self.focus = 0
        self.listening = False
        self.message = ""

    def menu_items(self, root, battle):
        if root == "title":
            return (("start", "开始游戏"), ("settings", "设置"), ("bindings", "操作说明"))
        rows = [("resume", "继续游戏"), ("character", "角色")]
        if battle:
            rows.append(("settings", "设置"))
        return (*rows, ("bindings", "操作说明"), ("replay", "重看教程"))

    def menu_key(self, key, root, levels):
        if self.page == "bindings":
            if not self.help_key(key):
                self.page, self.focus = root, self.parent_focus
            return
        if key == K.F6 and root == "pause":
            return "replay"
        if key == K.F5:
            self.parent_focus = self.focus if self.page == root else self.parent_focus
            self.open_menu("bindings")
            return
        shortcuts = (K.F1, K.F2, K.F3, K.F4)
        if levels is not None and key in shortcuts:
            index = shortcuts.index(key)
            self.adjust(levels, index, 1)
            if self.page == "settings":
                self.focus = index
            elif self.page == root:
                name = ("镜头震动", "命中闪光", "音量", "粒子密度")[index]
                self.message = f"{name}   {levels[index]} / 3"
            return
        if self.page != root and key == K.ESCAPE:
            self.page, self.focus = root, self.parent_focus
            return
        if self.page == "character":
            return
        if self.page == "settings":
            if key in (K.UP, K.DOWN):
                self.focus = (self.focus + (1 if key == K.DOWN else -1)) % 4
            elif key in (K.LEFT, K.RIGHT, K.ENTER, K.RETURN):
                self.adjust(levels, self.focus, -1 if key == K.LEFT else 1)
            return
        rows = self.menu_items(root, levels is not None)
        if key in (K.UP, K.DOWN):
            self.focus = (self.focus + (1 if key == K.DOWN else -1)) % len(rows)
        elif root == "pause" and key == K.ESCAPE:
            return "resume"
        elif key in (K.ENTER, K.RETURN):
            action = rows[self.focus][0]
            if action in ("start", "resume", "replay"):
                return action
            self.parent_focus = self.focus
            self.open_menu(action)

    def adjust(self, levels, index, delta):
        levels[index] = (levels[index] + delta) % 4
        self.store.update(setting=(index, levels[index]))

    def draw_menu(self, root, levels, *, objective="", location="", seed="", hp=None,
                  stamina=100, weapon="", equipment="", recipe=False):
        page = self.page
        if page == "bindings":
            blit(panel((405, 360), style="scrim", fill="#101c27fb"), 0, 0)
            blit(label("操作说明", 25, 170), 26, 294)
            for i, (action, title, _) in enumerate(ACTIONS):
                x, y = 26 + (i // 6)*181, 250 - (i % 6)*28
                if i == self.selected:
                    blit(panel((174, 24), style="focus", fill="#514638fb"), x-5, y-2)
                blit(label(title, 12, 116), x+10, y)
                blit(label(self.labels[action], 12, 55, GOLD), x+128, y)
            blit(label(self.labels["drop"]+" + "+self.labels["jump"]+"   下穿单向平台", 11, 220, FOAM), 28, 73)
            blit(label("R  结算后重开     1 / 2 / 3  装配", 11, 240, FOAM), 28, 53)
            blit(label(self.message or ("按新键    Esc  取消" if self.listening else "↑ ↓  选择     Enter  改键     Esc  返回"), 12, 355, GOLD), 28, 24)
            return
        blit(panel((335, 360), style="scrim", fill="#101c27fa"), 0, 0)
        if page == "title":
            blit(panel((44, 36), style="text", emblem="bell"), 30, 283)
            blit(label("盐炉渡口   /   潮钟线", 13, 190, GOLD), 31, 249)
            blit(label("余烬回廊", 39, 220), 28, 198)
            blit(label("穿过四道厂门，敲响退潮钟。", 12, 234, FOAM), 32, 175)
        else:
            heading = {"pause":"游戏暂停", "settings":"设置", "character":"遗迹行者"}[page]
            blit(label(location or "盐炉渡口", 12, 210, GOLD), 28, 308)
            blit(label(heading, 27, 185), 26, 264)
        if page in ("pause", "title"):
            rows = self.menu_items(root, levels is not None)
            top = 135 if page == "title" else 226
            for i, (_, text) in enumerate(rows):
                menu_row(text, 28, top - i*26, 202, i == self.focus)
            if page == "pause" and objective:
                blit(label("当前目标", 11, 90, GOLD), 29, 77)
                blit(label(objective, 13, 308), 29, 54)
            if seed:
                blit(label(seed, 11, 220, FOAM), 29, 32)
            if recipe and page == "title":
                blit(label("覆炉甲片炉谱已解锁", 11, 180, FOAM), 29, 51)
            blit(label(self.message or "↑ ↓  选择     Enter  确认", 11, 190, FOAM), 29, 11)
        elif page == "settings":
            for i, name in enumerate(("镜头震动", "命中闪光", "音量", "粒子密度")):
                y = 221 - i*35
                menu_row(name, 28, y, 232, i == self.focus)
                blit(label(("关闭","低","中","高")[levels[i]], 13, 40, GOLD), 184, y)
                for j in range(3):
                    arcade.draw_lbwh_rectangle_filled(218+j*7, y+6, 5, 6, (217,175,113) if j<levels[i] else (65,79,84))
            blit(label("↑ ↓  选择     ← →  调节     Esc  返回", 11, 270, FOAM), 29, 32)
        else:
            for i, (name, value) in enumerate((("生命", str(hp) if hp is not None else "—"),
                    ("奔跑耐力", str(round(stamina))), ("武器", weapon or "—"), ("炉件", equipment or "未装配"))):
                y = 222-i*34
                blit(label(name, 13, 92, FOAM), 29, y)
                blit(label(value, 14, 160), 131, y)
            blit(label("Esc  返回", 11, 90, FOAM), 29, 32)

    def draw_lesson(self, guide):
        name = guide.active
        if name is None:
            return
        key = (
            self.labels[name]
            if name != "move"
            else self.labels["left"] + " / " + self.labels["right"]
        )
        card, cap, cap_x = lesson_card(key, LESSONS[name])
        x = (640 - card.width) // 2
        # Below the quay's lowest walkable surface, bolt targets and ground telegraphs.
        blit(card, x, 12, guide.opacity)
        blit(cap, x + cap_x, 16, guide.key_opacity)


def menu_row(text, x, y, width, selected):
    if selected:
        blit(panel((width, 23), style="focus", fill="#514638ed"), x, y-2)
    blit(label(text, 14, width-20, GOLD if selected else PALE), x+17, y)


@lru_cache(maxsize=32)
def lesson_card(key, label):
    cap_width = max(23, len(key) * 8 + 12)
    width = cap_width + len(label) * 14 + 26
    card = panel((width, 30), [(cap_width + 15, 5, label, 13, PALE)], fill="#14232deb")
    cap = panel((cap_width, 22), [(6, 1, key, 12, GOLD)], style="key")
    return card, cap, 7
