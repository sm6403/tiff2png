import io
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from conftest import FIXTURES, QUADRANT_COLOURS
from tiff2png.core.geometry import Box, compute_geometry
from tiff2png.core.imaging import (
    PageMeta,
    estimate_png_size,
    format_size,
    load_pages,
    render,
    save_png,
)
from tiff2png.core.settings import (
    ColourMode,
    ConvertSettings,
    Dither,
    Fit,
    Pages,
    Resample,
)

CMYK_PROFILE = Path(r"C:\Windows\System32\spool\drivers\color\USWebCoatedSWOP.icc")


def first_page(path):
    pages = list(load_pages(path, Pages.FIRST))
    assert len(pages) == 1
    return pages[0]


def convert(path, settings, crop_box=None, dst=None):
    _, image, meta = first_page(path)
    geometry = compute_geometry(image.size, settings, crop_box)
    out = render(image, geometry, settings)
    if dst is not None:
        save_png(out, dst, settings, meta)
    return out, meta


def colours(image):
    data = image.convert("RGB").tobytes()
    return set(zip(data[0::3], data[1::3], data[2::3]))


def srgb_bytes():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_fixture_mode_saves_to_a_png_that_reopens(tiff, tmp_path, name):
    settings = ConvertSettings(scale=0.5)
    dst = tmp_path / "out.png"
    out, _ = convert(tiff(name), settings, dst=dst)
    with Image.open(dst) as reopened:
        reopened.load()
        assert reopened.format == "PNG"
        assert reopened.size == out.size
        assert reopened.mode == out.mode
        assert reopened.mode in {"1", "L", "LA", "P", "RGB", "RGBA", "I;16"}


@pytest.mark.parametrize(
    ("name", "mode"),
    [
        ("cmyk", "RGB"),
        ("cmyk_icc", "RGB"),
        ("lab", "RGB"),
        ("ycbcr", "RGB"),
        ("i16", "I;16"),
        ("i32", "I;16"),
        ("f_unit", "I;16"),
        ("f_big", "I;16"),
        ("one", "1"),
        ("p", "P"),
        ("rgba", "RGBA"),
    ],
)
def test_normalised_mode(tiff, name, mode):
    _, image, _ = first_page(tiff(name))
    assert image.mode == mode


def test_alpha_survives_to_png(tiff, tmp_path):
    dst = tmp_path / "a.png"
    convert(tiff("rgba"), ConvertSettings(), dst=dst)
    with Image.open(dst) as reopened:
        low, high = reopened.convert("RGBA").getchannel("A").getextrema()
    assert low < high


def test_alpha_survives_palette_conversion(tiff, tmp_path):
    dst = tmp_path / "a.png"
    out, _ = convert(tiff("rgba"), ConvertSettings(colour=ColourMode.P), dst=dst)
    assert out.mode == "P"
    with Image.open(dst) as reopened:
        low, high = reopened.convert("RGBA").getchannel("A").getextrema()
    assert low < 64 and high > 192


def test_icc_and_dpi_survive(tiff, tmp_path):
    dst = tmp_path / "icc.png"
    _, meta = convert(tiff("dpi_icc"), ConvertSettings(scale=0.5), dst=dst)
    assert meta.icc_profile == srgb_bytes()
    with Image.open(dst) as reopened:
        assert reopened.info["icc_profile"] == srgb_bytes()
        assert reopened.info["dpi"] == pytest.approx((300, 300), abs=0.01)


def test_rgb_profile_is_dropped_when_output_is_grey(tiff, tmp_path):
    dst = tmp_path / "grey.png"
    convert(tiff("dpi_icc"), ConvertSettings(colour=ColourMode.L), dst=dst)
    with Image.open(dst) as reopened:
        assert "icc_profile" not in reopened.info
        assert reopened.mode == "L"


def test_no_profile_or_dpi_means_none_written(tiff, tmp_path):
    dst = tmp_path / "plain.png"
    _, meta = convert(tiff("rgb"), ConvertSettings(), dst=dst)
    assert meta == PageMeta()
    with Image.open(dst) as reopened:
        assert "icc_profile" not in reopened.info


def test_exif_orientation_6_swaps_dimensions_and_rotates(tiff):
    _, image, _ = first_page(tiff("exif6"))
    assert image.size == (48, 64)
    assert image.getpixel((47, 0)) == (255, 0, 0)


def test_cmyk_profile_not_carried_into_png(tiff, tmp_path):
    dst = tmp_path / "c.png"
    out, meta = convert(tiff("cmyk_icc"), ConvertSettings(), dst=dst)
    assert out.mode == "RGB"
    assert meta.icc_profile is None
    with Image.open(dst) as reopened:
        assert "icc_profile" not in reopened.info


