import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image, ImageCms

SIZE = (64, 48)
QUADRANT_COLOURS = {
    "tl": (255, 0, 0),
    "tr": (0, 255, 0),
    "bl": (0, 0, 255),
    "br": (255, 255, 0),
}


@dataclass(frozen=True)
class FixtureSpec:
    builder: Callable[[Path], None]
    mode: str
    size: tuple[int, int]
    n_frames: int = 1


def _rgb_pattern(size=SIZE) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    image.putdata(
        [(x * 255 // (width - 1), y * 255 // (height - 1), (x + y) % 256)
         for y in range(height) for x in range(width)]
    )
    return image


def _gradient_values(size, maximum):
    width, height = size
    return [x * maximum // (width - 1) for _ in range(height) for x in range(width)]


def _srgb_profile_bytes() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _rgb(path):
    _rgb_pattern().save(path)


def _rgba(path):
    image = _rgb_pattern().convert("RGBA")
    image.putalpha(Image.linear_gradient("L").resize(SIZE))
    image.save(path)


def _l(path):
    _rgb_pattern().convert("L").save(path)


def _one(path):
    _rgb_pattern().convert("L").convert("1").save(path)


def _p(path):
    _rgb_pattern().quantize(32).save(path)


def _cmyk(path):
    _rgb_pattern().convert("CMYK").save(path)


def _cmyk_icc(path):
    _rgb_pattern().convert("CMYK").save(path, icc_profile=_srgb_profile_bytes())


def _i16(path):
    image = Image.new("I;16", SIZE)
    image.putdata(_gradient_values(SIZE, 65535))
    image.save(path)


def _i32(path):
    width, height = SIZE
    image = Image.new("I", SIZE)
    image.putdata([-500 + x * 100500 // (width - 1) for _ in range(height) for x in range(width)])
    image.save(path)


def _f_unit(path):
    width, height = SIZE
    image = Image.new("F", SIZE)
    image.putdata([x / (width - 1) for _ in range(height) for x in range(width)])
    image.save(path)


def _f_big(path):
    width, height = SIZE
    image = Image.new("F", SIZE)
    image.putdata([x * 1000.0 + (70000.0 if x == width - 1 else 0.0) for _ in range(height) for x in range(width)])
    image.save(path)


def _lab(path):
    image = Image.new("LAB", SIZE)
    image.putdata([(x * 4, 128 + (x - 32), 128 + (y - 24)) for y in range(SIZE[1]) for x in range(SIZE[0])])
    image.save(path)


def _ycbcr(path):
    _rgb_pattern().convert("YCbCr").save(path)


def _multipage(path):
    colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    frames = [Image.new("RGB", SIZE, colour) for colour in colours]
    frames[0].save(path, save_all=True, append_images=frames[1:])


def _exif6(path):
    exif = Image.Exif()
    exif[274] = 6
    image = _rgb_pattern()
    image.putpixel((0, 0), (255, 0, 0))
    image.save(path, exif=exif)


def _dpi_icc(path):
    _rgb_pattern().save(path, dpi=(300, 300), icc_profile=_srgb_profile_bytes())


def _quadrants(path):
    width, height = SIZE
    image = Image.new("RGB", SIZE)
    for name, colour in QUADRANT_COLOURS.items():
        left = 0 if name.endswith("l") else width // 2
        top = 0 if name.startswith("t") else height // 2
        image.paste(colour, (left, top, left + width // 2, top + height // 2))
    image.save(path)


FIXTURES: dict[str, FixtureSpec] = {
    "rgb": FixtureSpec(_rgb, "RGB", SIZE),
    "rgba": FixtureSpec(_rgba, "RGBA", SIZE),
    "l": FixtureSpec(_l, "L", SIZE),
    "one": FixtureSpec(_one, "1", SIZE),
    "p": FixtureSpec(_p, "P", SIZE),
    "cmyk": FixtureSpec(_cmyk, "CMYK", SIZE),
    "cmyk_icc": FixtureSpec(_cmyk_icc, "CMYK", SIZE),
    "i16": FixtureSpec(_i16, "I;16", SIZE),
    "i32": FixtureSpec(_i32, "I", SIZE),
    "f_unit": FixtureSpec(_f_unit, "F", SIZE),
    "f_big": FixtureSpec(_f_big, "F", SIZE),
    "lab": FixtureSpec(_lab, "LAB", SIZE),
    "ycbcr": FixtureSpec(_ycbcr, "YCbCr", SIZE),
    "multipage": FixtureSpec(_multipage, "RGB", SIZE, n_frames=3),
    "exif6": FixtureSpec(_exif6, "RGB", (SIZE[1], SIZE[0])),
    "dpi_icc": FixtureSpec(_dpi_icc, "RGB", SIZE),
    "quadrants": FixtureSpec(_quadrants, "RGB", SIZE),
}


@pytest.fixture
def tiff_dir(tmp_path) -> Path:
    directory = tmp_path / "fixtures"
    directory.mkdir()
    for name, spec in FIXTURES.items():
        spec.builder(directory / f"{name}.tif")
    return directory


@pytest.fixture
def tiff(tiff_dir) -> Callable[[str], Path]:
    return lambda name: tiff_dir / f"{name}.tif"


@pytest.fixture
def noise_image() -> Image.Image:
    data = random.Random(1234).randbytes(256 * 256 * 3)
    return Image.frombytes("RGB", (256, 256), data)
