import tkinter as tk
from tkinter import ttk
from pathlib import Path

class InfoFrame(ttk.LabelFrame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="File Information", padding="5", *args, **kwargs)
        self.parent = parent
        
        # Create grid layout for two columns
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Input file info (left column)
        ttk.Label(self, text="Input File:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_file_label = ttk.Label(self, text="No file selected")
        self.input_file_label.grid(row=1, column=0, sticky=tk.W, pady=2)
        
        ttk.Label(self, text="File Size:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.input_size_label = ttk.Label(self, text="--")
        self.input_size_label.grid(row=3, column=0, sticky=tk.W, pady=2)
        
        ttk.Label(self, text="Resolution:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.resolution_label = ttk.Label(self, text="--")
        self.resolution_label.grid(row=5, column=0, sticky=tk.W, pady=2)
        
        # Output file info (right column)
        ttk.Label(self, text="Output File:").grid(row=0, column=1, sticky=tk.W, pady=2)
        self.output_file_label = ttk.Label(self, text="--")
        self.output_file_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(self, text="Estimated Size:").grid(row=2, column=1, sticky=tk.W, pady=2)
        self.estimated_size_label = ttk.Label(self, text="--")
        self.estimated_size_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(self, text="Output Resolution:").grid(row=4, column=1, sticky=tk.W, pady=2)
        self.output_res_label = ttk.Label(self, text="--")
        self.output_res_label.grid(row=5, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(self, text="Compression Ratio:").grid(row=6, column=1, sticky=tk.W, pady=2)
        self.compression_ratio_label = ttk.Label(self, text="--")
        self.compression_ratio_label.grid(row=7, column=1, sticky=tk.W, pady=2)
        
        # Add tooltips
        self.create_tooltip(self.input_size_label,
                          "Size of the input TIFF file")
        self.create_tooltip(self.resolution_label,
                          "Current resolution of the image\n"
                          "Format: Width x Height pixels")
        self.create_tooltip(self.estimated_size_label,
                          "Estimated size of the output PNG file\n"
                          "based on current settings")
        self.create_tooltip(self.compression_ratio_label,
                          "Ratio of output size to input size\n"
                          "Lower numbers indicate better compression")
        self.create_tooltip(self.output_res_label,
                          "Resolution of the output PNG file\n"
                          "Format: Width x Height pixels")

    def update_input_info(self, file_path, file_size, resolution):
        """Update input file information"""
        if file_path:
            self.input_file_label.config(text=Path(file_path).name)
            self.input_size_label.config(text=file_size)
            self.resolution_label.config(text=f"{resolution[0]} x {resolution[1]} pixels")
        else:
            self.input_file_label.config(text="No file selected")
            self.input_size_label.config(text="--")
            self.resolution_label.config(text="--")

    def update_output_info(self, file_path, estimated_size, output_resolution, compression_ratio):
        """Update output file information"""
        if file_path:
            self.output_file_label.config(text=Path(file_path).name)
            self.estimated_size_label.config(text=estimated_size)
            self.output_res_label.config(text=output_resolution)
            self.compression_ratio_label.config(text=f"{compression_ratio:.1f}x")
        else:
            self.output_file_label.config(text="--")
            self.estimated_size_label.config(text="--")
            self.output_res_label.config(text="--")
            self.compression_ratio_label.config(text="--")

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