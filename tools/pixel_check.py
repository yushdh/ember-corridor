"""Readback checks shared by the Windows verification routes."""
import arcade
from PIL import Image, ImageChops, ImageDraw
from game.motion import fit_view


def check_pixels(im):
    x, y, w, h = fit_view(*im.size)
    top = im.height - y - h
    content = im.crop((x, top, x + w, top + h))
    small = content.resize((640, 360), Image.Resampling.NEAREST)
    diff = ImageChops.difference(content, small.resize((w, h), Image.Resampling.NEAREST))
    # Physical-resolution text can split a world pixel. Mask only the actual UI draws.
    scale = w // 640
    draw = ImageDraw.Draw(diff)
    for left, bottom, width, height in arcade.get_window().ui_regions:
        draw.rectangle((left*scale, (360-bottom-height)*scale,
                        (left+width)*scale-1, (360-bottom)*scale-1),fill=0)
    assert not diff.getbbox(), "non-uniform world pixel blocks"
    expected = Image.new("RGB", im.size, (12, 19, 27))
    expected.paste(content, (x, top))
    assert not ImageChops.difference(expected, im).getbbox(), "letterbox mismatch"
    assert small.getextrema()[0][1] - small.getextrema()[0][0] > 160
    return small
