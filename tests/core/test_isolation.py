import subprocess
import sys

IMPORT_ALL_CORE = (
    "import importlib, pkgutil, sys\n"
    "import tiff2png.core as core\n"
    "for module in pkgutil.iter_modules(core.__path__, 'tiff2png.core.'):\n"
    "    importlib.import_module(module.name)\n"
    "assert 'tkinter' not in sys.modules, 'core imported tkinter'\n"
)


def test_core_does_not_import_tkinter():
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_ALL_CORE],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
