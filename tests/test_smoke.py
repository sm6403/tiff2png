import tkinter as tk

import pytest

from tiff2png.ui.app import TIFFtoPNGConverter


class WithdrawnTk(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.withdraw()


def test_app_constructs_and_destroys(monkeypatch):
    monkeypatch.setattr(tk, "Tk", WithdrawnTk)
    try:
        app = TIFFtoPNGConverter()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    try:
        app.root.update()
        assert app.root.state() == "withdrawn"
    finally:
        app.root.destroy()
