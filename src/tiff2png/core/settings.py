from dataclasses import dataclass
from enum import Enum

from PIL import Image

STANDARD_RESOLUTIONS: dict[str, tuple[int, int] | None] = {
    "Custom": None,
    "4K (3840x2160)": (3840, 2160),
    "2K (2560x1440)": (2560, 1440),
    "Full HD (1920x1080)": (1920, 1080),
    "HD (1280x720)": (1280, 720),
    "SVGA (800x600)": (800, 600),
    "VGA (640x480)": (640, 480),
}

MIN_SCALE = 0.01
MAX_SCALE = 1.0
MAX_TARGET_DIMENSION = 65535


class Fit(Enum):
    FIT = "fit"
    FILL = "fill"


class Resample(Enum):
    NEAREST = Image.Resampling.NEAREST
    BOX = Image.Resampling.BOX
    BILINEAR = Image.Resampling.BILINEAR
    HAMMING = Image.Resampling.HAMMING
    BICUBIC = Image.Resampling.BICUBIC
    LANCZOS = Image.Resampling.LANCZOS


class ColourMode(Enum):
    AUTO = "auto"
    RGB = "rgb"
    RGBA = "rgba"
    L = "l"
    P = "p"


class Dither(Enum):
    NONE = Image.Dither.NONE
    FLOYDSTEINBERG = Image.Dither.FLOYDSTEINBERG


class Pages(Enum):
    FIRST = "first"
    ALL = "all"


@dataclass(frozen=True)
class ConvertSettings:
    scale: float = 1.0
    target: tuple[int, int] | None = None
    fit: Fit = Fit.FIT
    resample: Resample = Resample.LANCZOS
    colour: ColourMode = ColourMode.AUTO
    dither: Dither = Dither.FLOYDSTEINBERG
    optimize: bool = False
    compress_level: int = 9
    pages: Pages = Pages.FIRST

    def __post_init__(self):
        if isinstance(self.scale, bool) or not isinstance(self.scale, (int, float)):
            raise ValueError("Scale must be a number")
        if not MIN_SCALE <= self.scale <= MAX_SCALE:
            raise ValueError(
                f"Scale must be between {MIN_SCALE * 100:g}% and {MAX_SCALE * 100:g}%"
            )
        if self.target is not None:
            try:
                width, height = self.target
            except (TypeError, ValueError):
                raise ValueError("Target must be a (width, height) pair") from None
            for value in (width, height):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError("Target width and height must be whole numbers")
                if not 1 <= value <= MAX_TARGET_DIMENSION:
                    raise ValueError(
                        f"Target width and height must be between 1 and {MAX_TARGET_DIMENSION}"
                    )
            object.__setattr__(self, "target", (width, height))
        for name, enum_type in (
            ("fit", Fit),
            ("resample", Resample),
            ("colour", ColourMode),
            ("dither", Dither),
            ("pages", Pages),
        ):
            if not isinstance(getattr(self, name), enum_type):
                raise ValueError(f"{name} must be a {enum_type.__name__} value")
        if not isinstance(self.optimize, bool):
            raise ValueError("optimize must be True or False")
        if (
            isinstance(self.compress_level, bool)
            or not isinstance(self.compress_level, int)
            or not 0 <= self.compress_level <= 9
        ):
            raise ValueError("Compression level must be a whole number from 0 to 9")
