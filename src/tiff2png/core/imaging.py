import io
import math
import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

from tiff2png.core.geometry import Geometry
from tiff2png.core.settings import ColourMode, ConvertSettings, Dither, Pages, Resample

KEEP_MODES = frozenset({"1", "L", "LA", "P", "RGB", "RGBA", "I;16"})
SIXTEEN_BIT_MODES = frozenset({"I;16", "I;16B", "I;16L", "I;16N"})
GRAY_PROFILE_MODES = frozenset({"1", "L", "LA", "I;16"})
RGB_PROFILE_MODES = frozenset({"P", "RGB", "RGBA"})
MAX_16_BIT = 65535
X_RESOLUTION_TAG = 282
Y_RESOLUTION_TAG = 283


@dataclass(frozen=True)
class PageMeta:
    icc_profile: bytes | None = None
    dpi: tuple[float, float] | None = None


def load_pages(
    path: str | os.PathLike, pages: Pages
) -> Iterator[tuple[int, Image.Image, PageMeta]]:
    with Image.open(path) as source:
        frame_count = getattr(source, "n_frames", 1)
        indices = range(frame_count) if pages is Pages.ALL else range(1)
        for index in indices:
            source.seek(index)
            source.load()
            icc_profile = source.info.get("icc_profile")
            dpi = _read_dpi(source)
            oriented = ImageOps.exif_transpose(source)
            image, icc_profile = normalise(oriented, icc_profile)
            yield index, image, PageMeta(icc_profile=icc_profile, dpi=dpi)


def _read_dpi(source: Image.Image) -> tuple[float, float] | None:
    tags = getattr(source, "tag_v2", {})
    value = source.info.get("dpi")
    if not value or X_RESOLUTION_TAG not in tags or Y_RESOLUTION_TAG not in tags:
        return None
    x_dpi, y_dpi = value
    if x_dpi <= 0 or y_dpi <= 0:
        return None
    return float(x_dpi), float(y_dpi)


def normalise(
    image: Image.Image, icc_profile: bytes | None = None
) -> tuple[Image.Image, bytes | None]:
    mode = image.mode
    if mode in KEEP_MODES:
        return image, icc_profile
    if mode in ("I;16B", "I;16L", "I;16N"):
        return image.convert("I;16"), icc_profile
    if mode in ("RGBX", "YCbCr"):
        return image.convert("RGB"), icc_profile
    if mode in ("RGBa", "PA"):
        return image.convert("RGBA"), icc_profile
    if mode == "CMYK":
        return _cmyk_to_rgb(image, icc_profile), None
    if mode == "LAB":
        return image.convert("RGB"), None
    if mode == "I":
        return image.convert("I;16"), icc_profile
    if mode == "F":
        return _float_to_16_bit(image), icc_profile
    raise ValueError(f"Unsupported TIFF image mode: {mode}")


def _cmyk_to_rgb(image: Image.Image, icc_profile: bytes | None) -> Image.Image:
    if icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
            srgb_profile = ImageCms.createProfile("sRGB")
            return ImageCms.profileToProfile(
                image, source_profile, srgb_profile, outputMode="RGB"
            )
        except ImageCms.PyCMSError:
            pass
    return image.convert("RGB")


def _float_to_16_bit(image: Image.Image) -> Image.Image:
    low, high = image.getextrema()
    if 0.0 <= low and high <= 1.0:
        image = image.point(lambda value: value * MAX_16_BIT + 0.5)
    return image.convert("I").convert("I;16")


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA"):
        return image.getchannel("A").getextrema()[0] < 255
    return "transparency" in image.info


def _prepare_for_resize(image: Image.Image, resample: Resample) -> Image.Image:
    if resample is Resample.NEAREST:
        return image
    if image.mode == "P":
        return image.convert("RGBA" if "transparency" in image.info else "RGB")
    if image.mode == "1":
        return image.convert("L")
    return image


def _to_8_bit(image: Image.Image) -> Image.Image:
    if image.mode == "I;16":
        return image.point(lambda value: value / 256, "L")
    return image


def render(image: Image.Image, geometry: Geometry, settings: ConvertSettings) -> Image.Image:
    prepared = _prepare_for_resize(image, settings.resample)
    resized = prepared.resize(
        geometry.out_size, settings.resample.value, box=geometry.box.as_tuple()
    )
    return _apply_colour(resized, settings)


def _apply_colour(image: Image.Image, settings: ConvertSettings) -> Image.Image:
    colour = settings.colour
    if colour is ColourMode.AUTO:
        return image
    image = _to_8_bit(image)
    if colour is ColourMode.P:
        return _to_palette(image, settings.dither)
    return image.convert(colour.name)


def _to_palette(image: Image.Image, dither: Dither) -> Image.Image:
    if image.mode == "P":
        return image
    if _has_alpha(image):
        return image.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE)
    rgb = image.convert("RGB")
    palette = rgb.quantize(256, method=Image.Quantize.MEDIANCUT)
    return rgb.quantize(palette=palette, dither=dither.value)


def _profile_matches(icc_profile: bytes, mode: str) -> bool:
    colour_space = icc_profile[16:20]
    if mode in GRAY_PROFILE_MODES:
        return colour_space == b"GRAY"
    if mode in RGB_PROFILE_MODES:
        return colour_space == b"RGB "
    return False


def _png_options(settings: ConvertSettings) -> dict:
    return {
        "optimize": settings.optimize,
        "compress_level": settings.compress_level,
    }


def save_png(
    image: Image.Image,
    path: str | os.PathLike,
    settings: ConvertSettings,
    meta: PageMeta | None = None,
) -> None:
    options = _png_options(settings)
    options["icc_profile"] = None
    if meta is not None:
        if meta.dpi is not None:
            options["dpi"] = meta.dpi
        if meta.icc_profile and _profile_matches(meta.icc_profile, image.mode):
            options["icc_profile"] = meta.icc_profile
    destination = Path(path)
    descriptor, temp_name = tempfile.mkstemp(
        dir=destination.parent, prefix=destination.stem + ".", suffix=".tmp"
    )
    os.close(descriptor)
    try:
        image.save(temp_name, format="PNG", **options)
        os.replace(temp_name, destination)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def estimate_png_size(
    proxy_output: Image.Image, out_size: tuple[int, int], settings: ConvertSettings
) -> int:
    buffer = io.BytesIO()
    proxy_output.save(buffer, format="PNG", **_png_options(settings))
    proxy_pixels = proxy_output.width * proxy_output.height
    out_pixels = out_size[0] * out_size[1]
    return max(1, round(buffer.tell() * out_pixels / proxy_pixels))


def format_size(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    index = min(int(math.log(size_bytes, 1024)), len(units) - 1)
    if index == 0:
        return f"{round(size_bytes)} B"
    return f"{round(size_bytes / 1024**index, 2)} {units[index]}"
