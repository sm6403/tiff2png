from types import SimpleNamespace

import pytest
from PIL import Image

from tiff2png.core.geometry import Box, compute_geometry
from tiff2png.core.imaging import load_pages, render
from tiff2png.core.settings import ConvertSettings, Fit, Pages
from tiff2png.ui import settings_frame as settings_module

TARGET = (32, 24)
CENTRED = Box(16, 12, 48, 36)


def event(x, y, state=0, keysym=""):
    return SimpleNamespace(x=x, y=y, state=state, keysym=keysym)


def to_canvas(frame, x, y):
    return x * frame.display_scale, y * frame.display_scale


def load_fill(app, tiff, name="quadrants", target=TARGET):
    app.input_path_var.set(str(tiff(name)))
    app.apply_paths()
    frame = app.settings_frame
    frame.manual_width_var.set(str(target[0]))
    frame.manual_height_var.set(str(target[1]))
    frame.fit_var.set(settings_module.FILL_LABEL)
    frame.notify_change()
    app.root.update()
    return app.preview_frame


def assert_box_close(box, expected, tolerance=1.0):
    for got, want in zip(box.as_tuple(), expected.as_tuple()):
        assert got == pytest.approx(want, abs=tolerance)


def drag(frame, start, end):
    frame._on_mouse_down(event(*to_canvas(frame, *start)))
    frame._on_mouse_drag(event(*to_canvas(frame, *end)))
    frame._on_mouse_up(event(*to_canvas(frame, *end)))


def core_output(path, settings, box):
    for _index, image, _meta in load_pages(path, Pages.FIRST):
        return render(image, compute_geometry(image.size, settings, box), settings)


def test_overlay_shows_default_centred_box(app, tiff):
    frame = load_fill(app, tiff)
    assert_box_close(frame.crop_box, CENTRED)
    assert frame.display_scale == pytest.approx(400 / 64)


def test_drag_moves_box_to_top_left_and_conversion_uses_it(app, tiff, tmp_path):
    frame = load_fill(app, tiff)
    drag(frame, (32, 24), (16, 8))
    expected = Box(0, 0, 32, 24)
    assert_box_close(app.crop_box, expected)

    out = tmp_path / "dragged.png"
    app.output_path_var.set(str(out))
    app.convert_single_file()
    settings = app.current_settings()
    with Image.open(out) as result:
        result.load()
        dragged = result.copy()
    reference = core_output(tiff("quadrants"), settings, app.crop_box)
    centred = core_output(tiff("quadrants"), settings, None)
    assert dragged.tobytes() == reference.tobytes()
    assert dragged.tobytes() != centred.tobytes()
    assert dragged.getpixel((0, 0)) == dragged.getpixel((31, 23))


def test_press_on_off_centre_point_does_not_jump(app, tiff):
    frame = load_fill(app, tiff)
    drag(frame, (20, 14), (26, 14))
    assert_box_close(app.crop_box, Box(22, 12, 54, 36))


def test_resize_handle_keeps_aspect_and_anchor(app, tiff):
    frame = load_fill(app, tiff)
    drag(frame, (48, 36), (56, 60))
    box = app.crop_box
    assert box.left == pytest.approx(16, abs=1)
    assert box.top == pytest.approx(12, abs=1)
    assert box.width / box.height == pytest.approx(TARGET[0] / TARGET[1], rel=1e-3)
    assert box.width > 32
    assert box.right <= 64 and box.bottom <= 48
    assert app.proxy.source_size == (64, 48)


def test_resize_is_clamped_to_image(app, tiff):
    frame = load_fill(app, tiff)
    drag(frame, (16, 12), (-40, -40))
    box = app.crop_box
    assert box.left >= 0 and box.top >= 0
    assert box.right == pytest.approx(48, abs=1)
    assert box.width / box.height == pytest.approx(TARGET[0] / TARGET[1], rel=1e-3)


def test_arrow_keys_move_and_shift_resizes(app, tiff):
    frame = load_fill(app, tiff)
    frame._on_key_press(event(0, 0, keysym="Left"))
    assert app.crop_box.left < CENTRED.left
    assert app.crop_box.width == pytest.approx(CENTRED.width)
    before = app.crop_box.width
    frame._on_key_press(event(0, 0, state=1, keysym="Right"))
    assert app.crop_box.width > before
    ratio = app.crop_box.width / app.crop_box.height
    assert ratio == pytest.approx(TARGET[0] / TARGET[1], rel=1e-3)


def test_canvas_has_mouse_and_key_bindings(app):
    canvas = app.preview_frame.canvas
    for sequence in ("<Button-1>", "<B1-Motion>", "<ButtonRelease-1>", "<Key>"):
        assert canvas.bind(sequence)


def test_scale_or_target_change_resets_box(app, tiff):
    frame = load_fill(app, tiff)
    drag(frame, (32, 24), (16, 8))
    assert app.crop_box is not None
    app.settings_frame.manual_width_var.set("40")
    app.settings_frame.manual_height_var.set("30")
    app.settings_frame.notify_change()
    app.root.update()
    assert app.crop_box is None
    assert frame.crop_box.width == pytest.approx(40)


def test_no_overlay_without_fill_target(app, tiff):
    app.input_path_var.set(str(tiff("quadrants")))
    app.apply_paths()
    assert app.preview_frame.crop_box is None


def test_settings_changes_never_reopen_the_file(app, tiff, monkeypatch):
    load_fill(app, tiff)
    calls = []
    real_open = Image.open

    def counting_open(*args, **kwargs):
        calls.append(args)
        return real_open(*args, **kwargs)

    monkeypatch.setattr(Image, "open", counting_open)
    frame = app.settings_frame
    for percent in (90, 80, 70, 60, 50):
        frame.scale_var.set(percent)
        frame.notify_change()
        app.root.update()
    for level in ("1", "2", "3", "4", "5"):
        frame.compress_level_var.set(level)
        frame.notify_change()
        app.root.update()
    assert calls == []


def test_load_opens_the_file_exactly_once(app, tiff, monkeypatch):
    calls = []
    real_open = Image.open

    def counting_open(*args, **kwargs):
        calls.append(args)
        return real_open(*args, **kwargs)

    monkeypatch.setattr(Image, "open", counting_open)
    app.input_path_var.set(str(tiff("quadrants")))
    app.apply_paths()
    frame = app.settings_frame
    for percent in range(90, 0, -10):
        frame.scale_var.set(percent)
        frame.notify_change()
        app.root.update()
    frame.compress_level_var.set("4")
    frame.notify_change()
    app.root.update()
    assert len(calls) == 1


def test_large_source_is_proxied_but_converted_at_full_size(app, tmp_path, monkeypatch):
    big = tmp_path / "big.tif"
    Image.new("RGB", (3000, 2000), (10, 200, 30)).save(big)
    app.input_path_var.set(str(big))
    app.apply_paths()
    assert max(app.proxy.image.size) == 1024
    assert app.proxy.source_size == (3000, 2000)
    out = tmp_path / "big.png"
    app.output_path_var.set(str(out))
    app.settings_frame.scale_var.set(50)
    app.settings_frame.notify_change()
    app.root.update()
    app.convert_single_file()
    with Image.open(out) as result:
        assert result.size == (1500, 1000)
