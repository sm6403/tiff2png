import logging
import tkinter as tk
from datetime import datetime
from importlib import resources
from tkinter import ttk

from PIL import Image, ImageTk

from tiff2png import __version__
from tiff2png.core.settings import (
    STANDARD_RESOLUTIONS,
    ColourMode,
    ConvertSettings,
    Dither,
    Fit,
    Resample,
)
from tiff2png.ui.tooltip import Tooltip

CUSTOM = "Custom"
COLOUR_CHOICES = ("auto", "RGB", "RGBA", "L", "P")
DITHER_CHOICES = tuple(member.name for member in Dither)
RESAMPLE_CHOICES = tuple(member.name for member in Resample)
FIT_LABEL = "Fit within (keep aspect, never upscale)"
FILL_LABEL = "Fill (crop to exact size)"
FIT_CHOICES = {FIT_LABEL: Fit.FIT, FILL_LABEL: Fit.FILL}
DEFAULT_COMPRESS_LEVEL = 9
OPTIMIZE_COMPRESS_LEVEL = 9
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class SettingsFrame(ttk.Frame):
    def __init__(self, parent, on_settings_change=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.on_settings_change = on_settings_change
        self.standard_resolutions = STANDARD_RESOLUTIONS
        self.input_image_size = None

        self.settings_notebook = ttk.Notebook(self)
        self.settings_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E))

        self.basic_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.basic_tab, text="Basic")
        self.advanced_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.advanced_tab, text="Advanced")
        self.logs_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.logs_tab, text="Logs")
        self.about_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.about_tab, text="About")
        self.init_about_tab()

        self.create_variables()
        self.validation_var = tk.StringVar()
        ttk.Label(self, textvariable=self.validation_var, foreground="#c42b1c",
                  wraplength=320, justify=tk.LEFT).grid(row=1, column=0, sticky=tk.W)

        self.init_basic_settings()
        self.init_advanced_settings()
        self.init_logs_tab()
        self.setup_logging()
        self.bind("<Destroy>", self._on_destroy)

    def setup_logging(self):
        self.logger = logging.getLogger('TIFFtoPNG')
        self.logger.setLevel(logging.DEBUG)
        self.console_handler = ConsoleHandler(self.log_text)
        self.console_handler.setLevel(logging.DEBUG)
        self.console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(self.console_handler)

    def _on_destroy(self, event):
        if event.widget is self:
            self.logger.removeHandler(self.console_handler)
            self.console_handler.cancel_pending()

    def init_logs_tab(self):
        self.log_text = tk.Text(self.logs_tab, wrap=tk.WORD, width=50, height=15)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar = ttk.Scrollbar(self.logs_tab, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.logs_tab.grid_columnconfigure(0, weight=1)
        self.logs_tab.grid_rowconfigure(0, weight=1)
        clear_button = ttk.Button(self.logs_tab, text="Clear Logs", command=self.clear_logs)
        clear_button.grid(row=1, column=0, columnspan=2, pady=5)
        self.log_text.insert(tk.END, f"Log started at {datetime.now().strftime(LOG_TIME_FORMAT)}\n")
        self.log_text.configure(state='disabled')

    def clear_logs(self):
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, f"Log cleared at {datetime.now().strftime(LOG_TIME_FORMAT)}\n")
        self.log_text.configure(state='disabled')

    def create_variables(self):
        self.scale_var = tk.DoubleVar(value=100)
        self.resolution_var = tk.StringVar(value=CUSTOM)
        self.fit_var = tk.StringVar(value=FIT_LABEL)
        self.optimize_var = tk.BooleanVar(value=True)

        self.color_mode_var = tk.StringVar(value=COLOUR_CHOICES[0])
        self.dither_var = tk.StringVar(value=Dither.FLOYDSTEINBERG.name)
        self.filter_var = tk.StringVar(value=Resample.LANCZOS.name)
        self.compress_level_var = tk.StringVar(value=str(DEFAULT_COMPRESS_LEVEL))
        self._level_before_optimize = str(DEFAULT_COMPRESS_LEVEL)
        self.manual_width_var = tk.StringVar(value="")
        self.manual_height_var = tk.StringVar(value="")

    def notify_change(self, *args):
        if self.on_settings_change:
            self.on_settings_change()

    def set_input_image_size(self, size):
        self.input_image_size = size

    def read_settings(self):
        """Return (ConvertSettings, None) or (None, validation message)."""
        try:
            target = self._read_target()
            try:
                compress_level = int(self.compress_level_var.get().strip())
            except ValueError:
                raise ValueError("Compression level must be a whole number from 0 to 9") from None
            settings = ConvertSettings(
                scale=round(self.scale_var.get()) / 100,
                target=target,
                fit=FIT_CHOICES[self.fit_var.get()],
                resample=Resample[self.filter_var.get()],
                colour=self._read_colour(),
                dither=Dither[self.dither_var.get()],
                optimize=self.optimize_var.get(),
                compress_level=compress_level,
            )
        except (ValueError, KeyError, tk.TclError) as error:
            message = str(error)
            self.validation_var.set(message)
            return None, message
        self.validation_var.set("")
        return settings, None

    def _read_colour(self):
        choice = self.color_mode_var.get()
        return ColourMode.AUTO if choice == "auto" else ColourMode[choice]

    def _read_target(self):
        width_text = self.manual_width_var.get().strip()
        height_text = self.manual_height_var.get().strip()
        if width_text or height_text:
            if not (width_text and height_text):
                raise ValueError("Enter both a width and a height, or leave both empty")
            try:
                return int(width_text), int(height_text)
            except ValueError:
                raise ValueError("Width and height must be whole numbers") from None
        return self.standard_resolutions.get(self.resolution_var.get())

    def init_basic_settings(self):
        ttk.Label(self.basic_tab, text="Resolution Scale:").grid(row=0, column=0, sticky=tk.W, pady=5)
        scale_scale = ttk.Scale(self.basic_tab, from_=10, to=100, orient=tk.HORIZONTAL,
                                variable=self.scale_var)
        scale_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        scale_scale.bind('<ButtonRelease-1>', lambda e: self.notify_change())
        self.scale_percent_var = tk.StringVar()

        def update_scale_label(*args):
            self.scale_percent_var.set(f"{round(self.scale_var.get())}%")
        self.scale_var.trace_add('write', update_scale_label)
        update_scale_label()
        ttk.Label(self.basic_tab, textvariable=self.scale_percent_var).grid(row=0, column=3, padx=5)
        ttk.Label(self.basic_tab, text="(10-100%)").grid(row=0, column=2, padx=5)

        ttk.Label(self.basic_tab, text="Standard Resolution:").grid(row=1, column=0, sticky=tk.W, pady=5)
        resolution_combo = ttk.Combobox(self.basic_tab, textvariable=self.resolution_var,
                                        values=list(self.standard_resolutions.keys()),
                                        state="readonly")
        resolution_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        resolution_combo.bind('<<ComboboxSelected>>', self.on_resolution_selected)

        optimize_check = ttk.Checkbutton(
            self.basic_tab,
            text="Optimize PNG (Reduces file size by analyzing and optimizing the image data)",
            variable=self.optimize_var, command=self.on_optimize_toggle)
        optimize_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        Tooltip(resolution_combo,
                "Select a standard resolution.\n"
                "Use the Fit/Fill choice in the Advanced tab to decide whether\n"
                "the image is fitted inside it or cropped to fill it exactly.")
        Tooltip(optimize_check,
                "When enabled, the encoder tries several filters for the smallest\n"
                "PNG. Slower to save, with no quality loss.")

    def on_optimize_toggle(self):
        self._sync_compress_level()
        self.notify_change()

    def _sync_compress_level(self):
        if self.optimize_var.get():
            if str(self.compress_spin.cget("state")) != "disabled":
                self._level_before_optimize = self.compress_level_var.get()
            self.compress_level_var.set(str(OPTIMIZE_COMPRESS_LEVEL))
            self.compress_spin.configure(state="disabled")
        else:
            self.compress_level_var.set(self._level_before_optimize)
            self.compress_spin.configure(state="normal")

    def on_resolution_selected(self, event=None):
        resolution = self.standard_resolutions.get(self.resolution_var.get())
        if resolution:
            self.fit_var.set(FILL_LABEL)
            self.manual_width_var.set(str(resolution[0]))
            self.manual_height_var.set(str(resolution[1]))
        else:
            self.manual_width_var.set("")
            self.manual_height_var.set("")
        self.notify_change()

    def init_advanced_settings(self):
        color_frame = ttk.LabelFrame(self.advanced_tab, text="Color Settings", padding="5")
        color_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(color_frame, text="Color Mode:").grid(row=0, column=0, sticky=tk.W, pady=2)
        color_mode_combo = ttk.Combobox(color_frame, textvariable=self.color_mode_var,
                                        values=list(COLOUR_CHOICES), state="readonly", width=10)
        color_mode_combo.grid(row=0, column=1, padx=5, pady=2)
        color_mode_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())

        ttk.Label(color_frame, text="Dithering:").grid(row=1, column=0, sticky=tk.W, pady=2)
        dither_combo = ttk.Combobox(color_frame, textvariable=self.dither_var,
                                    values=list(DITHER_CHOICES), state="readonly", width=15)
        dither_combo.grid(row=1, column=1, padx=5, pady=2)
        dither_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())

        comp_frame = ttk.LabelFrame(self.advanced_tab, text="Resampling and Compression", padding="5")
        comp_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(comp_frame, text="Resampling:").grid(row=0, column=0, sticky=tk.W, pady=2)
        filter_combo = ttk.Combobox(comp_frame, textvariable=self.filter_var,
                                    values=list(RESAMPLE_CHOICES), state="readonly", width=10)
        filter_combo.grid(row=0, column=1, padx=5, pady=2)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())

        ttk.Label(comp_frame, text="Compression Level:").grid(row=1, column=0, sticky=tk.W, pady=2)
        compress_spin = ttk.Spinbox(comp_frame, textvariable=self.compress_level_var,
                                    from_=0, to=9, width=4, command=self.notify_change)
        compress_spin.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        compress_spin.bind('<Return>', self.notify_change)
        compress_spin.bind('<FocusOut>', self.notify_change)
        self.compress_spin = compress_spin
        self._sync_compress_level()

        manual_res_frame = ttk.LabelFrame(self.advanced_tab, text="Manual Output Resolution", padding="5")
        manual_res_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        ttk.Label(manual_res_frame, text="Width:").grid(row=0, column=0, sticky=tk.W, padx=5)
        width_entry = ttk.Entry(manual_res_frame, textvariable=self.manual_width_var, width=8)
        width_entry.grid(row=0, column=1, padx=5)
        ttk.Label(manual_res_frame, text="px").grid(row=0, column=2, sticky=tk.W)
        ttk.Label(manual_res_frame, text="Height:").grid(row=0, column=3, sticky=tk.W, padx=5)
        height_entry = ttk.Entry(manual_res_frame, textvariable=self.manual_height_var, width=8)
        height_entry.grid(row=0, column=4, padx=5)
        ttk.Label(manual_res_frame, text="px").grid(row=0, column=5, sticky=tk.W)
        fit_combo = ttk.Combobox(manual_res_frame, textvariable=self.fit_var,
                                 values=list(FIT_CHOICES), state="readonly", width=36)
        fit_combo.grid(row=1, column=0, columnspan=6, sticky=tk.W, pady=5, padx=5)
        fit_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())
        Tooltip(fit_combo,
                "Fit: the image is scaled to fit inside the resolution, keeping its\n"
                "aspect ratio, and is never made larger than the scale % allows.\n"
                "Fill: the image is cropped to exactly the resolution.")
        Tooltip(width_entry, "Output width in pixels. Leave both empty to use the standard resolution.")
        Tooltip(height_entry, "Output height in pixels. Leave both empty to use the standard resolution.")
        for entry in (width_entry, height_entry):
            entry.bind('<FocusOut>', self.clamp_and_notify)
            entry.bind('<Return>', self.clamp_and_notify)

        ttk.Button(self.advanced_tab, text="Reset to Defaults",
                   command=self.reset_advanced_settings).grid(row=4, column=0, columnspan=2, pady=10)

        Tooltip(color_mode_combo,
                "Color mode for output PNG:\nauto: keep the source colour mode\nRGB: Full color (24-bit)\n"
                "RGBA: Full color with transparency\nL: Grayscale\nP: Palette mode (8-bit)")
        Tooltip(dither_combo,
                "Dithering used when reducing to palette mode:\nNONE: No dithering\n"
                "FLOYDSTEINBERG: Error diffusion dithering\n"
                "Has no effect on sources with transparency.")
        Tooltip(filter_combo,
                "Resampling filter used when resizing:\nNEAREST is fastest, LANCZOS is sharpest.")
        Tooltip(compress_spin,
                "PNG compression level, 0 (fastest, biggest) to 9 (slowest, smallest).\n"
                "Lossless at every level.")

    def clamp_and_notify(self, event=None):
        for var, axis in ((self.manual_width_var, 0), (self.manual_height_var, 1)):
            text = var.get().strip()
            if not text:
                continue
            try:
                value = int(text)
            except ValueError:
                continue
            value = max(1, value)
            if self.input_image_size is not None:
                value = min(value, self.input_image_size[axis])
            var.set(str(value))
        self.notify_change()

    def reset_advanced_settings(self):
        self.color_mode_var.set(COLOUR_CHOICES[0])
        self.dither_var.set(Dither.FLOYDSTEINBERG.name)
        self.filter_var.set(Resample.LANCZOS.name)
        self._level_before_optimize = str(DEFAULT_COMPRESS_LEVEL)
        if not self.optimize_var.get():
            self.compress_level_var.set(self._level_before_optimize)
        self.fit_var.set(FIT_LABEL)
        self.manual_width_var.set("")
        self.manual_height_var.set("")
        self.notify_change()

    def init_about_tab(self):
        try:
            with resources.files("tiff2png.ui").joinpath("assets", "T2P.ico").open("rb") as icon_file:
                icon_img = Image.open(icon_file)
                icon_img = icon_img.resize((64, 64), Image.LANCZOS)
            self.about_icon = ImageTk.PhotoImage(icon_img)
            icon_label = ttk.Label(self.about_tab, image=self.about_icon)
        except (OSError, ValueError):
            icon_label = ttk.Label(self.about_tab, text="[icon]")
        icon_label.grid(row=0, column=0, pady=(10, 5), padx=10)
        ttk.Label(self.about_tab, text="TIFF 2 PNG", font=("Segoe UI", 18, "bold")).grid(
            row=1, column=0, pady=(0, 5), padx=10)
        ttk.Label(self.about_tab, text=f"Version {__version__}", font=("Segoe UI", 10)).grid(
            row=2, column=0, pady=(0, 10), padx=10)
        ttk.Label(
            self.about_tab,
            text="Scott McCabe\nBuilt with Python, Tkinter, sv-ttk and Pillow",
            font=("Segoe UI", 9), justify="center",
        ).grid(row=3, column=0, pady=(0, 10), padx=10)
        ttk.Label(
            self.about_tab,
            text="A fast, user-friendly tool for converting TIFF images to PNG.\n"
                 "Supports batch conversion, cropping, scaling, and more.",
            font=("Segoe UI", 9), justify="center",
        ).grid(row=4, column=0, pady=(0, 10), padx=10)


class ConsoleHandler(logging.Handler):
    """Logging handler that writes to a tkinter Text widget"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.pending = set()

    def emit(self, record):
        msg = self.format(record)
        job = None

        def append():
            self.pending.discard(job)
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + "\n")
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        job = self.text_widget.after(0, append)
        self.pending.add(job)

    def cancel_pending(self):
        for job in self.pending:
            self.text_widget.after_cancel(job)
        self.pending.clear()
