import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os
from PIL import Image
import math
import logging
import sys

from ui.preview_frame import PreviewFrame
from ui.batch_preview_frame import BatchPreviewFrame
from ui.settings_frame import SettingsFrame
from ui.info_frame import InfoFrame
from core.image_processor import ImageProcessor

class TIFFtoPNGConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TIFF to PNG Converter")
        def resource_path(relative_path):
            try:
                base_path = sys._MEIPASS
            except AttributeError:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
        self.root.iconbitmap(resource_path("ui/T2P.ico"))
        
        # Configure root window
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Create left panel for controls
        self.left_panel = ttk.Frame(self.main_frame, padding="5")
        self.left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create right panel for previews
        self.right_panel = ttk.Frame(self.main_frame, padding="5")
        self.right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=1)
        
        # Initialize components
        self.image_processor = ImageProcessor()
        self.init_components()
        
        # Set minimum window size
        self.root.update_idletasks()
        min_width = self.main_frame.winfo_reqwidth() + 20
        min_height = self.main_frame.winfo_reqwidth() + 20
        self.root.minsize(min_width, min_height)
        
        # Center window on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - min_width) // 2
        y = (screen_height - min_height) // 2
        self.root.geometry(f"+{x}+{y}")
        
        # Get logger from settings frame
        self.logger = self.settings_frame.logger
        self.logger.info("Application started")

    def init_components(self):
        """Initialize all UI components"""
        # Mode selection
        mode_frame = ttk.LabelFrame(self.left_panel, text="Conversion Mode", padding="5")
        mode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(mode_frame, text="Single File", variable=self.mode_var,
                       value="single", command=self.on_mode_change).grid(row=0, column=0, padx=5)
        ttk.Radiobutton(mode_frame, text="Batch Convert", variable=self.mode_var,
                       value="batch", command=self.on_mode_change).grid(row=0, column=1, padx=5)
        
        # File selection
        file_frame = ttk.LabelFrame(self.left_panel, text="File Selection", padding="5")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Input file
        ttk.Label(file_frame, text="Input:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.input_path_var, width=30).grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)
        
        # Output file/folder
        ttk.Label(file_frame, text="Output:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.output_path_var, width=30).grid(row=1, column=1, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)
        
        # Batch settings
        self.batch_frame = ttk.LabelFrame(self.left_panel, text="Batch Settings", padding="5")
        self.batch_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        # Save to folder checkbox inside batch_frame
        self.save_to_folder_var = tk.BooleanVar(value=True)
        self.save_to_folder_cb = ttk.Checkbutton(
            self.batch_frame,
            text="Save to new folder in input directory",
            variable=self.save_to_folder_var,
            command=self.on_save_to_folder_change
        )
        self.save_to_folder_cb.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        # Root name label and entry
        ttk.Label(self.batch_frame, text="Root Name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.batch_root_var = tk.StringVar(value="Batch_01")
        ttk.Entry(self.batch_frame, textvariable=self.batch_root_var, width=20).grid(row=1, column=1, padx=5)
        # Settings frame
        self.settings_frame = SettingsFrame(self.left_panel, on_settings_change=self.on_settings_change)
        self.settings_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Info frame
        self.info_frame = InfoFrame(self.left_panel)
        self.info_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Preview frames
        self.preview_frame = PreviewFrame(self.right_panel, on_crop_update=self.on_crop_update)
        self.preview_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.batch_preview_frame = BatchPreviewFrame(self.right_panel)
        self.batch_preview_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.left_panel, variable=self.progress_var,
                                          maximum=100, mode='determinate')
        self.progress_bar.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(self.left_panel, textvariable=self.status_var)
        self.status_label.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Convert button
        self.convert_button = ttk.Button(self.left_panel, text="Convert",
                                       command=self.start_conversion)
        self.convert_button.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Add trace callbacks to input and output path variables
        self.input_path_var.trace_add('write', self.on_path_change)
        self.output_path_var.trace_add('write', self.on_path_change)
        # Only add traces/callbacks to settings variables that should update live
        # Remove scale_var trace to on_settings_change to prevent lag
        self.settings_frame.resolution_var.trace_add('write', self.on_settings_change)
        self.settings_frame.optimize_var.trace_add('write', self.on_settings_change)
        self.settings_frame.fill_mode_var.trace_add('write', self.on_settings_change)
        self.settings_frame.color_mode_var.trace_add('write', self.on_settings_change)
        self.settings_frame.dither_var.trace_add('write', self.on_settings_change)
        self.settings_frame.filter_var.trace_add('write', self.on_settings_change)
        self.settings_frame.chunk_optimize_var.trace_add('write', self.on_settings_change)
        self.settings_frame.interlace_var.trace_add('write', self.on_settings_change)

    def on_mode_change(self):
        """Handle mode change between single and batch conversion"""
        mode = self.mode_var.get()
        self.logger.info(f"Switching to {mode} mode")
        if mode == "single":
            self.batch_frame.grid_remove()
            self.batch_preview_frame.grid_remove()
            self.preview_frame.grid()
        else:
            self.batch_frame.grid()
            self.batch_preview_frame.grid()
            self.preview_frame.grid_remove()

    def browse_input(self):
        """Browse for input file or folder"""
        if self.mode_var.get() == "single":
            file_path = filedialog.askopenfilename(
                title="Select TIFF File",
                filetypes=[("TIFF files", "*.tif;*.tiff"), ("All files", "*.*")]
            )
            if file_path:
                self.logger.info(f"Selected input file: {file_path}")
                self.input_path_var.set(file_path)
                self.load_input_file(file_path)
        else:
            folder_path = filedialog.askdirectory(title="Select Input Folder")
            if folder_path:
                self.logger.info(f"Selected input folder: {folder_path}")
                self.input_path_var.set(folder_path)
                self.load_batch_files(folder_path)

    def browse_output(self):
        """Browse for output file or folder"""
        if self.mode_var.get() == "single":
            file_path = filedialog.asksaveasfilename(
                title="Save PNG File",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if file_path:
                self.logger.info(f"Selected output file: {file_path}")
                self.output_path_var.set(file_path)
                # Always update output info if input is set
                input_path = self.input_path_var.get()
                if input_path:
                    try:
                        img = Image.open(input_path)
                        file_size = os.path.getsize(input_path)
                        self.update_estimated_size(img, file_size)
                        self.update_live_output_preview(img)
                    except Exception as e:
                        self.logger.error(f"Failed to update output info: {str(e)}")
        else:
            folder_path = filedialog.askdirectory(title="Select Output Folder")
            if folder_path:
                self.logger.info(f"Selected output folder: {folder_path}")
                self.output_path_var.set(folder_path)
                # Always update output info if input is set
                input_path = self.input_path_var.get()
                if input_path:
                    try:
                        tiff_files = []
                        for ext in ('.tif', '.tiff'):
                            tiff_files.extend(Path(input_path).glob(f'*{ext}'))
                        if tiff_files:
                            img = Image.open(tiff_files[0])
                            file_size = os.path.getsize(tiff_files[0])
                            self.update_estimated_size(img, file_size)
                            self.update_live_output_preview(img)
                    except Exception as e:
                        self.logger.error(f"Failed to update output info: {str(e)}")

    def load_input_file(self, file_path):
        """Load and display input file"""
        try:
            self.logger.debug(f"Loading input file: {file_path}")
            # Load image
            img = Image.open(file_path)
            
            # Get file info
            file_size = os.path.getsize(file_path)
            resolution = img.size
            
            self.logger.info(f"Loaded image: {resolution[0]}x{resolution[1]}, {self.image_processor.format_size(file_size)}")
            
            # Update info frame
            self.info_frame.update_input_info(
                file_path,
                self.image_processor.format_size(file_size),
                resolution
            )
            
            # Update preview
            self.preview_frame.update_input_preview(img)
            
            # Autofill output path
            self.autofill_output_path(file_path)
            
            # Update estimated output size
            self.update_estimated_size(img, file_size)
            
        except Exception as e:
            self.logger.error(f"Failed to load file: {str(e)}")
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")

    def load_batch_files(self, folder_path):
        """Load and display batch files"""
        try:
            self.logger.debug(f"Loading batch files from: {folder_path}")
            # Get all TIFF files
            tiff_files = []
            for ext in ('.tif', '.tiff'):
                tiff_files.extend(Path(folder_path).glob(f'*{ext}'))
            
            if not tiff_files:
                self.logger.warning("No TIFF files found in selected folder")
                messagebox.showwarning("Warning", "No TIFF files found in selected folder")
                return
            
            self.logger.info(f"Found {len(tiff_files)} TIFF files")
            
            # Update batch preview
            self.batch_preview_frame.update_preview(tiff_files)
            
            # Set default output folder
            if not self.output_path_var.get():
                output_folder = str(Path(folder_path) / "PNG_Output")
                self.output_path_var.set(output_folder)
                self.logger.info(f"Set default output folder: {output_folder}")
            
        except Exception as e:
            self.logger.error(f"Failed to load batch files: {str(e)}")
            messagebox.showerror("Error", f"Failed to load batch files: {str(e)}")

    def update_estimated_size(self, img, input_size):
        """Update estimated output size based on current settings"""
        try:
            # Get current settings
            scale = self.settings_frame.scale_var.get() / 100
            optimize = self.settings_frame.optimize_var.get()
            resolution = img.size
            # Calculate output resolution
            selected = self.settings_frame.resolution_var.get()
            if selected != "Custom" and self.image_processor.standard_resolutions.get(selected):
                target_width, target_height = self.image_processor.standard_resolutions[selected]
                if self.settings_frame.fill_mode_var.get():
                    output_resolution = f"{target_width} x {target_height} pixels"
                else:
                    output_resolution = f"{int(resolution[0]*scale)} x {int(resolution[1]*scale)} pixels"
            else:
                output_resolution = f"{int(resolution[0]*scale)} x {int(resolution[1]*scale)} pixels"
            # Calculate estimated size
            estimated_size = self.image_processor.estimate_png_size(
                img, optimize, scale
            )
            # Calculate compression ratio
            compression_ratio = estimated_size / input_size
            self.logger.info(f"Estimated output size: {self.image_processor.format_size(estimated_size)} "
                           f"(Compression ratio: {compression_ratio:.1f}x)")
            # Update info frame
            self.info_frame.update_output_info(
                self.output_path_var.get(),
                self.image_processor.format_size(estimated_size),
                output_resolution,
                compression_ratio
            )
        except Exception as e:
            self.logger.error(f"Error updating estimated size: {str(e)}")

    def start_conversion(self):
        """Start the conversion process"""
        if self.mode_var.get() == "single":
            self.convert_single_file()
        else:
            self.convert_batch_files()

    def convert_single_file(self):
        """Convert a single file"""
        input_path = self.input_path_var.get()
        output_path = self.output_path_var.get()
        
        if not input_path or not output_path:
            self.logger.warning("Input or output path not specified")
            messagebox.showwarning("Warning", "Please select input and output files")
            return
        
        try:
            # Get settings
            settings = self.get_conversion_settings()
            self.logger.info("Starting single file conversion")
            self.logger.debug(f"Conversion settings: {settings}")
            
            # Process image
            self.status_var.set("Converting...")
            self.progress_var.set(0)
            self.root.update()
            
            # Load and process image
            self.logger.debug(f"Loading image: {input_path}")
            img = Image.open(input_path)
            processed_img = self.image_processor.process_image(img, **settings)
            
            # Save image
            self.logger.debug(f"Saving image: {output_path}")
            save_kwargs = {
                'optimize': settings.get('optimize', True),
                'interlace': settings.get('interlace', False),
                'filter_method': settings.get('filter_method', 'auto')
            }
            self.image_processor.save_image(processed_img, output_path, **save_kwargs)
            
            # Update preview
            self.preview_frame.update_output_preview(processed_img)
            
            # Update status
            self.status_var.set("Conversion complete")
            self.progress_var.set(100)
            
            self.logger.info("File converted successfully")
            messagebox.showinfo("Success", "File converted successfully")
            
            # Update live output preview after conversion
            self.update_live_output_preview(img)
            
        except Exception as e:
            self.logger.error(f"Conversion failed: {str(e)}")
            messagebox.showerror("Error", f"Conversion failed: {str(e)}")
            self.status_var.set("Conversion failed")

    def convert_batch_files(self):
        """Convert multiple files in batch mode"""
        input_folder = self.input_path_var.get()
        output_folder = self.output_path_var.get()
        
        if not input_folder or not output_folder:
            self.logger.warning("Input or output folder not specified")
            messagebox.showwarning("Warning", "Please select input and output folders")
            return
        
        try:
            # Create output folder if it doesn't exist
            os.makedirs(output_folder, exist_ok=True)
            self.logger.info(f"Created output folder: {output_folder}")
            
            # Get all TIFF files
            tiff_files = []
            for ext in ('.tif', '.tiff'):
                tiff_files.extend(Path(input_folder).glob(f'*{ext}'))
            
            if not tiff_files:
                self.logger.warning("No TIFF files found in selected folder")
                messagebox.showwarning("Warning", "No TIFF files found in selected folder")
                return
            
            # Get settings
            settings = self.get_conversion_settings()
            self.logger.info(f"Starting batch conversion of {len(tiff_files)} files")
            self.logger.debug(f"Conversion settings: {settings}")
            
            # Start conversion
            self.status_var.set("Converting...")
            self.progress_var.set(0)
            self.root.update()
            
            # Process each file
            successful = 0
            failed = 0
            
            for i, file_path in enumerate(tiff_files):
                try:
                    # Generate output filename
                    root_name = self.batch_root_var.get()
                    output_name = f"{root_name}_{i+1:02d}.png"
                    output_path = Path(output_folder) / output_name
                    
                    self.logger.debug(f"Converting file {i+1}/{len(tiff_files)}: {file_path}")
                    
                    # Load and process image
                    img = Image.open(file_path)
                    processed_img = self.image_processor.process_image(img, **settings)
                    
                    # Save image
                    self.logger.debug(f"Saving image: {output_path}")
                    save_kwargs = {
                        'optimize': settings.get('optimize', True),
                        'interlace': settings.get('interlace', False),
                        'filter_method': settings.get('filter_method', 'auto')
                    }
                    self.image_processor.save_image(processed_img, output_path, **save_kwargs)
                    
                    successful += 1
                    self.logger.debug(f"Successfully converted: {output_path}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to convert {file_path}: {str(e)}")
                    failed += 1
                
                # Update progress
                progress = (i + 1) / len(tiff_files) * 100
                self.progress_var.set(progress)
                self.status_var.set(f"Converting... ({i+1}/{len(tiff_files)})")
                self.root.update()
            
            # Show completion message
            if failed == 0:
                self.logger.info(f"Batch conversion completed successfully: {successful} files converted")
                messagebox.showinfo("Success", f"Successfully converted {successful} files")
            else:
                self.logger.warning(f"Batch conversion completed with {failed} failures: {successful} files converted")
                messagebox.showwarning("Warning",
                                     f"Conversion complete with {failed} failures\n"
                                     f"Successfully converted {successful} files")
            
            self.status_var.set("Batch conversion complete")
            
        except Exception as e:
            self.logger.error(f"Batch conversion failed: {str(e)}")
            messagebox.showerror("Error", f"Batch conversion failed: {str(e)}")
            self.status_var.set("Batch conversion failed")

    def get_conversion_settings(self):
        selected = self.settings_frame.resolution_var.get()
        standard_res = self.image_processor.standard_resolutions
        # Use manual resolution if fill mode is enabled and both manual fields are > 0
        manual_w = getattr(self.settings_frame, 'manual_width_var', None)
        manual_h = getattr(self.settings_frame, 'manual_height_var', None)
        fill_mode = self.settings_frame.fill_mode_var.get()
        manual_res = None
        if fill_mode and manual_w and manual_h:
            w = manual_w.get()
            h = manual_h.get()
            if w > 0 and h > 0:
                manual_res = (w, h)
        return {
            'scale_factor': self.settings_frame.scale_var.get() / 100,
            'target_resolution': manual_res if manual_res else (standard_res[selected] if selected != "Custom" else None),
            'fill_mode': fill_mode,
            'optimize': self.settings_frame.optimize_var.get(),
            'color_mode': self.settings_frame.color_mode_var.get(),
            'dither_method': self.settings_frame.dither_var.get(),
            'filter_method': self.settings_frame.filter_var.get(),
            'interlace': self.settings_frame.interlace_var.get()
        }

    def on_path_change(self, *args):
        """Update info and preview when input or output path changes"""
        input_path = self.input_path_var.get()
        output_path = self.output_path_var.get()
        if input_path:
            try:
                img = Image.open(input_path)
                file_size = os.path.getsize(input_path)
                self.info_frame.update_input_info(
                    input_path,
                    self.image_processor.format_size(file_size),
                    img.size
                )
                # Calculate crop box if fill mode is enabled and target_resolution is set
                crop_box = None
                settings = self.get_conversion_settings()
                if settings['fill_mode'] and settings['target_resolution']:
                    img_w, img_h = img.size
                    target_w, target_h = settings['target_resolution']
                    scale_factor = settings['scale_factor']
                    scaled_w = int(img_w * scale_factor)
                    scaled_h = int(img_h * scale_factor)
                    left = (scaled_w - target_w) // 2
                    top = (scaled_h - target_h) // 2
                    right = left + target_w
                    bottom = top + target_h
                    inv_scale = 1.0 / scale_factor if scale_factor != 0 else 1.0
                    crop_box = (
                        left * inv_scale,
                        top * inv_scale,
                        right * inv_scale,
                        bottom * inv_scale
                    )
                self.preview_frame.update_input_preview(img, crop_box)
                # Update output info and preview if output path is set
                if output_path:
                    self.update_estimated_size(img, file_size)
                    self.update_live_output_preview(img)
            except Exception as e:
                self.logger.error(f"Error updating input info/preview: {str(e)}")
        else:
            self.info_frame.update_input_info(None, None, None)
            self.preview_frame.update_input_preview(None)
            self.info_frame.update_output_info(None, None, None)
            self.preview_frame.update_output_preview(None)

    def update_live_output_preview(self, img):
        """Show a live preview of the output image with current settings"""
        try:
            settings = self.get_conversion_settings()
            self.logger.debug(f"Processing image for live output preview with settings: {settings}")
            processed_img = self.image_processor.process_image(img, **settings)
            if processed_img is None:
                self.logger.error("Processed image is None in live output preview.")
            self.preview_frame.update_output_preview(processed_img)
        except Exception as e:
            self.logger.error(f"Error updating live output preview: {str(e)}")
            self.preview_frame.update_output_preview(None)

    def on_settings_change(self, *args):
        """Update info and preview when any settings variable changes"""
        input_path = self.input_path_var.get()
        output_path = self.output_path_var.get()
        if input_path and output_path:
            try:
                img = Image.open(input_path)
                file_size = os.path.getsize(input_path)
                # Calculate crop box if fill mode is enabled and target_resolution is set
                crop_box = None
                settings = self.get_conversion_settings()
                if settings['fill_mode'] and settings['target_resolution']:
                    img_w, img_h = img.size
                    target_w, target_h = settings['target_resolution']
                    scale_factor = settings['scale_factor']
                    scaled_w = int(img_w * scale_factor)
                    scaled_h = int(img_h * scale_factor)
                    left = (scaled_w - target_w) // 2
                    top = (scaled_h - target_h) // 2
                    right = left + target_w
                    bottom = top + target_h
                    inv_scale = 1.0 / scale_factor if scale_factor != 0 else 1.0
                    crop_box = (
                        left * inv_scale,
                        top * inv_scale,
                        right * inv_scale,
                        bottom * inv_scale
                    )
                self.update_estimated_size(img, file_size)
                self.update_live_output_preview(img)
                self.preview_frame.update_input_preview(img, crop_box)
            except Exception as e:
                self.logger.error(f"Error updating info/preview on settings change: {str(e)}")

    def on_save_to_folder_change(self):
        """Update output path when the save-to-folder checkbox changes"""
        input_path = self.input_path_var.get()
        if input_path:
            self.autofill_output_path(input_path)

    def autofill_output_path(self, input_path):
        """Autofill the output file path based on input and checkbox state"""
        if not input_path:
            return
        input_path = Path(input_path)
        input_dir = input_path.parent
        input_name = input_path.stem
        if self.save_to_folder_var.get():
            output_dir = input_dir / "PNG_Output"
        else:
            output_dir = input_dir
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{input_name}.png"
        self.output_path_var.set(str(output_file))

    def on_crop_update(self, crop_box):
        """Callback when the crop box is moved. Update the output preview live."""
        try:
            if self.preview_frame.last_image and crop_box:
                # Crop the image to the new box and update output preview
                cropped = self.preview_frame.last_image.crop(tuple(map(int, crop_box)))
                # Optionally, apply any scaling or processing as in live preview
                self.preview_frame.update_output_preview(cropped)
        except Exception as e:
            self.logger.error(f"Error updating output preview on crop: {str(e)}")
            self.preview_frame.update_output_preview(None)

    def run(self):
        """Start the application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = TIFFtoPNGConverter()
    app.run() 