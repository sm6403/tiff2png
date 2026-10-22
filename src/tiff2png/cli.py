import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from tiff2png.core.geometry import Box
from tiff2png.core.jobs import DEFAULT_ROOT, Naming, find_tiffs, plan_jobs
from tiff2png.core.runner import run_jobs
from tiff2png.core.settings import (
    ColourMode,
    ConvertSettings,
    Dither,
    Fit,
    Pages,
    Resample,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

DEFAULT_COMPRESS_LEVEL = 9
DITHER_NAMES = {"none": Dither.NONE, "fs": Dither.FLOYDSTEINBERG}


class UsageError(Exception):
    pass


def _size(text: str) -> tuple[int, int]:
    try:
        width, height = text.lower().split("x")
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WxH, got {text!r}") from None


def _crop(text: str) -> Box:
    try:
        left, top, right, bottom = (float(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected L,T,R,B, got {text!r}") from None
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("crop box must have right > left and bottom > top")
    return Box(left, top, right, bottom)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiff2png",
        description=(
            "Convert TIFF images to PNG. INPUT is one or more files, or a single folder. "
            "A single file is written as <stem>.png; folders and several files are "
            "written as <root>_NN.png."
        ),
    )
    parser.add_argument("inputs", nargs="+", metavar="INPUT")
    parser.add_argument(
        "-o", "--output", metavar="OUT",
        help=(
            "output folder (default: the folder of the first input); with a single file "
            "input, a name ending in .png is written as exactly that file"
        ),
    )
    parser.add_argument(
        "--scale", type=float, default=100.0, metavar="PCT",
        help="scale percentage, 1 to 100 (default 100)",
    )
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--fit", type=_size, metavar="WxH", help="fit within WxH, never upscaling")
    size.add_argument("--fill", type=_size, metavar="WxH", help="fill exactly WxH, cropping the excess")
    parser.add_argument(
        "--crop", type=_crop, metavar="L,T,R,B",
        help="crop box in source pixels, used with --fill",
    )
    parser.add_argument(
        "--resample", default=Resample.LANCZOS.name.lower(),
        choices=[member.name.lower() for member in Resample],
        type=str.lower, help="resampling filter (default lanczos)",
    )
    parser.add_argument(
        "--colour", default="auto", choices=[member.value for member in ColourMode],
        type=str.lower, help="output colour mode (default auto)",
    )
    parser.add_argument(
        "--dither", default="fs", choices=list(DITHER_NAMES), type=str.lower,
        help="dithering for palette output (default fs)",
    )
    parser.add_argument("--no-optimize", action="store_true", help="skip PNG optimisation")
    parser.add_argument(
        "--compress-level", type=int, default=None, metavar="N",
        help=(
            "PNG compression level 0 to 9; setting it turns optimisation off, because "
            "optimisation always uses level 9 (default: optimise, level 9)"
        ),
    )
    parser.add_argument("--all-pages", action="store_true", help="export every page of multi-page TIFFs")
    parser.add_argument(
        "--naming", default=None, choices=[member.value for member in Naming],
        type=str.lower,
        help=(
            "root: <root>_NN.png, original: <stem>.png "
            "(default: original for a single file, root for folders and several files)"
        ),
    )
    parser.add_argument("--root", default=DEFAULT_ROOT, metavar="NAME", help="root name for --naming root")
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    return parser


def _settings(args: argparse.Namespace) -> ConvertSettings:
    if args.crop is not None and args.fill is None:
        raise UsageError("--crop requires --fill")
    target = args.fill or args.fit
    fit = Fit.FILL if args.fill else Fit.FIT
    try:
        return ConvertSettings(
            scale=args.scale / 100.0,
            target=target,
            fit=fit,
            resample=Resample[args.resample.upper()],
            colour=ColourMode(args.colour),
            dither=DITHER_NAMES[args.dither],
            optimize=not args.no_optimize and args.compress_level is None,
            compress_level=DEFAULT_COMPRESS_LEVEL if args.compress_level is None else args.compress_level,
            pages=Pages.ALL if args.all_pages else Pages.FIRST,
        )
    except ValueError as error:
        raise UsageError(str(error)) from None


def _resolve_inputs(raw: Sequence[str]) -> list[Path]:
    paths = [Path(item) for item in raw]
    for path in paths:
        if not path.exists():
            raise UsageError(f"no such file or folder: {path}")
    folders = [path for path in paths if path.is_dir()]
    if folders:
        if len(paths) > 1:
            raise UsageError("give either files or a single folder, not a mix")
        found = find_tiffs(folders[0])
        if not found:
            raise UsageError(f"no TIFF files in {folders[0]}")
        return found
    return paths


def _run(args: argparse.Namespace) -> int:
    settings = _settings(args)
    inputs = _resolve_inputs(args.inputs)
    single_file = len(args.inputs) == 1 and not Path(args.inputs[0]).is_dir()
    if args.naming is not None:
        naming = Naming(args.naming)
    else:
        naming = Naming.ORIGINAL if single_file else Naming.ROOT_NN
    out_dir = Path(args.output) if args.output else inputs[0].parent
    dst_file = None
    if single_file and args.output and out_dir.suffix.lower() == ".png" and not out_dir.is_dir():
        dst_file = out_dir
        out_dir = dst_file.parent
    try:
        plan = plan_jobs(inputs, out_dir, naming, args.root, settings.pages, dst_file)
    except ValueError as error:
        raise UsageError(str(error)) from None
    if plan.collisions:
        names = ", ".join(sorted({group[0].dst.name for group in plan.collisions}))
        raise UsageError(f"output names collide: {names}")
    if plan.existing and not args.overwrite:
        names = ", ".join(job.dst.name for job in plan.existing)
        raise UsageError(f"output exists (use --overwrite): {names}")
    report = run_jobs(plan.jobs, settings, crop_box=args.crop)
    if report.failed:
        print(
            f"{len(report.done)} converted, {len(report.failed)} failed:",
            file=sys.stderr,
        )
        for failure in report.failed:
            print(f"  {failure.job.src}: {failure.message}", file=sys.stderr)
        return EXIT_FAILED
    print(f"{len(report.done)} converted")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.CRITICAL)
    logging.captureWarnings(True)
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except UsageError as error:
        print(f"tiff2png: error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
