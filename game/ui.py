"""Native-density type and hand-drawn interface ornaments for the foundry."""
from dataclasses import dataclass
from functools import lru_cache

import arcade
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

from .resources import font_face

GOLD, FOAM, PALE = "#e6b977", "#abbaaf", "#f8efdb"
INK = "#121e29"


@dataclass(frozen=True)
class Panel:
    width: int
    height: int
    lines: tuple
    style: str
    fill: str
    emblem: str | None


def panel(size, lines=(), *, style="card", fill="#14232df5", emblem=None):
    return Panel(*size, tuple(lines), style, fill, emblem)


def tag(text, width, color=PALE):
    return panel((width, 21), [(7, 1, text, 12, color)])


def label(text, size, width, color=PALE):
    return panel((width, size + 6), [(0, 0, text, size, color)], style="text")


@lru_cache(maxsize=127)
def stamina_track(fill):
    # The 126-pixel track has exactly 127 distinct fill widths.
    im = Image.new("RGBA", (128, 10), (106, 103, 87))
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, 126, 8), fill=(31, 43, 49))
    if fill:
        d.rectangle((1, 1, fill, 8), fill=(196, 137, 66))
        d.rectangle((1, 1, fill, 3), fill=(239, 192, 118))
        d.line((fill, 2, fill, 7), fill=(255, 224, 157))
    for i in (1, 2, 3):
        x = 1 + round(126*i/4)
        d.line((x, 7, x, 8), fill=(73, 64, 52))
    return arcade.Texture(im)


def draw_stamina(stamina):
    blit(stamina_track(round(126 * stamina / 100)), 49, 324)
    value = str(round(stamina))
    blit(label(value, 10, 21, GOLD), 176-6*len(value), 334)


@lru_cache(maxsize=64)
def font(pixels):
    return ImageFont.truetype(font_face(), pixels)


@lru_cache(maxsize=256)
def raster(spec, scale):
    w, h = spec.width * scale, spec.height * scale
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)

    def points(coords):
        return [(round(x * scale), round(y * scale)) for x, y in coords]

    def polygon(coords, color):
        d.polygon(points(coords), fill=color)

    def line(coords, color, weight=1):
        d.line(points(coords), fill=color, width=max(1, round(weight * scale)))

    if spec.style in ("card", "scrim", "focus", "chapter", "toast", "hud"):
        r, g, b, a = ImageColor.getcolor(spec.fill, "RGBA")
        for x in range(w):
            u = x / max(1, w - 1)
            if spec.style in ("chapter", "toast"):
                u = abs(2*u - 1)
            fade = min(1, (1-u) / (0.48 if spec.style == "scrim" else 0.25))
            d.line((x, 0, x, h), fill=(r, g, b, round(a*fade)))
        if spec.style in ("chapter", "toast", "hud", "card"):
            feather = Image.new("L", (1, h))
            edge = max(1, round(h * (0.45 if spec.style == "chapter" else 0.22)))
            feather.putdata([round(255 * min(1, (y+1)/edge, (h-y)/edge)) for y in range(h)])
            im.putalpha(ImageChops.multiply(im.getchannel("A"), feather.resize((w, h))))
    if spec.style == "focus":
        polygon([(0, 1), (2, 1), (2, spec.height-2), (0, spec.height-2)], GOLD)
        polygon([(7, spec.height/2-3), (11, spec.height/2), (7, spec.height/2+3)], GOLD)
    elif spec.style == "key":
        d.rounded_rectangle((0, 0, w-1, h-1), radius=2*scale, fill="#283a43", outline="#8e927d", width=scale)
        line([(3,spec.height-3),(spec.width-4,spec.height-3)], "#536064")
    elif spec.style == "chapter":
        cx = spec.width // 2
        y = spec.height - 6
        line([(cx-55,y),(cx-6,y)], "#ad946c")
        line([(cx+6,y),(cx+55,y)], "#ad946c")
        polygon([(cx-3,y),(cx,y-3),(cx+3,y),(cx,y+3)], GOLD)
    if spec.emblem in ("light", "heavy"):
        # Worn tang, crossguard and asymmetric cutting edge read at the same icon size.
        polygon([(1,16),(14,1),(26,1),(31,7),(31,20),(19,32),(7,32),(1,26)], "#293a43")
        line([(1,19),(1,15),(14,1),(23,1)], "#a38a64")
        line([(6,27),(12,21)], "#b28858", 3)
        if spec.emblem == "light":
            polygon([(11,21),(15,15),(23,11),(28,5),(27,12),(22,18),(15,22)], "#e5c594")
            line([(15,21),(22,17),(27,11)], "#fff0bc")
            line([(9,17),(16,24)], "#bd9667", 2)
        else:
            line([(11,23),(22,10)], "#ceb084", 3)
            polygon([(15,9),(20,5),(28,10),(29,14),(25,18),(17,13)], "#91a7aa")
            line([(16,9),(21,6),(27,10)], "#f0e1bc")
    if spec.emblem == "bell":
        # A hanging bronze bell, a cut arch and the two tide marks beneath it.
        line([(1,24),(1,12),(12,1),(25,1),(36,12),(36,24)], "#907954")
        line([(6,22),(10,18),(11,12),(15,8),(21,8),(25,13),(26,18),(30,22),(6,22)], GOLD, 2)
        polygon([(15,24),(22,24),(20,27),(17,27)], "#e7c58a")
        line([(4,29),(12,31),(20,29),(28,31),(33,29)], "#8aa59c")
    for x, y, text, size, color in spec.lines:
        d.text((x*scale, y*scale), text, font=font(size*scale), fill=color,
               anchor="mt" if spec.style in ("chapter", "toast") else None,
               stroke_width=int(spec.style == "text"), stroke_fill="#1c2931")
    return arcade.Texture(im)


def blit(spec, x, y, alpha=255):
    if isinstance(spec, Panel):
        window = arcade.get_window()
        tex = raster(spec, window.ui_scale)
        window.ui_regions.append((x, y, spec.width, spec.height))
    else:
        tex = spec
    arcade.draw_texture_rect(
        tex, arcade.LBWH(x, y, spec.width, spec.height), alpha=alpha, pixelated=True
    )