@pytest.mark.skipif(not CMYK_PROFILE.exists(), reason="no system CMYK ICC profile")
def test_cmyk_with_real_profile_goes_through_colour_management(tmp_path):
    cmyk = Image.new("CMYK", (8, 8), (0, 255, 255, 0))
    path = tmp_path / "real.tif"
    cmyk.save(path, icc_profile=CMYK_PROFILE.read_bytes())
    managed, _ = convert(path, ConvertSettings())
    plain = cmyk.convert("RGB").getpixel((0, 0))
    assert managed.getpixel((0, 0)) != plain
    assert managed.mode == "RGB"


def test_16_bit_values_survive_auto(tiff):
    out, _ = convert(tiff("i16"), ConvertSettings(resample=Resample.NEAREST))
    assert out.mode == "I;16"
    assert out.getextrema() == (0, 65535)


def test_16_bit_resizes_with_every_filter(tiff):
    for resample in Resample:
        out, _ = convert(tiff("i16"), ConvertSettings(scale=0.5, resample=resample))
        assert out.mode == "I;16"
        assert out.size == (32, 24)
        assert out.getextrema()[1] > 50000


def test_16_bit_to_grey_scales_not_clips(tiff):
    out, _ = convert(
        tiff("i16"), ConvertSettings(colour=ColourMode.L, resample=Resample.NEAREST)
    )
    low, high = out.getextrema()
    assert low == 0 and high == 255
    assert 120 <= out.getpixel((32, 10)) <= 135


def test_32_bit_int_is_clipped_to_16_bit(tiff):
    _, image, _ = first_page(tiff("i32"))
    assert image.mode == "I;16"
    assert image.getextrema() == (0, 65535)


def test_float_in_unit_range_is_scaled(tiff):
    _, image, _ = first_page(tiff("f_unit"))
    assert image.getextrema() == (0, 65535)
    assert image.getpixel((32, 0)) == pytest.approx(65535 * 32 / 63, abs=2)


def test_float_outside_unit_range_is_clipped_not_scaled(tiff):
    _, image, _ = first_page(tiff("f_big"))
    assert image.getpixel((1, 0)) == 1000
    assert image.getpixel((63, 0)) == 65535


def test_lab_converts_to_rgb(tiff):
    _, image, meta = first_page(tiff("lab"))
    assert image.mode == "RGB"
    assert meta.icc_profile is None
    assert image.getpixel((63, 0)) != image.getpixel((0, 0))


def test_multipage_yields_every_page_only_when_asked(tiff):
    first = list(load_pages(tiff("multipage"), Pages.FIRST))
    every = list(load_pages(tiff("multipage"), Pages.ALL))
    assert [index for index, _, _ in first] == [0]
    assert [index for index, _, _ in every] == [0, 1, 2]
    assert [image.getpixel((0, 0)) for _, image, _ in every] == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]


def test_source_file_is_closed_after_loading(tiff):
    path = tiff("rgb")
    for _ in load_pages(path, Pages.FIRST):
        pass
    path.rename(path.with_name("renamed.tif"))


def test_source_file_is_closed_when_generator_is_abandoned(tiff):
    path = tiff("multipage")
    pages = load_pages(path, Pages.ALL)
    next(pages)
    pages.close()
    path.rename(path.with_name("renamed.tif"))


def test_corrupt_file_raises_a_specific_error(tmp_path):
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"not a tiff")
    with pytest.raises(Image.UnidentifiedImageError):
        list(load_pages(bad, Pages.FIRST))


def test_fill_corners_are_the_expected_quadrant_colours(tiff):
    settings = ConvertSettings(target=(32, 32), fit=Fit.FILL)
    out, _ = convert(tiff("quadrants"), settings)
    assert out.size == (32, 32)
    assert out.getpixel((0, 0)) == QUADRANT_COLOURS["tl"]
    assert out.getpixel((31, 0)) == QUADRANT_COLOURS["tr"]
    assert out.getpixel((0, 31)) == QUADRANT_COLOURS["bl"]
    assert out.getpixel((31, 31)) == QUADRANT_COLOURS["br"]
    assert (0, 0, 0) not in colours(out)


def test_fill_upscale_when_source_is_smaller_than_target_has_no_padding(tiff):
    settings = ConvertSettings(scale=0.5, target=(200, 200), fit=Fit.FILL)
    out, _ = convert(tiff("quadrants"), settings)
    assert out.size == (200, 200)
    assert out.getpixel((0, 0)) == QUADRANT_COLOURS["tl"]
    assert out.getpixel((199, 199)) == QUADRANT_COLOURS["br"]
    assert (0, 0, 0) not in colours(out)


