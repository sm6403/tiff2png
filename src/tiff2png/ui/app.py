import logging
import os
import queue
import threading
import tkinter as tk
from importlib import resources
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import sv_ttk
from PIL import UnidentifiedImageError

from tiff2png.core.geometry import (
    Box,
    clamp_box,
    compute_geometry,
    default_fill_box,
    preview_geometry,
)
from tiff2png.core.imaging import (
    PROXY_MAX_SIDE,
    estimate_png_size,
    format_size,
    load_pages,
    make_proxy,
    render,
)
from tiff2png.core.jobs import Job, Naming, find_tiffs, plan_jobs
from tiff2png.core.runner import run_jobs
from tiff2png.core.settings import Fit, Pages
from tiff2png.ui.batch_preview_frame import BatchPreviewFrame
from tiff2png.ui.info_frame import InfoFrame
from tiff2png.ui.preview_frame import PreviewFrame
from tiff2png.ui.settings_frame import SettingsFrame

THEME = "light"
PATH_DEBOUNCE_MS = 400
LOAD_ERRORS = (OSError, ValueError, UnidentifiedImageError)
POLL_MS = 50
CLOSE_JOIN_SECONDS = 10
LOCKABLE_CLASSES = frozenset({
    "TButton", "TEntry", "TCheckbutton", "TRadiobutton", "TCombobox", "TScale", "TSpinbox",
    "Button", "Checkbutton", "Radiobutton", "Entry", "Scale", "Spinbox",
})
NAMING_CHOICES = {"Root_NN (Root Name + number)": Naming.ROOT_NN, "Keep original filenames": Naming.ORIGINAL}

logger = logging.getLogger(__name__)


def displayable(image):
    """Return a copy of image in a mode Tk can show."""
    if image.mode in ("L", "RGB", "RGBA"):
        return image
    if image.mode == "I;16":
        return image.point(lambda value: value / 256, "L")
    return image.convert("RGBA")


class TIFFtoPNGConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TIFF to PNG Converter")
        sv_ttk.set_theme(THEME, root=self.root)
        with resources.as_file(resources.files("tiff2png.ui") / "assets" / "T2P.ico") as icon_path:
            self.root.iconbitmap(str(icon_path))

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(self.main_frame, padding="5")
        self.left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.right_panel = ttk.Frame(self.main_frame, padding="5")
        self.right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=1)

        self.source_path = None
        self.proxy = None
        self.source_meta = None
        self.source_file_size = 0
        self.crop_box = None
        self.settings_error = None
        self._path_job = None
        self._loaded_input = None
        self._geometry_key = None
        self._queue = queue.Queue()
        self._worker = None
        self._cancel_event = None
        self._poll_job = None
        self._locked = {}
        self.init_components()
        self.root.bind("<Destroy>", self._on_root_destroy)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.update_idletasks()
        min_width = self.main_frame.winfo_reqwidth() + 20
        min_height = self.main_frame.winfo_reqheight() + 20
        self.root.minsize(min_width, min_height)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - min_width) // 2
        y = (screen_height - min_height) // 2
        self.root.geometry(f"+{x}+{y}")

        self.logger = self.settings_frame.logger
        self.logger.info("Application started")

    def init_components(self):
        mode_frame = self.mode_frame = ttk.LabelFrame(self.left_panel, text="Conversion Mode", padding="5")
        mode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

        self.mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(mode_frame, text="Single File", variable=self.mode_var,
                        value="single", command=self.on_mode_change).grid(row=0, column=0, padx=5)
        ttk.Radiobutton(mode_frame, text="Batch Convert", variable=self.mode_var,
                        value="batch", command=self.on_mode_change).grid(row=0, column=1, padx=5)

        file_frame = self.file_frame = ttk.LabelFrame(self.left_panel, text="File Selection", padding="5")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(file_frame, text="Input:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_path_var = tk.StringVar()
        self.input_entry = ttk.Entry(file_frame, textvariable=self.input_path_var, width=30)
        self.input_entry.grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)

        ttk.Label(file_frame, text="Output:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_path_var = tk.StringVar()
        self.output_entry = ttk.Entry(file_frame, textvariable=self.output_path_var, width=30)
        self.output_entry.grid(row=1, column=1, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)
        for entry in (self.input_entry, self.output_entry):
            entry.bind("<Return>", self.apply_paths)
            entry.bind("<FocusOut>", self.apply_paths)

        self.batch_frame = ttk.LabelFrame(self.left_panel, text="Batch Settings", padding="5")
        self.batch_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        self.save_to_folder_var = tk.BooleanVar(value=True)
        self.save_to_folder_cb = ttk.Checkbutton(
            self.batch_frame,
            text="Save to new folder in input directory",
            variable=self.save_to_folder_var,
            command=self.on_save_to_folder_change
        )
        self.save_to_folder_cb.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        self.naming_var = tk.StringVar(value=next(iter(NAMING_CHOICES)))
        ttk.Label(self.batch_frame, text="Naming:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.naming_combo = ttk.Combobox(self.batch_frame, textvariable=self.naming_var,
                                         values=list(NAMING_CHOICES), state="readonly", width=28)
        self.naming_combo.grid(row=1, column=1, padx=5)
        self.naming_combo.bind("<<ComboboxSelected>>", self.on_naming_change)
        ttk.Label(self.batch_frame, text="Root Name:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.batch_root_var = tk.StringVar(value="Batch_01")
        self.batch_root_entry = ttk.Entry(self.batch_frame, textvariable=self.batch_root_var, width=20)
        self.batch_root_entry.grid(row=2, column=1, padx=5, sticky=tk.W)
        self.all_pages_var = tk.BooleanVar(value=False)
        self.all_pages_cb = ttk.Checkbutton(self.batch_frame, text="Export all pages of multi-page files",
                                            variable=self.all_pages_var)
        self.all_pages_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)

        self.settings_frame = SettingsFrame(self.left_panel, on_settings_change=self.on_settings_change)
        self.settings_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)

        self.info_frame = InfoFrame(self.left_panel)
        self.info_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=5)

        self.preview_frame = PreviewFrame(self.right_panel, on_crop_update=self.on_crop_update)
        self.preview_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.batch_preview_frame = BatchPreviewFrame(self.right_panel)
        self.batch_preview_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.left_panel, variable=self.progress_var,
                                            maximum=100, mode='determinate')
        self.progress_bar.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=5)

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(self.left_panel, textvariable=self.status_var)
        self.status_label.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5)

        self.convert_button = ttk.Button(self.left_panel, text="Convert",
                                         command=self.start_conversion)
        self.convert_button.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=5)

        self.cancel_button = ttk.Button(self.left_panel, text="Cancel", command=self.cancel_batch,
                                        state=tk.DISABLED)
        self.cancel_button.grid(row=8, column=0, sticky=(tk.W, tk.E), pady=5)

        self.input_path_var.trace_add('write', self.on_path_change)
        self.output_path_var.trace_add('write', self.on_path_change)

        self.on_mode_change()

    def _on_root_destroy(self, event):
        if event.widget is self.root:
            self._cancel_path_job()
            self._cancel_poll()
            if self._cancel_event is not None:
                self._cancel_event.set()

    def on_close(self):
        if self._worker is not None:
            self._cancel_poll()
            self._cancel_event.set()
            self._worker.join(CLOSE_JOIN_SECONDS)
        self.root.destroy()

    def _cancel_poll(self):
        if self._poll_job is not None:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None

    def on_naming_change(self, event=None):
        original = NAMING_CHOICES[self.naming_var.get()] is Naming.ORIGINAL
        self.batch_root_entry.configure(state=tk.DISABLED if original else tk.NORMAL)

    def _cancel_path_job(self):
        if self._path_job is not None:
            self.root.after_cancel(self._path_job)
            self._path_job = None

    def current_settings(self):
        """Return the ConvertSettings for the UI state, or None with settings_error set."""
        settings, error = self.settings_frame.read_settings()
        self.settings_error = error
        if error is not None:
            self.status_var.set(error)
        return settings

    def on_mode_change(self):
        mode = self.mode_var.get()
        if hasattr(self, "logger"):
            self.logger.info(f"Switching to {mode} mode")
        if mode == "single":
            self.batch_frame.grid_remove()
            self.batch_preview_frame.grid_remove()
            self.preview_frame.grid()
        else:
            self.batch_frame.grid()
            self.batch_preview_frame.grid()
            self.preview_frame.grid_remove()
        self._loaded_input = None
        self.apply_paths()

    def browse_input(self):
        if self.mode_var.get() == "single":
            file_path = filedialog.askopenfilename(
                title="Select TIFF File",
                filetypes=[("TIFF files", "*.tif *.tiff"), ("All files", "*.*")]
            )
        else:
            file_path = filedialog.askdirectory(title="Select Input Folder")
        if file_path:
            self.logger.info(f"Selected input: {file_path}")
            self.input_path_var.set(file_path)
            self.apply_paths()

    def browse_output(self):
        if self.mode_var.get() == "single":
            path = filedialog.asksaveasfilename(
                title="Save PNG File",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
        else:
            path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.logger.info(f"Selected output: {path}")
            self.output_path_var.set(path)
            self.apply_paths()

    def on_path_change(self, *args):
        self._cancel_path_job()
        self._path_job = self.root.after(PATH_DEBOUNCE_MS, self.apply_paths)

    def apply_paths(self, event=None):
        """Load the input if it changed and refresh the info and previews."""
        self._cancel_path_job()
        input_text = self.input_path_var.get().strip()
        if self.mode_var.get() == "single":
            if input_text and Path(input_text).is_file():
                if input_text != self._loaded_input:
                    self.load_input_file(input_text)
                    return
            elif not input_text:
                self.clear_source()
                return
        else:
            if input_text and Path(input_text).is_dir():
                if input_text != self._loaded_input:
                    self.load_batch_files(input_text)
                    return
            elif not input_text:
                self.clear_source()
                return
        self.refresh_outputs()

    def clear_source(self):
        self._loaded_input = None
        self.source_path = None
        self.proxy = None
        self.source_meta = None
        self.crop_box = None
        self.info_frame.update_input_info(None, None, None)
        self.info_frame.update_output_info(None, None, None, None)
        self.preview_frame.clear_input()
        self.preview_frame.update_output_preview(None)

    def _set_source(self, path):
        """Load page 0 of path once and keep only a downscaled proxy for previews."""
        file_size = os.path.getsize(path)
        for _index, image, meta in load_pages(path, Pages.FIRST):
            proxy = make_proxy(image)
        self.proxy = proxy
        self.source_meta = meta
        self.source_file_size = file_size
        self.source_path = Path(path)
        self.crop_box = None
        self._geometry_key = None
        source_size = proxy.source_size
        self.settings_frame.set_input_image_size(source_size)
        self.info_frame.update_input_info(str(path), format_size(file_size), source_size)
        self.preview_frame.set_input_image(displayable(proxy.image), source_size)

    def load_input_file(self, file_path):
        try:
            self.logger.debug(f"Loading input file: {file_path}")
            self._set_source(file_path)
        except LOAD_ERRORS as error:
            self.logger.error(f"Failed to load file: {error}")
            messagebox.showerror("Error", f"Failed to load file: {error}")
            self._loaded_input = None
            return
        self._loaded_input = str(file_path)
        self.logger.info(
            f"Loaded image: {self.proxy.source_size[0]}x{self.proxy.source_size[1]}, "
            f"{format_size(self.source_file_size)}"
        )
        self.autofill_output_path(file_path)
        self.refresh_outputs()

    def load_batch_files(self, folder_path):
        try:
            tiff_files = find_tiffs(folder_path)
        except OSError as error:
            self.logger.error(f"Failed to load batch files: {error}")
            messagebox.showerror("Error", f"Failed to load batch files: {error}")
            return
        self._loaded_input = str(folder_path)
        if not tiff_files:
            self.logger.warning("No TIFF files found in selected folder")
            messagebox.showwarning("Warning", "No TIFF files found in selected folder")
            return
        self.logger.info(f"Found {len(tiff_files)} TIFF files")
        self.batch_preview_frame.update_preview(tiff_files)
        if not self.output_path_var.get():
            output_folder = str(Path(folder_path) / "PNG_Output")
            self.output_path_var.set(output_folder)
            self.logger.info(f"Set default output folder: {output_folder}")
        try:
            self._set_source(tiff_files[0])
        except LOAD_ERRORS as error:
            self.logger.error(f"Failed to read {tiff_files[0].name}: {error}")
            self.proxy = None
        self.refresh_outputs(show_input=False)

    def _effective_box(self, settings):
        if settings.fit is Fit.FILL and settings.target is not None:
            return self.crop_box
        return None

    def _input_overlay(self, settings):
        if settings.fit is not Fit.FILL or settings.target is None:
            return None
        size = self.proxy.source_size
        if self.crop_box is None:
            box = default_fill_box(size, settings.target, settings.scale)
        else:
            box = clamp_box(self.crop_box, size, settings.target[0] / settings.target[1])
        return box.as_tuple()

    def refresh_outputs(self, show_input=True):
        """Render the cached source with the current settings into the previews and info."""
        if self.proxy is None:
            return
        settings = self.current_settings()
        if settings is None:
            return
        key = (settings.scale, settings.target, settings.fit)
        if key != self._geometry_key:
            self._geometry_key = key
            self.crop_box = None
        try:
            proxy = self.proxy
            geometry = compute_geometry(proxy.source_size, settings, self._effective_box(settings))
            shown = preview_geometry(geometry, proxy.image.size, proxy.factor, PROXY_MAX_SIDE)
            output = render(proxy.image, shown, settings)
            estimated = estimate_png_size(output, geometry.out_size, settings)
        except (ValueError, OSError) as error:
            self.logger.error(f"Error updating preview: {error}")
            self.preview_frame.update_output_preview(None)
            return
        if show_input:
            overlay = self._input_overlay(settings)
            aspect = settings.target[0] / settings.target[1] if overlay else None
            self.preview_frame.set_crop_overlay(overlay, aspect)
        self.preview_frame.update_output_preview(displayable(output))
        out_w, out_h = geometry.out_size
        self.info_frame.update_output_info(
            self.output_path_var.get() or None,
            "~" + format_size(estimated),
            f"{out_w} x {out_h} pixels",
            estimated / self.source_file_size if self.source_file_size else 0,
        )

    def on_settings_change(self, *args):
        self.refresh_outputs(show_input=self.mode_var.get() == "single")

    def start_conversion(self):
        if self.mode_var.get() == "single":
            self.convert_single_file()
        else:
            self.convert_batch_files()

    def convert_single_file(self):
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()

        if not input_path or not output_path:
            self.logger.warning("Input or output path not specified")
            messagebox.showwarning("Warning", "Please select input and output files")
            return
        settings = self.current_settings()
        if settings is None:
            messagebox.showerror("Invalid settings", self.settings_error)
            return
        if self.proxy is None or self._loaded_input != input_path:
            self.load_input_file(input_path)
            if self.proxy is None or self._loaded_input != input_path:
                return

        job = Job(Path(input_path), 0, Path(output_path))
        self.logger.info("Starting single file conversion")
        self.logger.debug(f"Conversion settings: {settings}")
        self.status_var.set("Converting...")
        self.progress_var.set(0)
        self.root.update_idletasks()

        report = run_jobs(
            [job], settings,
            crop_box=self._effective_box(settings),
            crop_source_size=self.proxy.source_size,
        )
        if report.failed:
            message = report.failed[0].message
            self.logger.error(f"Conversion failed: {message}")
            messagebox.showerror("Error", f"Conversion failed: {message}")
            self.status_var.set("Conversion failed")
            return
        self.status_var.set("Conversion complete")
        self.progress_var.set(100)
        self.logger.info("File converted successfully")
        messagebox.showinfo("Success", "File converted successfully")

    def convert_batch_files(self):
        if self._worker is not None:
            return
        input_folder = self.input_path_var.get().strip()
        output_folder = self.output_path_var.get().strip()

        if not input_folder or not output_folder:
            self.logger.warning("Input or output folder not specified")
            messagebox.showwarning("Warning", "Please select input and output folders")
            return
        tiff_files = self.batch_preview_frame.get_selected_files()
        if not tiff_files:
            self.logger.warning("No TIFF files selected for conversion")
            messagebox.showwarning(
                "Warning", "No TIFF files selected for conversion. Please check at least one file.")
            return
        settings = self.current_settings()
        if settings is None:
            messagebox.showerror("Invalid settings", self.settings_error)
            return

        plan = plan_jobs(
            tiff_files, output_folder,
            NAMING_CHOICES[self.naming_var.get()],
            self.batch_root_var.get(),
            Pages.ALL if self.all_pages_var.get() else Pages.FIRST,
        )
        if plan.collisions:
            names = "\n".join(
                ", ".join(job.src.name for job in group) + f" -> {group[0].dst.name}"
                for group in plan.collisions)
            self.logger.error("Output name collisions, batch not started")
            messagebox.showerror(
                "Output name collision",
                f"Several files would write the same output name:\n\n{names}")
            return
        jobs = list(plan.jobs)
        if plan.existing:
            answer = messagebox.askyesnocancel(
                "Overwrite existing files?",
                f"{len(plan.existing)} output file(s) already exist.\n\n"
                "Yes: overwrite them\nNo: skip them\nCancel: do not convert")
            if answer is None:
                self.status_var.set("Batch conversion cancelled")
                return
            if not answer:
                skipped = set(plan.existing)
                jobs = [job for job in jobs if job not in skipped]
                if not jobs:
                    self.status_var.set("Nothing to convert, all outputs exist")
                    return
        self.logger.info(f"Starting batch conversion of {len(jobs)} files")
        self.logger.debug(f"Conversion settings: {settings}")
        self._start_batch_worker(jobs, settings)

    def _start_batch_worker(self, jobs, settings):
        self.status_var.set("Converting...")
        self.progress_var.set(0)
        self._set_running(True)
        self._cancel_event = threading.Event()
        crop_box = crop_size = None
        if self.proxy is not None:
            crop_box = self._effective_box(settings)
            crop_size = self.proxy.source_size
        self._worker = threading.Thread(
            target=self._worker_main,
            args=(jobs, settings, self._cancel_event, crop_box, crop_size),
            name="batch-convert", daemon=True)
        self._worker.start()
        self._poll_job = self.root.after(POLL_MS, self._drain_queue)

    def _worker_main(self, jobs, settings, cancel_event, crop_box, crop_size):
        """Runs off the main thread: reports only through the queue, never touches Tk."""
        def on_progress(finished, total, job):
            self._queue.put(("progress", finished, total, job))

        try:
            report = run_jobs(jobs, settings, on_progress, cancel_event, crop_box, crop_size)
        except Exception as error:
            logger.exception("Batch worker crashed")
            self._queue.put(("crashed", error))
        else:
            self._queue.put(("done", report))

    def _drain_queue(self):
        self._poll_job = None
        finished_message = None
        while True:
            try:
                message = self._queue.get_nowait()
            except queue.Empty:
                break
            if message[0] == "progress":
                _kind, finished, total, job = message
                self.progress_var.set(finished / total * 100)
                if not self._cancel_event.is_set():
                    self.status_var.set(f"Converting... ({finished}/{total}) {job.src.name}")
            else:
                finished_message = message
        if finished_message is None:
            self._poll_job = self.root.after(POLL_MS, self._drain_queue)
            return
        self._worker.join()
        self._worker = None
        self._cancel_event = None
        self._set_running(False)
        if finished_message[0] == "crashed":
            error = finished_message[1]
            self.status_var.set("Batch conversion failed")
            messagebox.showerror("Error", f"Batch conversion failed: {type(error).__name__}: {error}")
            return
        self._show_batch_result(finished_message[1])

    def _show_batch_result(self, report):
        successful = len(report.done)
        failed = len(report.failed)
        if report.cancelled:
            self.status_var.set(f"Cancelled ({successful} converted, {failed} failed)")
            self.logger.warning(f"Batch cancelled: {successful} converted, {failed} failed")
        else:
            self.status_var.set("Batch conversion complete")
            self.progress_var.set(100)
        if failed:
            self.logger.warning(f"Batch finished with {failed} failures: {successful} files converted")
            details = "\n".join(
                f"{item.job.src.name} (page {item.job.page + 1}): {item.message}"
                for item in report.failed)
            messagebox.showwarning(
                "Conversion summary",
                f"{failed} file(s) failed, {successful} converted"
                f"{' before cancelling' if report.cancelled else ''}\n\n{details}")
        elif not report.cancelled:
            self.logger.info(f"Batch conversion completed successfully: {successful} files converted")
            messagebox.showinfo("Success", f"Successfully converted {successful} files")

    def cancel_batch(self):
        if self._cancel_event is not None and not self._cancel_event.is_set():
            self._cancel_event.set()
            self.cancel_button.configure(state=tk.DISABLED)
            self.status_var.set("Cancelling...")
            self.logger.info("Batch cancel requested")

    def _lockable_widgets(self):
        stack = [self.mode_frame, self.file_frame, self.batch_frame,
                 self.settings_frame.basic_tab, self.settings_frame.advanced_tab,
                 self.batch_preview_frame, self.convert_button]
        while stack:
            widget = stack.pop()
            if widget.winfo_class() in LOCKABLE_CLASSES:
                yield widget
            stack.extend(widget.winfo_children())

    def _set_running(self, running):
        if running:
            for widget in self._lockable_widgets():
                self._locked[widget] = str(widget.cget("state"))
                widget.configure(state=tk.DISABLED)
            self.cancel_button.configure(state=tk.NORMAL)
        else:
            for widget, state in self._locked.items():
                if widget.winfo_exists():
                    widget.configure(state=state)
            self._locked = {}
            self.cancel_button.configure(state=tk.DISABLED)

    def on_save_to_folder_change(self):
        input_path = self.input_path_var.get()
        if input_path:
            self.autofill_output_path(input_path)

    def autofill_output_path(self, input_path):
        if not input_path:
            return
        input_path = Path(input_path)
        output_dir = input_path.parent / "PNG_Output" if self.save_to_folder_var.get() else input_path.parent
        self.output_path_var.set(str(output_dir / f"{input_path.stem}.png"))

    def on_crop_update(self, crop_box):
        """Callback when the crop box is moved: remember it and refresh the output."""
        if crop_box is None:
            return
        self.crop_box = Box(*crop_box)
        self.refresh_outputs(show_input=False)

    def run(self):
        self.root.mainloop()


def main():
    app = TIFFtoPNGConverter()
    app.run()


if __name__ == "__main__":
    main()
