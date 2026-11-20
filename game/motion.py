from dataclasses import dataclass
from .terrain import FLOOR, GROUND_Y, SURFACES, WORLD_WIDTH, Surface

WIDTH, HEIGHT = 640, 360
STEP = 1 / 120
MAX_STEPS = 12
BODY_HALF_WIDTH = 11
STAND_HEIGHT, TUCK_HEIGHT = 64, 42
RUN_SPEED, ROLL_SPEED = 154, 324
JUMP_SPEED, RELEASE_SPEED, GRAVITY = 444, 202, 1160
GRACE_TICKS = BUFFER_TICKS = 12
ROLL_TICKS, ROLL_RECHARGE = 42, 78
INVULN_START, INVULN_END = 5, 29
LAND_TICKS = 15


def fit_view(width, height):
    scale = max(1, min(width // WIDTH, height // HEIGHT))
    return (
        (width - WIDTH * scale) // 2,
        (height - HEIGHT * scale) // 2,
        WIDTH * scale,
        HEIGHT * scale,
    )


@dataclass
class Walker:
    x: float = 286.0
    y: float = GROUND_Y
    speed: float = 0.0
    vy: float = 0.0
    facing: int = 1
    action: str = "idle"
    age: float = 0.0
    support: Surface | None = FLOOR
    ignore: Surface | None = None
    grace: int = 0
    jump_buffer: int = 0
    roll_age: int = -1
    recharge: int = 0
    landing: int = 0
    tucked: bool = False

    @property
    def invulnerable(self):
        return INVULN_START <= self.roll_age < INVULN_END

    @property
    def height(self):
        return TUCK_HEIGHT if self.tucked else STAND_HEIGHT

    def overlaps_x(self, face):
        return self.x + BODY_HALF_WIDTH > face.left and self.x - BODY_HALF_WIDTH < face.right

    def headroom(self, surfaces):
        return not any(
            not s.one_way
            and self.overlaps_x(s)
            and self.y < s.top
            and self.y + STAND_HEIGHT > s.bottom
            for s in surfaces
        )

    def move_x(self, dx, surfaces):
        # Sweep the leading edge across every solid face crossed by this step.
        target = max(BODY_HALF_WIDTH, min(WORLD_WIDTH - BODY_HALF_WIDTH, self.x + dx))
        for s in surfaces:
            if s.one_way or self.y >= s.top or self.y + self.height <= s.bottom:
                continue
            if dx > 0 and self.x + BODY_HALF_WIDTH <= s.left < target + BODY_HALF_WIDTH:
                target = s.left - BODY_HALF_WIDTH
            if dx < 0 and self.x - BODY_HALF_WIDTH >= s.right > target - BODY_HALF_WIDTH:
                target = s.right + BODY_HALF_WIDTH
        if abs(target - (self.x + dx)) > 1e-8:
            self.speed = 0
        self.x = target

    def move_y(self, dy, surfaces):
        target = self.y + dy
        self.support = None
        for s in surfaces:
            if not self.overlaps_x(s) or s is self.ignore:
                continue
            if dy < 0 and target <= s.top <= self.y:
                target = s.top
                self.vy = 0
                self.support = s
            if (
                dy > 0
                and not s.one_way
                and self.y + self.height <= s.bottom <= target + self.height
            ):
                target = s.bottom - self.height
                self.vy = 0
        self.y = target
        if self.ignore and self.y < self.ignore.top:
            self.ignore = None

    def clear_transients(self, surfaces=SURFACES):
        self.jump_buffer = self.grace = 0
        self.roll_age = -1
        self.speed = 0
        if self.headroom(surfaces):
            self.tucked = False

    def step(self, axis, *, jump=False, held=False, drop=False, roll=False, surfaces=SURFACES):
        previous_support = self.support
        if self.roll_age >= 0:
            self.roll_age += 1
            if self.roll_age == ROLL_TICKS:
                self.roll_age = -1
                self.speed = max(-RUN_SPEED, min(RUN_SPEED, self.speed)) if axis else 0
        self.recharge = max(0, self.recharge - 1)
        if self.roll_age < 0:
            self.tucked = not self.headroom(surfaces)
            if axis:
                self.facing = axis
            if roll and self.support and not self.recharge and not self.tucked:
                self.roll_age, self.recharge, self.tucked = 0, ROLL_RECHARGE, True

        if jump:
            self.jump_buffer = BUFFER_TICKS
        if jump and drop and self.support and self.support.one_way and self.roll_age < 0:
            self.ignore = self.support
            self.support = None
            self.grace = self.jump_buffer = 0
            self.vy = -60
        if self.jump_buffer and (self.support or self.grace) and not self.tucked:
            self.vy = JUMP_SPEED
            self.support = None
            self.grace = self.jump_buffer = 0
        if not held and self.vy > RELEASE_SPEED:
            self.vy = RELEASE_SPEED

        if self.roll_age >= 0:
            self.speed = ROLL_SPEED * self.facing
        else:
            target = axis * (75 if self.tucked else RUN_SPEED)
            accel = (1170 if axis else 1580) if self.support else (740 if axis else 260)
            self.speed += max(-accel * STEP, min(accel * STEP, target - self.speed))
        self.move_x(self.speed * STEP, surfaces)
        self.vy = max(-720, self.vy - GRAVITY * STEP)
        walked_off = self.support is not None
        self.move_y(self.vy * STEP, surfaces)
        self.grace = GRACE_TICKS if walked_off and not self.support else max(0, self.grace - 1)
        self.jump_buffer = max(0, self.jump_buffer - 1)
        self.landing = max(0, self.landing - 1)
        if self.support and not previous_support:
            self.landing = LAND_TICKS
        if self.tucked:
            action = "roll" if self.roll_age >= 0 else "tuck"
        elif not self.support:
            action = "jump" if self.vy > 0 else "fall"
        elif self.landing:
            action = "land"
        else:
            action = "run" if abs(self.speed) > 4 else "idle"
        self.age = self.age + STEP if self.action == action else 0.0
        self.action = action
