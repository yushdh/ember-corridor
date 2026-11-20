"""Salt quay geometry in world pixels, origin at bottom left."""
from dataclasses import dataclass

WORLD_WIDTH = 1280
GROUND_Y = 94


@dataclass(frozen=True)
class Surface:
    name: str
    left: int
    right: int
    bottom: int
    top: int
    one_way: bool = False


FLOOR = Surface("quay", 0, WORLD_WIDTH, 0, GROUND_Y)
SURFACES = (
    FLOOR,
    Surface("weighbridge", 161, 253, 171, 191),
    Surface("sling", 356, 473, 147, 157, True),
    Surface("landing", 532, 657, GROUND_Y, 141),
    Surface("gantry", 735, 808, 140, 161),
    Surface("lift", 888, 984, 141, 151, True),
    Surface("sluice", 1028, 1126, GROUND_Y, 169),
    Surface("gallery", 1146, 1251, 214, 224, True),
)
