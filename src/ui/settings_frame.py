import tkinter as tk
from tkinter import ttk
import logging
from datetime import date
import sys
import os

class SettingsFrame(ttk.Frame):
    def __init__(self, parent, on_settings_change=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.on_settings_change = on_settings_change
        # Add standard resolutions
        self.standard_resolutions = {
            "Custom": None,
            "4K (3840x2160)": (3840, 2160),
            "2K (2560x1440)": (2560, 1440),
            "Full HD (1920x1080)": (1920, 1080),
            "HD (1280x720)": (1280, 720),
            "SVGA (800x600)": (800, 600),
            "VGA (640x480)": (640, 480)
        }
        
        # Create notebook for basic/advanced settings
        self.settings_notebook = ttk.Notebook(self)
        self.settings_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Basic settings tab
        self.basic_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.basic_tab, text="Basic")
        
        # Advanced settings tab
        self.advanced_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.advanced_tab, text="Advanced")
        
        # Logs tab
        self.logs_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.logs_tab, text="Logs")
        
        # About tab
        self.about_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(self.about_tab, text="About")
        self.init_about_tab()
        
        # Create variables first
        self.create_variables()
        
        # Initialize settings after variables are created
        self.init_basic_settings()
        self.init_advanced_settings()
        self.init_logs_tab()
        
        # Setup logging last
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration"""
        # Create logger
        self.logger = logging.getLogger('TIFFtoPNG')
        self.logger.setLevel(logging.DEBUG)
        
        # Create console handler
        self.console_handler = ConsoleHandler(self.log_text)
        self.console_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.console_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(self.console_handler)

    def init_logs_tab(self):
        """Initialize the logs tab with console"""
        # Create text widget for logs
        self.log_text = tk.Text(self.logs_tab, wrap=tk.WORD, width=50, height=15)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.logs_tab, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # Configure grid weights
        self.logs_tab.grid_columnconfigure(0, weight=1)
        self.logs_tab.grid_rowconfigure(0, weight=1)
        
        # Add clear button
        clear_button = ttk.Button(self.logs_tab, text="Clear Logs", command=self.clear_logs)
        clear_button.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Add initial log message
        self.log_text.insert(tk.END, f"Log started at {date.today().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_text.configure(state='disabled')

    def clear_logs(self):
        """Clear the log console"""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, f"Log cleared at {date.today().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_text.configure(state='disabled')

    def create_variables(self):
        """Create all setting variables"""
        # Basic settings
        self.scale_var = tk.DoubleVar(value=100)
        self.resolution_var = tk.StringVar(value="Custom")
        self.fill_mode_var = tk.BooleanVar(value=False)
        self.optimize_var = tk.BooleanVar(value=True)
        
        # Advanced settings
        self.color_mode_var = tk.StringVar(value="auto")
        self.dither_var = tk.StringVar(value="auto")
        self.filter_var = tk.StringVar(value="auto")
        self.chunk_optimize_var = tk.BooleanVar(value=True)
        self.interlace_var = tk.BooleanVar(value=False)
        # Manual resolution
        self.manual_width_var = tk.IntVar(value=0)
        self.manual_height_var = tk.IntVar(value=0)

    def notify_change(self, *args):
        if self.on_settings_change:
            self.on_settings_change()

    def init_basic_settings(self):
        """Initialize basic settings controls"""
        # Resolution scaling
        ttk.Label(self.basic_tab, text="Resolution Scale:").grid(row=0, column=0, sticky=tk.W, pady=5)
        scale_scale = ttk.Scale(self.basic_tab, from_=10, to=100, orient=tk.HORIZONTAL,
                              variable=self.scale_var)
        scale_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        # Only update preview on mouse release
        scale_scale.bind('<ButtonRelease-1>', lambda e: self.notify_change())
        # Live-updating percentage label (label only, no preview update)
        self.scale_percent_var = tk.StringVar()
        def update_scale_label(*args):
            self.scale_percent_var.set(f"{int(self.scale_var.get())}%")
        self.scale_var.trace_add('write', update_scale_label)
        update_scale_label()  # Initialize
        ttk.Label(self.basic_tab, textvariable=self.scale_percent_var).grid(row=0, column=3, padx=5)
        ttk.Label(self.basic_tab, text="(10-100%)").grid(row=0, column=2, padx=5)
        
        # Standard resolutions
        ttk.Label(self.basic_tab, text="Standard Resolution:").grid(row=1, column=0, sticky=tk.W, pady=5)
        resolution_combo = ttk.Combobox(self.basic_tab, textvariable=self.resolution_var,
                                      values=list(self.standard_resolutions.keys()),
                                      state="readonly")
        resolution_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        def on_resolution_selected(event=None):
            # Enable fill mode automatically when a standard resolution is selected (not Custom)
            res_name = self.resolution_var.get()
            if res_name != "Custom":
                self.fill_mode_var.set(True)
                res = self.standard_resolutions.get(res_name)
                if res:
                    self.manual_width_var.set(res[0])
                    self.manual_height_var.set(res[1])
            self.notify_change()
        resolution_combo.bind('<<ComboboxSelected>>', on_resolution_selected)
        
        # Optimization
        optimize_check = ttk.Checkbutton(self.basic_tab, 
                                       text="Optimize PNG (Reduces file size by analyzing and optimizing the image data)",
                                       variable=self.optimize_var, command=self.notify_change)
        optimize_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Add tooltips
        self.create_tooltip(resolution_combo, 
                          "Select a standard resolution.\n"
                          "The image will be scaled to fit within these dimensions\n"
                          "while maintaining its aspect ratio.")
        self.create_tooltip(optimize_check,
                          "When enabled, the PNG file will be optimized by:\n"
                          "1. Finding the best compression method for the image\n"
                          "2. Removing unnecessary metadata\n"
                          "3. Optimizing the color palette\n"
                          "This can reduce file size by 5-25% with no quality loss.")

    def init_advanced_settings(self):
        """Initialize advanced settings controls"""
        # Color mode settings
        color_frame = ttk.LabelFrame(self.advanced_tab, text="Color Settings", padding="5")
        color_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(color_frame, text="Color Mode:").grid(row=0, column=0, sticky=tk.W, pady=2)
        color_mode_combo = ttk.Combobox(color_frame, textvariable=self.color_mode_var,
                                      values=["auto", "RGB", "RGBA", "L", "P"],
                                      state="readonly", width=10)
        color_mode_combo.grid(row=0, column=1, padx=5, pady=2)
        color_mode_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())
        
        # Dithering settings
        ttk.Label(color_frame, text="Dithering:").grid(row=1, column=0, sticky=tk.W, pady=2)
        dither_combo = ttk.Combobox(color_frame, textvariable=self.dither_var,
                                  values=["auto", "NONE", "FLOYDSTEINBERG"],
                                  state="readonly", width=15)
        dither_combo.grid(row=1, column=1, padx=5, pady=2)
        dither_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())
        
        # Compression settings
        comp_frame = ttk.LabelFrame(self.advanced_tab, text="Compression Settings", padding="5")
        comp_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Filter method
        ttk.Label(comp_frame, text="Filter Method:").grid(row=0, column=0, sticky=tk.W, pady=2)
        filter_combo = ttk.Combobox(comp_frame, textvariable=self.filter_var,
                                  values=["auto", "NEAREST", "BOX", "BILINEAR", "HAMMING", "BICUBIC", "LANCZOS"],
                                  state="readonly", width=10)
        filter_combo.grid(row=0, column=1, padx=5, pady=2)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.notify_change())
        
        # Chunk optimization
        chunk_check = ttk.Checkbutton(comp_frame, text="Optimize PNG Chunks",
                                    variable=self.chunk_optimize_var)
        chunk_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Interlacing
        interlace_check = ttk.Checkbutton(comp_frame, text="Interlaced PNG",
                                        variable=self.interlace_var)
        interlace_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Manual resolution entry fields
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
        # Fill mode checkbox (moved from basic tab)
        fill_check = ttk.Checkbutton(manual_res_frame, text="Fill Mode (Crop to exact resolution)",
                                   variable=self.fill_mode_var, command=self.notify_change)
        fill_check.grid(row=1, column=0, columnspan=6, sticky=tk.W, pady=5)
        self.create_tooltip(fill_check,
                          "When enabled, the image will be cropped to exactly match\n"
                          "the selected or manual resolution. When disabled, the image will be\n"
                          "scaled to fit within the resolution while maintaining\n"
                          "its aspect ratio.")
        # Tooltips
        self.create_tooltip(width_entry, "Type the desired output width in pixels.")
        self.create_tooltip(height_entry, "Type the desired output height in pixels.")
        # Clamp and update on Enter or focus out
        def clamp_and_notify_width(event=None):
            min_w = 1
            max_w = getattr(self, 'input_image_width', 10000)
            try:
                val = int(self.manual_width_var.get())
            except Exception:
                val = min_w
            val = max(min_w, min(val, max_w))
            self.manual_width_var.set(val)
            self.notify_change()
        def clamp_and_notify_height(event=None):
            min_h = 1
            max_h = getattr(self, 'input_image_height', 10000)
            try:
                val = int(self.manual_height_var.get())
            except Exception:
                val = min_h
            val = max(min_h, min(val, max_h))
            self.manual_height_var.set(val)
            self.notify_change()
        width_entry.bind('<FocusOut>', clamp_and_notify_width)
        height_entry.bind('<FocusOut>', clamp_and_notify_height)
        width_entry.bind('<Return>', clamp_and_notify_width)
        height_entry.bind('<Return>', clamp_and_notify_height)
        
        # Reset to defaults button
        ttk.Button(self.advanced_tab, text="Reset to Defaults",
                  command=self.reset_advanced_settings).grid(row=4, column=0, columnspan=2, pady=10)
        
        # Add tooltips
        self.create_tooltip(color_mode_combo, 
                          "Color mode for output PNG:\nauto: Automatically choose best mode\nRGB: Full color (24-bit)\nRGBA: Full color with transparency\nP: Palette mode (8-bit)\nL: Grayscale\nLA: Grayscale with transparency")
        self.create_tooltip(dither_combo,
                          "Dithering method for color reduction:\nauto: Automatically choose best method\nnone: No dithering\nfloyd-steinberg: Error diffusion dithering\nordered: Ordered dithering")
        self.create_tooltip(filter_combo,
                          "PNG filter method:\nauto: Automatically choose best filter\nnone: No filtering\nsub: Subtract left pixel\nup: Subtract above pixel\naverage: Average of left and above\npaeth: Paeth predictor")
        self.create_tooltip(chunk_check,
                          "Optimize PNG chunk structure:\nRemoves unnecessary chunks\nReorders chunks for better compression\nMay slightly increase processing time")
        self.create_tooltip(interlace_check,
                          "Create interlaced PNG:\nAllows progressive loading\nSlightly larger file size\nBetter for web use")

    def reset_advanced_settings(self):
        """Reset advanced settings to their default values"""
        self.color_mode_var.set("auto")
        self.dither_var.set("auto")
        self.filter_var.set("auto")
        self.chunk_optimize_var.set(True)
        self.interlace_var.set(False)
        self.manual_width_var.set(0)
        self.manual_height_var.set(0)

    def create_tooltip(self, widget, text):
        """Create a tooltip for a given widget"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(tooltip, text=text, justify=tk.LEFT,
                            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                            padding=(5, 2))
            label.pack()
            
            def hide_tooltip():
                tooltip.destroy()
            
            widget.tooltip = tooltip
            widget.bind('<Leave>', lambda e: hide_tooltip())
            tooltip.bind('<Leave>', lambda e: hide_tooltip())
        
        widget.bind('<Enter>', show_tooltip)

    def init_about_tab(self):
        """Initialize the About tab with app info, icon, and version/date"""
        def resource_path(relative_path):
            try:
                base_path = sys._MEIPASS
            except AttributeError:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
        try:
            from PIL import Image, ImageTk
            icon_img = Image.open(resource_path("ui/T2P.ico"))
            icon_img = icon_img.resize((64, 64), Image.LANCZOS)
            self.about_icon = ImageTk.PhotoImage(icon_img)
            icon_label = ttk.Label(self.about_tab, image=self.about_icon)
            icon_label.grid(row=0, column=0, pady=(10, 5), padx=10)
        except Exception:
            icon_label = ttk.Label(self.about_tab, text="[icon]")
            icon_label.grid(row=0, column=0, pady=(10, 5), padx=10)
        # App name
        name_label = ttk.Label(self.about_tab, text="TIFF 2 PNG", font=("Segoe UI", 18, "bold"))
        name_label.grid(row=1, column=0, pady=(0, 5), padx=10)
        # Version and date
        version = "V0.1"
        today = date.today().strftime("%Y-%m-%d")
        version_label = ttk.Label(self.about_tab, text=f"Version {version} ({today})", font=("Segoe UI", 10))
        version_label.grid(row=2, column=0, pady=(0, 10), padx=10)
        # Copyright and credits
        copyright_label = ttk.Label(
            self.about_tab,
            text="© 2025 Scott McCabe\nDeveloped with Cursor, Python, Tkinter, and Pillow",
            font=("Segoe UI", 9), justify="center"
        )
        copyright_label.grid(row=3, column=0, pady=(0, 10), padx=10)
        # Description
        desc = ("A fast, user-friendly tool for converting TIFF images to PNG.\n"
                "Supports batch conversion, cropping, scaling, and more.\n"
                "For support or updates, visit: google.com")
        desc_label = ttk.Label(self.about_tab, text=desc, font=("Segoe UI", 9), justify="center")
        desc_label.grid(row=4, column=0, pady=(0, 10), padx=10)

class ConsoleHandler(logging.Handler):
    """Custom logging handler that writes to a tkinter Text widget"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        # Schedule the update on the main thread
        self.text_widget.after(0, append) 