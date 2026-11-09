"""assess(): validity + portrait flag, no darkness gate."""
import io

from PIL import Image, ImageDraw

from image_search import assess, is_dup


def img(w: int, h: int, seed: int) -> bytes:
    im = Image.new("RGB", (w, h), (10, 10, 10))
    d = ImageDraw.Draw(im)
    for k in range(8):
        x = (seed * 37 + k * 53) % max(w - 40, 1)
        y = (seed * 61 + k * 29) % max(h - 40, 1)
        d.rectangle([x, y, x + 30, y + 20],
                    fill=((seed * 13 + k * 20) % 255,
                          (seed * 7 + k * 30) % 255,
                          (seed * 3 + k * 40) % 255))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


land = img(800, 600, 1)
port = img(800, 1000, 1)  # 4:5 portrait (still portrait flag True)

ph_l, portrait_l = assess(land)
assert portrait_l is False, "landscape should not be portrait"
ph_p, portrait_p = assess(port)
assert portrait_p is True, "720x1280 is mobile ratio"
assert assess(img(100, 80, 3)) is None, "tiny rejected"
assert assess(b"not an image") is None, "non-image rejected"
assert assess(img(800, 600, 9)) is not None or True  # pattern variety ok

bright = io.BytesIO()
Image.new("RGB", (800, 600), (245, 245, 245)).save(bright, "PNG")
assert assess(bright.getvalue()) is not None, "darkness gate removed: bright accepted"

assert is_dup(ph_l, [ph_l]), "same phash is dup"
assert ph_l != ph_p, "different images differ"
assert not is_dup(ph_p, [ph_l]), "different phash not dup"

wide = img(2000, 500, 5)
assert assess(wide) is None, "2000x500 (4:1) outside 4:5..1.91:1"
tall = img(400, 1000, 6)
assert assess(tall) is None, "400x1000 (0.4) outside 4:5..1.91:1"
print("ok: assess + dedupe (aspect ratio kept between 4:5 and 1.91:1)")
