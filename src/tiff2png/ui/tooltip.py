import tkinter as tk
from tkinter import ttk

TOOLTIP_OFFSET = 10


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def show(self, event):
        if self.window is not None:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{event.x_root + TOOLTIP_OFFSET}+{event.y_root + TOOLTIP_OFFSET}")
        ttk.Label(
            self.window, text=self.text, justify=tk.LEFT,
            background="#ffffe0", foreground="#000000",
            relief=tk.SOLID, borderwidth=1, padding=(5, 2),
        ).pack()

    def hide(self, event=None):
        if self.window is not None:
            self.window.destroy()
            self.window = None
