import os
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image

from tiff2png.core.settings import Pages

TIFF_SUFFIXES = frozenset({".tif", ".tiff"})
DEFAULT_ROOT = "Batch"


class Naming(Enum):
    ROOT_NN = "root"
    ORIGINAL = "original"


@dataclass(frozen=True)
class Job:
    src: Path
    page: int
    dst: Path


@dataclass(frozen=True)
class Plan:
    jobs: tuple[Job, ...]
    existing: tuple[Job, ...]
    collisions: tuple[tuple[Job, ...], ...]


def find_tiffs(folder: str | os.PathLike) -> list[Path]:
    return sorted(
        (
            entry
            for entry in Path(folder).iterdir()
            if entry.is_file() and entry.suffix.lower() in TIFF_SUFFIXES
        ),
        key=lambda entry: entry.name.lower(),
    )


def count_pages(path: Path) -> int:
    try:
        with Image.open(path) as source:
            return getattr(source, "n_frames", 1)
    except OSError:
        return 1


def plan_jobs(
    inputs: Sequence[str | os.PathLike],
    out: str | os.PathLike,
    naming: Naming = Naming.ROOT_NN,
    root: str = DEFAULT_ROOT,
    pages: Pages = Pages.FIRST,
) -> Plan:
    out_dir = Path(out)
    jobs: list[Job] = []
    for number, entry in enumerate(inputs, start=1):
        src = Path(entry)
        base = f"{root}_{number:02d}" if naming is Naming.ROOT_NN else src.stem
        page_count = count_pages(src) if pages is Pages.ALL else 1
        for page in range(page_count):
            suffix = f"_p{page + 1:02d}" if page_count > 1 else ""
            jobs.append(Job(src, page, out_dir / f"{base}{suffix}.png"))
    by_name: dict[str, list[Job]] = defaultdict(list)
    for job in jobs:
        by_name[job.dst.name.lower()].append(job)
    collisions = tuple(tuple(group) for group in by_name.values() if len(group) > 1)
    existing = tuple(job for job in jobs if job.dst.exists())
    return Plan(tuple(jobs), existing, collisions)
