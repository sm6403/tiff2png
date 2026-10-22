import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw

class PreviewFrame(ttk.Frame):
    def __init__(self, parent, on_crop_update=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.on_crop_update = on_crop_update
        self.crop_box = None  # (left, top, right, bottom) in original image coordinates
        self.dragging = False
        self.drag_offset = (0, 0)
        self.image_size = None
        self.last_image = None
        self.preview_image = None  # Store the base preview image without crop box
        self.resize_handle = None  # Current handle being dragged (None, 'nw', 'ne', 'sw', 'se')
        self.handle_size = 8  # Size of resize handles in pixels
        self.move_step = 5  # Pixels to move with arrow keys
        
        # Configure grid for vertical stacking
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        
        # Input preview label
        self.input_label = ttk.Label(self, text="Input Preview")
        self.input_label.grid(row=0, column=0, pady=(5, 0))
        
        # Input preview image
        self.input_preview_label = ttk.Label(self, text="No image selected")
        self.input_preview_label.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Output preview label
        self.output_label = ttk.Label(self, text="Output Preview")
        self.output_label.grid(row=2, column=0, pady=(10, 0))
        
        # Output preview image
        self.output_preview_label = ttk.Label(self, text="No output yet")
        self.output_preview_label.grid(row=3, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Store PhotoImage objects
        self.input_photo = None
        self.output_photo = None
        
        # Mouse event bindings for crop box
        self.input_preview_label.bind('<Button-1>', self._on_mouse_down)
        self.input_preview_label.bind('<B1-Motion>', self._on_mouse_drag)
        self.input_preview_label.bind('<ButtonRelease-1>', self._on_mouse_up)
        
        # Keyboard bindings for fine control
        self.input_preview_label.bind('<Key>', self._on_key_press)
        self.input_preview_label.focus_set()  # Enable keyboard focus

    def _get_handle_at(self, x, y):
        """Return which resize handle is at the given coordinates, or None"""
        if not self.crop_box:
            return None
            
        # Convert to preview coordinates
        px = int(x / self._preview_scale)
        py = int(y / self._preview_scale)
        l, t, r, b = self.crop_box
        
        # Check each corner
        if abs(px - l) <= self.handle_size and abs(py - t) <= self.handle_size:
            return 'nw'
        if abs(px - r) <= self.handle_size and abs(py - t) <= self.handle_size:
            return 'ne'
        if abs(px - l) <= self.handle_size and abs(py - b) <= self.handle_size:
            return 'sw'
        if abs(px - r) <= self.handle_size and abs(py - b) <= self.handle_size:
            return 'se'
        return None

    def _on_mouse_down(self, event):
        if not self.crop_box or not self.image_size:
            return
            
        # Get the label's position relative to the window
        label_x = self.input_preview_label.winfo_x()
        label_y = self.input_preview_label.winfo_y()
        
        # Adjust event coordinates relative to the label
        x = event.x - label_x
        y = event.y - label_y
        
        # Convert to image coordinates
        x = int(x / self._preview_scale)
        y = int(y / self._preview_scale)
        l, t, r, b = self.crop_box
        
        # Check for resize handles first
        self.resize_handle = self._get_handle_at(event.x - label_x, event.y - label_y)
        if self.resize_handle:
            self.dragging = True
            return
            
        # Check if inside crop box
        if l <= x <= r and t <= y <= b:
            self.dragging = True
            self.drag_offset = (x - l, y - t)

    def _on_mouse_drag(self, event):
        if not self.dragging or not self.crop_box or not self.image_size:
            return
            
        # Get the label's position relative to the window
        label_x = self.input_preview_label.winfo_x()
        label_y = self.input_preview_label.winfo_y()
        
        # Adjust event coordinates relative to the label
        x = event.x - label_x
        y = event.y - label_y
        
        img_w, img_h = self.image_size
        x = int(x / self._preview_scale)
        y = int(y / self._preview_scale)
        
        if self.resize_handle:
            # Handle resizing
            l, t, r, b = self.crop_box
            if 'n' in self.resize_handle:
                t = max(0, min(y, b - 10))
            if 's' in self.resize_handle:
                b = min(img_h, max(y, t + 10))
            if 'w' in self.resize_handle:
                l = max(0, min(x, r - 10))
            if 'e' in self.resize_handle:
                r = min(img_w, max(x, l + 10))
            self.crop_box = (l, t, r, b)
        else:
            # Handle moving
            box_w = self.crop_box[2] - self.crop_box[0]
            box_h = self.crop_box[3] - self.crop_box[1]
            new_l = max(0, min(x - self.drag_offset[0], img_w - box_w))
            new_t = max(0, min(y - self.drag_offset[1], img_h - box_h))
            new_r = new_l + box_w
            new_b = new_t + box_h
            self.crop_box = (new_l, new_t, new_r, new_b)
            
        # Update the crop box overlay
        self._draw_crop_box()

    def _on_mouse_up(self, event):
        if self.dragging:
            self.dragging = False
            self.resize_handle = None
            # Now that drag is complete, update the output preview
            if self.on_crop_update:
                self.on_crop_update(self.crop_box)

    def _on_key_press(self, event):
        """Handle keyboard controls for fine-tuning crop box position"""
        if not self.crop_box or not self.image_size:
            return
            
        img_w, img_h = self.image_size
        l, t, r, b = self.crop_box
        box_w = r - l
        box_h = b - t
        
        # Calculate movement step in original image coordinates
        step = int(self.move_step / self._preview_scale)
        
        if event.keysym == 'Up':
            new_t = max(0, t - step)
            new_b = new_t + box_h
            self.crop_box = (l, new_t, r, new_b)
        elif event.keysym == 'Down':
            new_b = min(img_h, b + step)
            new_t = new_b - box_h
            self.crop_box = (l, new_t, r, new_b)
        elif event.keysym == 'Left':
            new_l = max(0, l - step)
            new_r = new_l + box_w
            self.crop_box = (new_l, t, new_r, b)
        elif event.keysym == 'Right':
            new_r = min(img_w, r + step)
            new_l = new_r - box_w
            self.crop_box = (new_l, t, new_r, b)
            
        self._draw_crop_box()
        if self.on_crop_update:
            self.on_crop_update(self.crop_box)

    def _draw_crop_box(self):
        """Draw the crop box overlay on the preview image"""
        if not self.preview_image or not self.crop_box:
            return
            
        # Create a copy of the preview image for drawing
        preview_copy = self.preview_image.copy()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(preview_copy)
        
        # Scale crop box coordinates to preview size
        left, top, right, bottom = self.crop_box
        left = int(left * self._preview_scale)
        top = int(top * self._preview_scale)
        right = int(right * self._preview_scale)
        bottom = int(bottom * self._preview_scale)
        
        # Draw semi-transparent overlay
        overlay = Image.new('RGBA', preview_copy.size, (0, 0, 0, 128))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([0, 0, preview_copy.size[0], preview_copy.size[1]], fill=(0, 0, 0, 128))
        draw_overlay.rectangle([left, top, right, bottom], fill=(0, 0, 0, 0))
        preview_copy = Image.alpha_composite(preview_copy.convert('RGBA'), overlay)
        
        # Draw the crop box
        draw = ImageDraw.Draw(preview_copy)
        draw.rectangle([left, top, right, bottom], outline='red', width=2)
        
        # Draw resize handles
        handle_color = 'white'
        handle_outline = 'red'
        handle_size = int(self.handle_size * self._preview_scale)
        
        # Draw handles at corners
        for x, y in [(left, top), (right, top), (left, bottom), (right, bottom)]:
            draw.rectangle(
                [x - handle_size//2, y - handle_size//2,
                 x + handle_size//2, y + handle_size//2],
                fill=handle_color, outline=handle_outline
            )
        
        # Update the preview
        photo = ImageTk.PhotoImage(preview_copy)
        self.input_preview_label.configure(image=photo, text="")
        self.input_photo = photo

    def update_input_preview(self, image, crop_box=None):
        """Update the input preview with a new image and optional crop box overlay"""
        try:
            self.last_image = image
            if image:
                self.image_size = image.size
                # Create and store the base preview image
                self.preview_image = self.resize_image(image)
                self._preview_scale = min(400 / image.size[0], 400 / image.size[1])
                
                # Draw crop box if provided
                if crop_box:
                    self.crop_box = crop_box
                    self._draw_crop_box()
                else:
                    self.crop_box = None
                    photo = ImageTk.PhotoImage(self.preview_image)
                    self.input_preview_label.configure(image=photo, text="")
                    self.input_photo = photo
            else:
                self.input_preview_label.configure(image=None, text="No image selected")
                self.input_photo = None
                self.preview_image = None
        except Exception as e:
            self.input_preview_label.configure(image=None, text=f"Error loading preview: {str(e)}")
            self.input_photo = None
            self.preview_image = None

    def update_output_preview(self, image):
        """Update the output preview with a new image"""
        try:
            if image:
                preview_img = self.resize_image(image)
                photo = ImageTk.PhotoImage(preview_img)
                self.output_preview_label.configure(image=photo, text="")
                self.output_photo = photo
            else:
                self.output_preview_label.configure(image=None, text="No output yet")
                self.output_photo = None
        except Exception as e:
            self.output_preview_label.configure(image=None, text=f"Error loading preview: {str(e)}")
            self.output_photo = None

    def resize_image(self, image, max_size=(400, 400)):
        """Resize image maintaining aspect ratio"""
        ratio = min(max_size[0]/image.size[0], max_size[1]/image.size[1])
        new_size = tuple(int(dim * ratio) for dim in image.size)
        return image.resize(new_size, Image.Resampling.LANCZOS) 