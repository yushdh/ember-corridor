"""Readback checks shared by the Windows verification routes."""
from PIL import Image, ImageChops
from game.motion import fit_view


def check_pixels(im):
    x, y, w, h = fit_view(*im.size)
    top = im.height - y - h
    content = im.crop((x, top, x + w, top + h))
    small = content.resize((640, 360), Image.Resampling.NEAREST)
    assert not ImageChops.difference(
        content, small.resize((w, h), Image.Resampling.NEAREST)
    ).getbbox(), "non-uniform pixel blocks"
    expected = Image.new("RGB", im.size, (12, 19, 27))
    expected.paste(content, (x, top))
    assert not ImageChops.difference(expected, im).getbbox(), "letterbox mismatch"
    assert small.getextrema()[0][1] - small.getextrema()[0][0] > 160
    return small
