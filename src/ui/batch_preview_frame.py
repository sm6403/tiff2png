import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class BatchPreviewFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Grid frame for previews
        self.grid_frame = ttk.Frame(self)
        self.grid_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Navigation frame
        nav_frame = ttk.Frame(self)
        nav_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        nav_frame.grid_columnconfigure(1, weight=1)
        
        # Select/Deselect All buttons frame (now below navigation)
        select_frame = ttk.Frame(self)
        select_frame.grid(row=2, column=0, columnspan=2, sticky=tk.N, pady=(0, 5))
        self.select_all_btn = ttk.Button(select_frame, text="Select All", command=self.select_all)
        self.select_all_btn.grid(row=0, column=0, padx=(0, 2))
        self.deselect_all_btn = ttk.Button(select_frame, text="Deselect All", command=self.deselect_all)
        self.deselect_all_btn.grid(row=0, column=1)
        
        # Previous page button
        self.prev_page_btn = ttk.Button(nav_frame, text="← Previous", command=self.prev_page)
        self.prev_page_btn.grid(row=0, column=0, padx=5)
        
        # Page info label
        self.page_info_var = tk.StringVar(value="Page 1 of 1")
        ttk.Label(nav_frame, textvariable=self.page_info_var).grid(row=0, column=1)
        
        # Next page button
        self.next_page_btn = ttk.Button(nav_frame, text="Next →", command=self.next_page)
        self.next_page_btn.grid(row=0, column=2, padx=5)
        
        # Store preview images and state
        self.preview_images = []
        self.current_page = 0
        self.images_per_page = 12  # 2x6 grid
        self.batch_files = []
        self.checkbox_vars = []  # Store BooleanVars for checkboxes

    def update_preview(self, batch_files):
        """Update the batch preview with new files"""
        self.batch_files = batch_files
        self.current_page = 0
        # Reset checkbox vars for new batch
        self.checkbox_vars = [tk.BooleanVar(value=True) for _ in batch_files]
        self.update_grid()

    def update_grid(self):
        """Update the preview grid"""
        # Clear existing preview labels
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.preview_images = []  # Clear previous image references
        if not self.batch_files:
            return
        
        # Set tighter preview size
        preview_width, preview_height = 140, 105
        cols = 2
        rows = 6
        # Calculate start and end indices for current page
        start_idx = self.current_page * self.images_per_page
        end_idx = min(start_idx + self.images_per_page, len(self.batch_files))
        # Update page info
        total_pages = (len(self.batch_files) + self.images_per_page - 1) // self.images_per_page
        self.page_info_var.set(f"Page {self.current_page + 1} of {total_pages}")
        # Enable/disable navigation buttons
        self.prev_page_btn.state(['!disabled' if self.current_page > 0 else 'disabled'])
        self.next_page_btn.state(['!disabled' if self.current_page < total_pages - 1 else 'disabled'])
        # Create grid of previews
        for i, tiff_file in enumerate(self.batch_files[start_idx:end_idx]):
            row = i % rows
            col = i // rows
            # Create frame for each preview
            preview_frame = ttk.Frame(self.grid_frame)
            preview_frame.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E, tk.N, tk.S))
            preview_frame.grid_columnconfigure(0, weight=1)
            preview_frame.grid_rowconfigure(0, weight=1)
            # Create canvas for preview and checkbox overlay
            canvas = tk.Canvas(preview_frame, width=preview_width, height=preview_height, highlightthickness=0)
            canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            # Create label for preview
            preview_label = ttk.Label(canvas)
            canvas.create_window(0, 0, anchor=tk.NW, window=preview_label)
            # Add checkbox for selection (positioned in top-left corner)
            file_idx = start_idx + i
            cb_var = self.checkbox_vars[file_idx]
            checkbox = ttk.Checkbutton(canvas, variable=cb_var)
            canvas.create_window(5, 5, anchor=tk.NW, window=checkbox)
            # Add filename label
            filename_label = ttk.Label(preview_frame, text=tiff_file.name, wraplength=preview_width)
            filename_label.grid(row=1, column=0, pady=(2, 0))
            try:
                # Load and resize image for preview
                with Image.open(tiff_file) as img:
                    # Fit image inside preview box, maintaining aspect ratio
                    img.thumbnail((preview_width, preview_height), Image.Resampling.LANCZOS)
                    # Center image in the canvas
                    img_w, img_h = img.size
                    x = (preview_width - img_w) // 2
                    y = (preview_height - img_h) // 2
                    photo = ImageTk.PhotoImage(img)
                    self.preview_images.append(photo)  # Keep reference
                    preview_label.configure(image=photo)
                    canvas.coords(canvas.create_window(x, y, anchor=tk.NW, window=preview_label), x, y)
            except Exception as e:
                preview_label.configure(text=f"Error loading preview:\n{str(e)}")

    def prev_page(self):
        """Go to previous page of previews"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_grid()

    def next_page(self):
        """Go to next page of previews"""
        total_pages = (len(self.batch_files) + self.images_per_page - 1) // self.images_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_grid()

    def get_selected_files(self):
        """Return a list of batch_files that are checked for conversion"""
        return [f for f, var in zip(self.batch_files, self.checkbox_vars) if var.get()]

    def select_all(self):
        """Check all checkboxes"""
        for var in self.checkbox_vars:
            var.set(True)

    def deselect_all(self):
        """Uncheck all checkboxes"""
        for var in self.checkbox_vars:
            var.set(False) 