import pytest
from PIL import Image

from tiff2png.core.settings import (
    STANDARD_RESOLUTIONS,
    ConvertSettings,
    Dither,
    Resample,
)


def test_defaults_are_valid():
    settings = ConvertSettings()
    assert settings.resample is Resample.LANCZOS
    assert settings.compress_level == 9


def test_enums_map_to_pillow_constants():
    assert Resample.NEAREST.value is Image.Resampling.NEAREST
    assert Resample.LANCZOS.value is Image.Resampling.LANCZOS
    assert Dither.NONE.value is Image.Dither.NONE
    assert Dither.FLOYDSTEINBERG.value is Image.Dither.FLOYDSTEINBERG


def test_has_no_interlace_or_chunk_fields():
    fields = set(ConvertSettings.__dataclass_fields__)
    assert not {name for name in fields if "interlace" in name or "chunk" in name}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"scale": 0},
        {"scale": 0.001},
        {"scale": 1.5},
        {"scale": "50"},
        {"target": (0, 10)},
        {"target": (10, -1)},
        {"target": (10.5, 10)},
        {"target": (10,)},
        {"compress_level": 10},
        {"compress_level": -1},
        {"resample": "lanczos"},
        {"dither": "NONE"},
        {"optimize": "yes"},
    ],
)
def test_invalid_settings_raise_value_error(kwargs):
    with pytest.raises(ValueError):
        ConvertSettings(**kwargs)


def test_settings_are_frozen():
    with pytest.raises(AttributeError):
        ConvertSettings().scale = 0.5


def test_standard_resolutions_single_source():
    assert STANDARD_RESOLUTIONS["Custom"] is None
    assert STANDARD_RESOLUTIONS["Full HD (1920x1080)"] == (1920, 1080)
