from dataclasses import dataclass

from tiff2png.core.settings import ConvertSettings, Fit

MIN_BOX_SIDE = 1.0


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)

    def scaled(self, factor: float) -> "Box":
        return Box(
            self.left * factor,
            self.top * factor,
            self.right * factor,
            self.bottom * factor,
        )


@dataclass(frozen=True)
class Geometry:
    box: Box
    out_size: tuple[int, int]


def _whole(src_size: tuple[int, int]) -> Box:
    return Box(0.0, 0.0, float(src_size[0]), float(src_size[1]))


def _centred_box(src_size: tuple[int, int], width: float, height: float) -> Box:
    src_w, src_h = src_size
    width = min(width, src_w)
    height = min(height, src_h)
    left = (src_w - width) / 2
    top = (src_h - height) / 2
    return Box(left, top, left + width, top + height)


def _largest_box(src_size: tuple[int, int], aspect: float) -> Box:
    src_w, src_h = src_size
    if src_w / src_h > aspect:
        return _centred_box(src_size, src_h * aspect, src_h)
    return _centred_box(src_size, src_w, src_w / aspect)


def fill_factor(src_size: tuple[int, int], scale: float, target: tuple[int, int]) -> float:
    src_w, src_h = src_size
    return max(scale, target[0] / src_w, target[1] / src_h)


def default_fill_box(
    src_size: tuple[int, int], target: tuple[int, int], scale: float
) -> Box:
    factor = fill_factor(src_size, scale, target)
    return _centred_box(src_size, target[0] / factor, target[1] / factor)


def clamp_box(box: Box, src_size: tuple[int, int], aspect: float) -> Box:
    """Clip box to the image, then shrink it around its centre to the given aspect."""
    src_w, src_h = src_size
    left = max(0.0, min(box.left, box.right))
    right = min(float(src_w), max(box.left, box.right))
    top = max(0.0, min(box.top, box.bottom))
    bottom = min(float(src_h), max(box.top, box.bottom))
    width = right - left
    height = bottom - top
    if width < MIN_BOX_SIDE or height < MIN_BOX_SIDE:
        return _largest_box(src_size, aspect)
    centre_x = (left + right) / 2
    centre_y = (top + bottom) / 2
    if width / height > aspect:
        width = height * aspect
    else:
        height = width / aspect
    if width < MIN_BOX_SIDE or height < MIN_BOX_SIDE:
        return _largest_box(src_size, aspect)
    return Box(
        centre_x - width / 2,
        centre_y - height / 2,
        centre_x + width / 2,
        centre_y + height / 2,
    )


def compute_geometry(
    src_size: tuple[int, int],
    settings: ConvertSettings,
    crop_box: Box | None = None,
) -> Geometry:
    src_w, src_h = src_size
    if src_w < 1 or src_h < 1:
        raise ValueError("Source image has no pixels")
    target = settings.target
    if target is None:
        factor = settings.scale
        return Geometry(_whole(src_size), _round_size(src_w * factor, src_h * factor))
    target_w, target_h = target
    if settings.fit is Fit.FIT:
        factor = min(settings.scale, target_w / src_w, target_h / src_h)
        return Geometry(_whole(src_size), _round_size(src_w * factor, src_h * factor))
    if crop_box is None:
        box = default_fill_box(src_size, target, settings.scale)
    else:
        box = clamp_box(crop_box, src_size, target_w / target_h)
    return Geometry(box, (target_w, target_h))


def preview_geometry(
    geometry: Geometry,
    proxy_size: tuple[int, int],
    factor: float,
    max_out_side: int,
) -> Geometry:
    """Map a source-space geometry onto a proxy that is `factor` times the source size.

    The output size is shrunk, never grown, so its long side is at most max_out_side.
    """
    proxy_w, proxy_h = proxy_size
    box = geometry.box.scaled(factor)
    left = min(max(0.0, box.left), proxy_w - 1.0)
    top = min(max(0.0, box.top), proxy_h - 1.0)
    right = min(float(proxy_w), max(box.right, left + 1.0))
    bottom = min(float(proxy_h), max(box.bottom, top + 1.0))
    out_w, out_h = geometry.out_size
    shrink = min(1.0, max_out_side / max(out_w, out_h))
    return Geometry(Box(left, top, right, bottom), _round_size(out_w * shrink, out_h * shrink))


def _round_size(width: float, height: float) -> tuple[int, int]:
    return max(1, round(width)), max(1, round(height))
