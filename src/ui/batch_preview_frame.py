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
        self.grid_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Navigation frame
        nav_frame = ttk.Frame(self)
        nav_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        nav_frame.grid_columnconfigure(1, weight=1)
        
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
        self.images_per_page = 10  # 5x2 grid
        self.batch_files = []

    def update_preview(self, batch_files):
        """Update the batch preview with new files"""
        self.batch_files = batch_files
        self.current_page = 0
        self.update_grid()

    def update_grid(self):
        """Update the preview grid"""
        # Clear existing preview labels
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        
        if not self.batch_files:
            return
        
        # Calculate grid dimensions
        cols = 2
        rows = 5
        
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
            preview_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
            preview_frame.grid_columnconfigure(0, weight=1)
            preview_frame.grid_rowconfigure(0, weight=1)
            
            # Create label for preview
            preview_label = ttk.Label(preview_frame)
            preview_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Add filename label
            filename_label = ttk.Label(preview_frame, text=tiff_file.name, wraplength=150)
            filename_label.grid(row=1, column=0, pady=2)
            
            try:
                # Load and resize image for preview
                with Image.open(tiff_file) as img:
                    # Calculate preview size (maintain aspect ratio)
                    preview_size = (200, 200)
                    img.thumbnail(preview_size, Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    photo = ImageTk.PhotoImage(img)
                    
                    # Store reference and update label
                    self.preview_images.append(photo)  # Keep reference
                    preview_label.configure(image=photo)
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