import tkinter as tk
from tkinter import filedialog, messagebox

import pytest

from tiff2png.ui.app import TIFFtoPNGConverter


class WithdrawnTk(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.withdraw()


@pytest.fixture
def dialogs(monkeypatch):
    calls = {}

    def recorder(name):
        def record(*args, **kwargs):
            calls.setdefault(name, []).append(args)
        return record

    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(messagebox, name, recorder(name))
    for name in ("askopenfilename", "asksaveasfilename", "askdirectory"):
        monkeypatch.setattr(filedialog, name, lambda *a, **k: "")
    return calls


@pytest.fixture
def app(monkeypatch, dialogs):
    monkeypatch.setattr(tk, "Tk", WithdrawnTk)
    try:
        application = TIFFtoPNGConverter()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    application.root.update()
    yield application
    application.root.destroy()
