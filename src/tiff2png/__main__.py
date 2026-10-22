import ctypes
import os
import sys
import tempfile
import tkinter as tk
from importlib import resources
from pathlib import Path

from PIL import Image

from tiff2png.cli import main as cli_main
from tiff2png.core.jobs import Job
from tiff2png.core.runner import run_jobs
from tiff2png.core.settings import ConvertSettings
from tiff2png.ui.app import main as gui_main

SELF_TEST_FLAG = "--self-test"
ATTACH_PARENT_PROCESS = -1


def _attach_console() -> None:
    """A windowed frozen exe has no stdio; reattach to the launching console for CLI use."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    if os.name == "nt" and ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        sys.stdout = open("CONOUT$", "w")
        sys.stderr = open("CONOUT$", "w")
    else:
        sys.stdout = sys.stdout or open(os.devnull, "w")
        sys.stderr = sys.stderr or open(os.devnull, "w")


def self_test(out_path: str) -> int:
    root = tk.Tk()
    root.withdraw()
    try:
        with resources.as_file(resources.files("tiff2png.ui") / "assets" / "T2P.ico") as icon_path:
            root.iconbitmap(str(icon_path))
    finally:
        root.destroy()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "selftest.tif"
        Image.new("CMYK", (64, 48), (200, 60, 0, 20)).save(src)
        dst = Path(out_path)
        report = run_jobs([Job(src, 0, dst)], ConvertSettings())
    if report.failed:
        print(f"self-test failed: {report.failed[0].message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        _attach_console()
    if args[:1] == [SELF_TEST_FLAG]:
        if len(args) != 2:
            print(f"usage: {SELF_TEST_FLAG} OUT.png", file=sys.stderr)
            sys.exit(2)
        sys.exit(self_test(args[1]))
    if args:
        sys.exit(cli_main())
    gui_main()
