import threading

from PIL import Image

from tiff2png.core.geometry import Box
from tiff2png.core.jobs import Naming, plan_jobs
from tiff2png.core.runner import run_jobs
from tiff2png.core.settings import ConvertSettings, Fit, Pages


def test_cancel_after_first_job(tiff, tmp_path):
    out = tmp_path / "out"
    plan = plan_jobs([tiff("rgb"), tiff("l"), tiff("p")], out, Naming.ORIGINAL)
    cancel = threading.Event()
    seen = []

    def progress(done, total, job):
        seen.append((done, total))
        cancel.set()

    report = run_jobs(plan.jobs, ConvertSettings(), progress, cancel)
    assert report.cancelled
    assert len(report.done) == 1
    assert report.failed == []
    assert seen == [(1, 3)]
    assert sorted(p.name for p in out.iterdir()) == ["rgb.png"]
    assert not list(out.glob("*.tmp"))


def test_per_job_failure_does_not_stop_run(tiff, tmp_path):
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"nope")
    plan = plan_jobs([bad, tiff("rgb")], tmp_path / "out", Naming.ORIGINAL)
    report = run_jobs(plan.jobs, ConvertSettings())
    assert [job.src.name for job in report.done] == ["rgb.tif"]
    assert [f.job.src.name for f in report.failed] == ["bad.tif"]
    assert report.failed[0].message
    assert not report.cancelled


def test_multipage_pages_written(tiff, tmp_path):
    out = tmp_path / "out"
    settings = ConvertSettings(pages=Pages.ALL)
    plan = plan_jobs([tiff("multipage")], out, Naming.ORIGINAL, pages=Pages.ALL)
    report = run_jobs(plan.jobs, settings)
    assert len(report.done) == 3
    assert len(list(out.glob("*.png"))) == 3


def test_crop_box_only_applies_to_matching_size(tiff, tmp_path):
    settings = ConvertSettings(target=(16, 12), fit=Fit.FILL)
    plan = plan_jobs([tiff("quadrants")], tmp_path / "out", Naming.ORIGINAL)
    box = Box(32, 24, 64, 48)
    run_jobs(plan.jobs, settings, crop_box=box, crop_source_size=(10, 10))
    with Image.open(tmp_path / "out" / "quadrants.png") as image:
        mismatched = image.convert("RGB").getpixel((1, 1))
    run_jobs(plan.jobs, settings, crop_box=box, crop_source_size=(64, 48))
    with Image.open(tmp_path / "out" / "quadrants.png") as image:
        matched = image.convert("RGB").getpixel((1, 1))
    assert mismatched != matched
