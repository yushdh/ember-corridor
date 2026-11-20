"""Native frame sizes, atlas layout and top-origin anchors for the tideworks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Strip:
    name: str
    width: int
    height: int
    count: int
    columns: int

    def box(self, index):
        x = index % self.columns * self.width
        y = index // self.columns * self.height
        return x, y, x + self.width, y + self.height


SKY = Strip("tide-sky", 640, 124, 32, 4)
WHEEL = Strip("tide-wheel", 160, 160, 24, 8)
BAY = Strip("moonwater", 300, 50, 24, 6)
WORKS = Strip("workshop", 96, 80, 20, 10)

# Centres in world coordinates, tick interval per frame.
ROOM_WORKS = (
    (8, ((211, 145), (632, 145), (1036, 145))),
    (12, ((195, 146), (638, 146), (1042, 146))),
    (4, ((183, 229), (470, 229), (736, 229), (1028, 229))),
    (9, ((194, 153), (598, 120), (908, 176), (1124, 135))),
    (7, ((277, 150), (524, 160), (807, 181), (1070, 153))),
)