def test_fill_crop_box_selects_source_region(tiff):
    settings = ConvertSettings(target=(16, 12), fit=Fit.FILL)
    out, _ = convert(tiff("quadrants"), settings, crop_box=Box(0, 0, 20, 15))
    assert colours(out) == {QUADRANT_COLOURS["tl"]}
    out, _ = convert(tiff("quadrants"), settings, crop_box=Box(44, 33, 64, 48))
    assert colours(out) == {QUADRANT_COLOURS["br"]}


def test_fit_output_fits_target_with_right_aspect(tiff):
    settings = ConvertSettings(target=(40, 40), fit=Fit.FIT)
    out, _ = convert(tiff("rgb"), settings)
    assert out.size == (40, 30)


def test_palette_dither_changes_pixels_on_a_gradient(tmp_path):
    gradient = Image.linear_gradient("L").convert("RGB")
    path = tmp_path / "g.tif"
    gradient.save(path)
    plain, _ = convert(path, ConvertSettings(colour=ColourMode.P, dither=Dither.NONE))
    dithered, _ = convert(
        path, ConvertSettings(colour=ColourMode.P, dither=Dither.FLOYDSTEINBERG)
    )
    assert plain.mode == dithered.mode == "P"
    assert plain.tobytes() != dithered.tobytes()


def test_resample_filter_is_used(noise_image, tmp_path):
    path = tmp_path / "n.tif"
    noise_image.save(path)
    nearest, _ = convert(path, ConvertSettings(scale=0.37, resample=Resample.NEAREST))
    lanczos, _ = convert(path, ConvertSettings(scale=0.37, resample=Resample.LANCZOS))
    assert nearest.size == lanczos.size
    assert nearest.tobytes() != lanczos.tobytes()


def test_non_nearest_resample_of_palette_image_is_smooth(tiff):
    out, _ = convert(tiff("p"), ConvertSettings(scale=0.5, resample=Resample.LANCZOS))
    assert out.mode == "RGB"


def test_compress_level_0_is_bigger_than_9(tiff, tmp_path):
    sizes = {}
    for level in (0, 9):
        dst = tmp_path / f"c{level}.png"
        convert(tiff("rgb"), ConvertSettings(compress_level=level), dst=dst)
        sizes[level] = dst.stat().st_size
    assert sizes[0] > sizes[9]


def test_save_replaces_existing_file_and_leaves_no_temp(tiff, tmp_path):
    dst = tmp_path / "x.png"
    dst.write_bytes(b"old")
    convert(tiff("rgb"), ConvertSettings(), dst=dst)
    assert dst.read_bytes()[:4] == b"\x89PNG"
    assert list(tmp_path.glob("*.tmp")) == []


def test_failed_save_keeps_old_file_and_leaves_no_temp(tiff, tmp_path, monkeypatch):
    dst = tmp_path / "x.png"
    dst.write_bytes(b"old")
    _, image, meta = first_page(tiff("rgb"))

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError):
        save_png(image, dst, ConvertSettings(), meta)
    assert dst.read_bytes() == b"old"
    assert list(tmp_path.glob("*.tmp")) == []


def proxy_estimate(source: Image.Image, settings: ConvertSettings):
    geometry = compute_geometry(source.size, settings)
    actual = io.BytesIO()
    render(source, geometry, settings).save(
        actual, format="PNG", compress_level=settings.compress_level
    )
    proxy = source.resize((source.width // 2, source.height // 2), Resample.BOX.value)
    proxy_geometry = compute_geometry(proxy.size, settings)
    estimate = estimate_png_size(
        render(proxy, proxy_geometry, settings), geometry.out_size, settings
    )
    return estimate, actual.tell()


def test_estimate_is_within_half_to_double_on_flat_image():
    flat = Image.new("RGB", (512, 512), (10, 120, 200))
    estimate, actual = proxy_estimate(flat, ConvertSettings())
    assert 0.5 * actual <= estimate <= 2 * actual


def test_estimate_is_within_half_to_double_on_noise_image(noise_image):
    estimate, actual = proxy_estimate(noise_image, ConvertSettings())
    assert 0.5 * actual <= estimate <= 2 * actual


def test_estimate_scales_with_output_size(noise_image):
    settings = ConvertSettings()
    small = estimate_png_size(noise_image, (256, 256), settings)
    large = estimate_png_size(noise_image, (512, 512), settings)
    assert large == pytest.approx(4 * small, rel=0.01)


@pytest.mark.parametrize(
    ("size", "text"),
    [(0, "0 B"), (512, "512 B"), (1536, "1.5 KB"), (5 * 1024**2, "5.0 MB")],
)
def test_format_size(size, text):
    assert format_size(size) == text
