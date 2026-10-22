import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from tiff2png.core.geometry import Box, compute_geometry
from tiff2png.core.imaging import load_pages, render, save_png
from tiff2png.core.jobs import Job
from tiff2png.core.settings import ConvertSettings, Pages

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, Job], None]


@dataclass(frozen=True)
class Failure:
    job: Job
    message: str


@dataclass
class Report:
    done: list[Job] = field(default_factory=list)
    failed: list[Failure] = field(default_factory=list)
    cancelled: bool = False


def _group_by_source(jobs: Sequence[Job]) -> list[list[Job]]:
    groups: list[list[Job]] = []
    for job in jobs:
        if groups and groups[-1][0].src == job.src:
            groups[-1].append(job)
        else:
            groups.append([job])
    return groups


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def run_jobs(
    jobs: Sequence[Job],
    settings: ConvertSettings,
    progress_cb: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    crop_box: Box | None = None,
    crop_source_size: tuple[int, int] | None = None,
) -> Report:
    report = Report()
    total = len(jobs)
    finished = 0

    def cancelled() -> bool:
        if cancel_event is not None and cancel_event.is_set():
            report.cancelled = True
        return report.cancelled

    def finish(job: Job, failure: Failure | None) -> None:
        nonlocal finished
        finished += 1
        if failure is None:
            report.done.append(job)
        else:
            report.failed.append(failure)
        if progress_cb is not None:
            progress_cb(finished, total, job)

    for group in _group_by_source(jobs):
        if cancelled():
            break
        pending = list(group)
        pages = Pages.ALL if any(job.page > 0 for job in group) else Pages.FIRST
        try:
            for index, image, meta in load_pages(group[0].src, pages):
                if not pending:
                    break
                if index != pending[0].page:
                    continue
                if cancelled():
                    break
                job = pending.pop(0)
                try:
                    box = crop_box
                    if crop_source_size is not None and image.size != crop_source_size:
                        box = None
                    geometry = compute_geometry(image.size, settings, box)
                    output = render(image, geometry, settings)
                    if cancelled():
                        break
                    job.dst.parent.mkdir(parents=True, exist_ok=True)
                    save_png(output, job.dst, settings, meta)
                except Exception as error:
                    logger.exception("Failed to convert %s page %d", job.src, job.page)
                    finish(job, Failure(job, _describe(error)))
                else:
                    finish(job, None)
        except Exception as error:
            logger.exception("Failed to read %s", group[0].src)
            for job in pending:
                finish(job, Failure(job, _describe(error)))
            pending = []
        if report.cancelled:
            break
        for job in pending:
            finish(job, Failure(job, "Page not found in file"))
    return report
