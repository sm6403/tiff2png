import pytest

from tiff2png.core.geometry import Box, compute_geometry
from tiff2png.core.settings import ConvertSettings, Fit


def fill(scale, target):
    return ConvertSettings(scale=scale, target=target, fit=Fit.FILL)


def fit(scale, target):
    return ConvertSettings(scale=scale, target=target, fit=Fit.FIT)


@pytest.mark.parametrize(
    ("src", "settings", "crop", "out", "box"),
    [
        ((400, 300), fill(0.5, (160, 120)), None, (160, 120), (40, 30, 360, 270)),
        ((400, 300), fill(1.0, (160, 120)), None, (160, 120), (120, 90, 280, 210)),
        ((100, 80), fill(1.0, (200, 200)), None, (200, 200), (10, 0, 90, 80)),
        (
            (400, 300),
            fill(1.0, (160, 120)),
            Box(300, 200, 500, 400),
            (160, 120),
            (300, 212.5, 400, 287.5),
        ),
    ],
)
def test_fill_geometry_table(src, settings, crop, out, box):
    geometry = compute_geometry(src, settings, crop)
    assert geometry.out_size == out
    assert geometry.box.as_tuple() == pytest.approx(box)


@pytest.mark.parametrize("src", [(400, 300), (100, 80), (30, 500), (5000, 40)])
@pytest.mark.parametrize("scale", [0.01, 0.5, 1.0])
@pytest.mark.parametrize("crop", [None, Box(-50, -50, 90, 10), Box(0, 0, 10000, 10000), Box(70, 20, 71, 21)])
def test_fill_box_stays_inside_source_and_matches_target_aspect(src, scale, crop):
    target = (160, 120)
    geometry = compute_geometry(src, fill(scale, target), crop)
    box = geometry.box
    assert geometry.out_size == target
    assert box.left >= -1e-9 and box.top >= -1e-9
    assert box.right <= src[0] + 1e-9 and box.bottom <= src[1] + 1e-9
    assert box.width / box.height == pytest.approx(target[0] / target[1])


def test_fill_default_box_is_centred():
    box = compute_geometry((400, 300), fill(1.0, (100, 100))).box
    assert (box.left + box.right) / 2 == pytest.approx(200)
    assert (box.top + box.bottom) / 2 == pytest.approx(150)


@pytest.mark.parametrize(
    ("src", "scale", "target", "out"),
    [
        ((400, 300), 1.0, (160, 160), (160, 120)),
        ((400, 300), 0.25, (160, 160), (100, 75)),
        ((50, 40), 1.0, (200, 200), (50, 40)),
        ((300, 400), 1.0, (160, 120), (90, 120)),
    ],
)
def test_fit_fits_within_target_and_keeps_aspect(src, scale, target, out):
    geometry = compute_geometry(src, fit(scale, target))
    assert geometry.out_size == out
    assert geometry.out_size[0] <= target[0] and geometry.out_size[1] <= target[1]
    assert geometry.out_size[0] / geometry.out_size[1] == pytest.approx(
        src[0] / src[1], rel=0.02
    )
    assert geometry.box.as_tuple() == (0, 0, src[0], src[1])


def test_no_target_scales_whole_image():
    geometry = compute_geometry((101, 51), ConvertSettings(scale=0.5))
    assert geometry.out_size == (round(50.5), round(25.5))
    assert geometry.box.as_tuple() == (0, 0, 101, 51)


def test_tiny_scale_never_gives_zero_size():
    assert compute_geometry((10, 10), ConvertSettings(scale=0.01)).out_size == (1, 1)


def test_crop_box_ignored_without_fill():
    geometry = compute_geometry((100, 100), fit(1.0, (50, 50)), Box(0, 0, 10, 10))
    assert geometry.box.as_tuple() == (0, 0, 100, 100)
