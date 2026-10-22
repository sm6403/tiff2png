import shutil
import threading
import time
from tkinter import messagebox

import pytest
from PIL import Image

from tiff2png.core import runner as runner_module
from tiff2png.ui import app as app_module

GOOD = ("rgb", "l", "rgba", "quadrants")
TIMEOUT = 10


def pump_until(app, condition, timeout=TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.root.update()
        if condition():
            return
        time.sleep(0.01)
    pytest.fail("timed out waiting for condition")


def wait_idle(app):
    pump_until(app, lambda: app._worker is None)


def make_batch(tmp_path, tiff, names=GOOD, corrupt=True, copies=None):
    folder = tmp_path / "batch_in"
    folder.mkdir()
    for name in names:
        shutil.copy(tiff(name), folder / f"{name}.tif")
    if corrupt:
        (folder / "broken.tif").write_bytes(b"this is not a tiff")
    for name, count in (copies or {}).items():
        for index in range(count):
            shutil.copy(tiff(name), folder / f"{name}_{index}.tif")
    return folder


def open_batch(app, folder, out):
    app.mode_var.set("batch")
    app.on_mode_change()
    app.input_path_var.set(str(folder))
    app.output_path_var.set(str(out))
    app.apply_paths()
    app.root.update()


def outputs(out):
    return sorted(path.name for path in out.glob("*.png"))


@pytest.fixture
def answers(monkeypatch):
    given = {"calls": []}

    def ask(title, message, **kwargs):
        given["calls"].append(message)
        return given["answer"]

    given["answer"] = True
    monkeypatch.setattr(messagebox, "askyesnocancel", ask)
    return given


def test_batch_converts_good_files_and_reports_corrupt_off_main_thread(
        app, tiff, tmp_path, dialogs, monkeypatch):
    threads = []
    real_run_jobs = app_module.run_jobs

    def spy(*args, **kwargs):
        threads.append(threading.current_thread())
        return real_run_jobs(*args, **kwargs)

    monkeypatch.setattr(app_module, "run_jobs", spy)
    out = tmp_path / "out"
    open_batch(app, make_batch(tmp_path, tiff), out)

    app.start_conversion()
    wait_idle(app)

    assert len(outputs(out)) == 4
    summary = dialogs["showwarning"][-1][1]
    assert "broken.tif" in summary
    assert "showinfo" not in dialogs
    assert threads and all(thread is not threading.main_thread() for thread in threads)
    assert app.status_var.get() == "Batch conversion complete"
    assert str(app.convert_button.cget("state")) == "normal"
    assert str(app.cancel_button.cget("state")) == "disabled"


def test_cancel_stops_remaining_jobs_and_sets_cancelled_status(
        app, tiff, tmp_path, dialogs, monkeypatch):
    real_render = runner_module.render
    release = threading.Event()
    calls = []

    def blocking_render(*args, **kwargs):
        calls.append(1)
        if len(calls) > 1:
            assert release.wait(TIMEOUT)
        return real_render(*args, **kwargs)

    monkeypatch.setattr(runner_module, "render", blocking_render)
    out = tmp_path / "out"
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False, copies={"rgb": 1}), out)
    assert len(app.batch_preview_frame.get_selected_files()) == 5

    app.start_conversion()
    pump_until(app, lambda: len(calls) > 1)
    pump_until(app, lambda: "(1/5)" in app.status_var.get())
    app.cancel_batch()
    assert app.status_var.get() == "Cancelling..."
    release.set()
    wait_idle(app)

    assert len(outputs(out)) < 5
    assert app.status_var.get().startswith("Cancelled")
    assert "showinfo" not in dialogs


def test_controls_are_locked_during_run_and_restored_after(app, tiff, tmp_path, monkeypatch):
    real_render = runner_module.render
    release = threading.Event()
    started = threading.Event()

    def blocking_render(*args, **kwargs):
        started.set()
        assert release.wait(TIMEOUT)
        return real_render(*args, **kwargs)

    monkeypatch.setattr(runner_module, "render", blocking_render)
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), tmp_path / "out")
    before = {widget: str(widget.cget("state")) for widget in app._lockable_widgets()}
    assert "readonly" in before.values()

    app.start_conversion()
    pump_until(app, started.is_set)
    assert all(str(widget.cget("state")) == "disabled" for widget in before)
    assert str(app.cancel_button.cget("state")) == "normal"
    app.start_conversion()
    assert app._worker is not None

    release.set()
    wait_idle(app)
    assert {widget: str(widget.cget("state")) for widget in before} == before


def test_overwrite_no_keeps_existing_output_byte_identical(app, tiff, tmp_path, answers):
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "Batch_01_01.png"
    existing.write_bytes(b"precious")
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), out)
    answers["answer"] = False

    app.start_conversion()
    wait_idle(app)

    assert existing.read_bytes() == b"precious"
    assert outputs(out) == ["Batch_01_01.png", "Batch_01_02.png", "Batch_01_03.png", "Batch_01_04.png"]
    assert len(answers["calls"]) == 1


