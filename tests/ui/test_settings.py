import shutil
import time
import tkinter as tk

import pytest
from PIL import Image

from tiff2png import __version__
from tiff2png.core.geometry import compute_geometry
from tiff2png.core.imaging import load_pages, render
from tiff2png.core.settings import (
    STANDARD_RESOLUTIONS,
    ColourMode,
    ConvertSettings,
    Dither,
    Fit,
    Pages,
    Resample,
)
from tiff2png.ui import settings_frame as settings_module


def all_widget_text(widget):
    texts = []
    for option in ("text", "values"):
        try:
            value = widget.cget(option)
        except tk.TclError:
            continue
        if isinstance(value, (tuple, list)):
            texts.extend(str(item) for item in value)
        else:
            texts.append(str(value))
    for child in widget.winfo_children():
        texts.extend(all_widget_text(child))
    return texts


def test_defaults_match_core_defaults_with_ui_optimize(app):
    assert app.current_settings() == ConvertSettings(optimize=True)


def test_variables_map_to_settings(app):
    frame = app.settings_frame
    frame.scale_var.set(50)
    frame.manual_width_var.set("320")
    frame.manual_height_var.set("200")
    frame.fit_var.set(settings_module.FILL_LABEL)
    frame.color_mode_var.set("P")
    frame.dither_var.set("NONE")
    frame.filter_var.set("NEAREST")
    frame.compress_level_var.set("3")
    frame.optimize_var.set(False)
    assert app.current_settings() == ConvertSettings(
        scale=0.5,
        target=(320, 200),
        fit=Fit.FILL,
        resample=Resample.NEAREST,
        colour=ColourMode.P,
        dither=Dither.NONE,
        optimize=False,
        compress_level=3,
        pages=Pages.FIRST,
    )
    assert app.settings_error is None


def test_standard_resolution_selection_fills_target(app):
    frame = app.settings_frame
    frame.resolution_var.set("VGA (640x480)")
    frame.on_resolution_selected()
    settings = app.current_settings()
    assert settings.target == STANDARD_RESOLUTIONS["VGA (640x480)"]
    assert settings.fit is Fit.FILL


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("manual_width_var", "abc", "whole numbers"),
        ("compress_level_var", "ten", "Compression level"),
        ("compress_level_var", "12", "Compression level"),
    ],
)
def test_invalid_input_yields_message_not_exception(app, field, value, expected):
    frame = app.settings_frame
    frame.manual_height_var.set("100")
    frame.manual_width_var.set("100")
    getattr(frame, field).set(value)
    assert app.current_settings() is None
    assert expected in app.settings_error
    assert expected in frame.validation_var.get()


def test_single_dimension_is_rejected(app):
    app.settings_frame.manual_width_var.set("100")
    assert app.current_settings() is None
    assert "both a width and a height" in app.settings_error


def test_core_validation_message_is_shown(app):
    app.settings_frame.manual_width_var.set("0")
    app.settings_frame.manual_height_var.set("10")
    assert app.current_settings() is None
    assert "between 1 and" in app.settings_error


def test_no_interlace_or_chunk_widgets(app):
    texts = all_widget_text(app.root)
    assert texts
    for text in texts:
        assert "interlace" not in text.lower()
        assert "chunk" not in text.lower()


def test_resampling_and_dither_choices_are_real_enums(app):
    assert set(settings_module.RESAMPLE_CHOICES) == {member.name for member in Resample}
    assert set(settings_module.DITHER_CHOICES) == {member.name for member in Dither}


def test_clamp_uses_loaded_image_size(app, tiff):
    app.input_path_var.set(str(tiff("rgb")))
    app.apply_paths()
    frame = app.settings_frame
    assert frame.input_image_size == (64, 48)
    frame.manual_width_var.set("5000")
    frame.manual_height_var.set("0")
    frame.clamp_and_notify()
    assert frame.manual_width_var.get() == "64"
    assert frame.manual_height_var.get() == "1"


def test_about_shows_version_without_google(app):
    texts = all_widget_text(app.settings_frame.about_tab)
    assert any(__version__ in text for text in texts)
    assert not any("google" in text.lower() for text in texts)


def test_log_uses_real_clock(app):
    first_line = app.settings_frame.log_text.get("1.0", "1.end")
    assert "00:00:00" not in first_line


def test_loading_requires_a_file_and_does_not_create_dirs(app, tiff, tmp_path, dialogs):
    path = tiff("rgb")
    app.input_path_var.set(str(tmp_path))
    app.apply_paths()
    assert app.source_image is None
    assert "showerror" not in dialogs

    app.input_path_var.set(str(path))
    app.apply_paths()
    assert app.source_image is not None
    assert app.output_path_var.get().endswith("rgb.png")
    assert not (path.parent / "PNG_Output").exists()


def test_typing_loads_only_after_debounce(app, tiff):
    app.input_path_var.set(str(tiff("rgb")))
    assert app.source_image is None
    deadline = time.monotonic() + 5
    while app.source_image is None and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.02)
    assert app.source_image is not None


def test_convert_single_file_matches_core_output(app, tiff, tmp_path, dialogs):
    path = tiff("rgb")
    destination = tmp_path / "out" / "result.png"
    frame = app.settings_frame
    frame.scale_var.set(50)
    frame.filter_var.set("BOX")
    frame.color_mode_var.set("P")
    frame.dither_var.set("FLOYDSTEINBERG")
    app.input_path_var.set(str(path))
    app.apply_paths()
    app.output_path_var.set(str(destination))

    app.convert_single_file()

    assert "showerror" not in dialogs
    assert "showinfo" in dialogs
    settings = app.current_settings()
    _index, image, _meta = next(load_pages(path, Pages.FIRST))
    expected = render(image, compute_geometry(image.size, settings), settings)
    with Image.open(destination) as written:
        assert written.size == (32, 24)
        assert written.mode == "P"
        assert written.convert("RGB").tobytes() == expected.convert("RGB").tobytes()


def test_convert_single_file_reports_failure(app, tiff, tmp_path, dialogs):
    app.input_path_var.set(str(tiff("rgb")))
    app.apply_paths()
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    app.output_path_var.set(str(blocker / "result.png"))
    app.convert_single_file()
    assert "Conversion failed" in dialogs["showerror"][0][1]


def test_convert_with_invalid_settings_shows_message(app, tiff, tmp_path, dialogs):
    app.input_path_var.set(str(tiff("rgb")))
    app.apply_paths()
    app.output_path_var.set(str(tmp_path / "x.png"))
    app.settings_frame.manual_width_var.set("abc")
    app.settings_frame.manual_height_var.set("5")
    app.convert_single_file()
    assert "whole numbers" in dialogs["showerror"][0][1]
    assert not (tmp_path / "x.png").exists()


def test_batch_uses_core_with_root_naming(app, tiff, tmp_path, dialogs):
    folder = tmp_path / "batch_in"
    folder.mkdir()
    shutil.copy(tiff("rgb"), folder / "a.TIF")
    shutil.copy(tiff("l"), folder / "b.tiff")
    app.mode_var.set("batch")
    app.on_mode_change()
    app.input_path_var.set(str(folder))
    app.apply_paths()
    out = tmp_path / "batch_out"
    app.output_path_var.set(str(out))
    app.convert_batch_files()
    assert "showerror" not in dialogs
    assert sorted(p.name for p in out.iterdir()) == ["Batch_01_01.png", "Batch_01_02.png"]
