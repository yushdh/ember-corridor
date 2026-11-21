"""One fitted insert per expedition. Ranks stay on the insert when it is replaced."""
from dataclasses import dataclass, field, replace

COOLDOWN = 420  # Base seal cooldown in simulation ticks.


@dataclass(frozen=True)
class Insert:
    name: str
    effect: str


INSERTS = {
    "tooth": Insert("赤铜刃齿", "每阶使普攻和蓄焰斩伤害 +6"),
    "tide": Insert("回潮轮", "每阶使潮印冷却缩短 0.6 秒"),
    "shell": Insert("覆炉甲片", "每阶使受到的伤害减少 3 点"),
}


@dataclass
class Loadout:
    shell_known: bool = False
    equipped: str | None = None
    ranks: dict = field(default_factory=dict)

    @property
    def options(self):
        return tuple(INSERTS) if self.shell_known else ("tooth", "tide")

    def fit(self, item):
        if item not in self.options:
            raise ValueError("未解锁的炉件")
        self.ranks[item] = self.ranks.get(item, 0) + 1
        self.equipped = item

    def rank(self, item):
        return self.ranks.get(item, 0) if self.equipped == item else 0

    def after_fit(self, item):
        preview = replace(self, ranks=self.ranks.copy())
        preview.fit(item)
        return preview

    def melee_damage(self, base):
        return base + 6 * self.rank("tooth")

    @property
    def seal_period(self):
        return COOLDOWN - 72 * self.rank("tide")

    @property
    def damage_reduction(self):
        return 3 * self.rank("shell")