def test_overwrite_yes_replaces_existing_output(app, tiff, tmp_path, answers):
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "Batch_01_01.png"
    existing.write_bytes(b"precious")
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), out)

    app.start_conversion()
    wait_idle(app)

    with Image.open(existing) as image:
        assert image.format == "PNG"


def test_overwrite_cancel_aborts_without_writing(app, tiff, tmp_path, answers):
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "Batch_01_01.png"
    existing.write_bytes(b"precious")
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), out)
    answers["answer"] = None

    app.start_conversion()

    assert app._worker is None
    assert existing.read_bytes() == b"precious"
    assert outputs(out) == ["Batch_01_01.png"]


def test_original_names_option(app, tiff, tmp_path, dialogs):
    out = tmp_path / "out"
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), out)
    app.naming_var.set("Keep original filenames")
    app.on_naming_change()
    assert str(app.batch_root_entry.cget("state")) == "disabled"

    app.start_conversion()
    wait_idle(app)

    assert outputs(out) == sorted(f"{name}.png" for name in GOOD)


def test_collisions_show_error_and_do_not_start(app, tiff, tmp_path, dialogs):
    folder = make_batch(tmp_path, tiff, names=("rgb",), corrupt=False)
    (folder / "RGB.TIFF").write_bytes(tiff("rgb").read_bytes())
    out = tmp_path / "out"
    open_batch(app, folder, out)
    app.naming_var.set("Keep original filenames")
    app.on_naming_change()

    app.start_conversion()

    assert app._worker is None
    assert "showerror" in dialogs
    assert not out.exists()


def test_export_all_pages_writes_each_page(app, tiff, tmp_path, dialogs):
    out = tmp_path / "out"
    open_batch(app, make_batch(tmp_path, tiff, names=("multipage", "rgb"), corrupt=False), out)
    app.all_pages_var.set(True)

    app.start_conversion()
    wait_idle(app)

    assert outputs(out) == ["Batch_01_01_p01.png", "Batch_01_01_p02.png", "Batch_01_01_p03.png",
                            "Batch_01_02.png"]


def test_batch_passes_crop_box_with_source_size(app, tiff, tmp_path, dialogs, monkeypatch):
    captured = {}

    def spy(jobs, settings, progress_cb=None, cancel_event=None, crop_box=None, crop_source_size=None):
        captured["size"] = crop_source_size
        return runner_module.Report()

    monkeypatch.setattr(app_module, "run_jobs", spy)
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), tmp_path / "out")

    app.start_conversion()
    wait_idle(app)

    assert captured["size"] == app.proxy.source_size


def start_blocked_batch(app, tiff, tmp_path, monkeypatch):
    real_render = runner_module.render
    started = threading.Event()
    release = threading.Event()

    def blocking_render(*args, **kwargs):
        started.set()
        release.wait(TIMEOUT)
        return real_render(*args, **kwargs)

    monkeypatch.setattr(runner_module, "render", blocking_render)
    out = tmp_path / "out"
    open_batch(app, make_batch(tmp_path, tiff, corrupt=False), out)
    app.start_conversion()
    pump_until(app, started.is_set)
    return out, release


def test_closing_during_run_cancels_without_blocking_and_destroys_when_job_ends(
    app, tiff, tmp_path, dialogs, monkeypatch
):
    out, release = start_blocked_batch(app, tiff, tmp_path, monkeypatch)
    cancel = app._cancel_event
    destroyed = threading.Event()
    real_destroy = app.root.destroy

    def destroy():
        if destroyed.is_set():
            return
        destroyed.set()
        real_destroy()

    monkeypatch.setattr(app.root, "destroy", destroy)
    start = time.monotonic()
    app.on_close()
    assert time.monotonic() - start < 0.5
    assert cancel.is_set()
    assert app.status_var.get() == "Cancelling..."
    assert not destroyed.is_set()

    longest = 0.0
    for _ in range(10):
        tick = time.monotonic()
        app.root.update()
        longest = max(longest, time.monotonic() - tick)
        time.sleep(0.02)
    assert longest < 0.5
    assert not destroyed.is_set()

    release.set()
    pump_until(app, destroyed.is_set)
    assert not list(out.glob("*.tmp"))
    assert dialogs == {}


def test_closing_with_no_run_destroys_immediately(app, monkeypatch):
    destroyed = []
    real_destroy = app.root.destroy
    monkeypatch.setattr(app.root, "destroy", lambda: destroyed.append(True))
    app.on_close()
    assert destroyed == [True]
    real_destroy()


def test_batch_thumbnails_render_for_sixteen_bit_and_lab(app, tiff, tmp_path):
    folder = tmp_path / "thumbs"
    folder.mkdir()
    for name in ("i16", "lab", "f_unit"):
        shutil.copy(tiff(name), folder / f"{name}.tif")
    open_batch(app, folder, tmp_path / "out")
    frame = app.batch_preview_frame
    assert len(frame.preview_images) == 3
    texts = [
        label.cget("text")
        for holder in frame.grid_frame.winfo_children()
        for canvas in holder.winfo_children()
        if canvas.winfo_class() == "Canvas"
        for label in canvas.winfo_children()
        if label.winfo_class() == "TLabel"
    ]
    assert not any("Error loading preview" in text for text in texts)
