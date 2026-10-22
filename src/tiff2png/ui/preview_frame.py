import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from tiff2png.core.geometry import Box, clamp_box

DISPLAY_MAX = 400
HANDLE_PX = 8
MIN_BOX_PX = 12
KEY_STEP_PX = 5
SHIFT_MASK = 0x1
CORNERS = {"nw": (-1, -1), "ne": (1, -1), "sw": (-1, 1), "se": (1, 1)}
ARROWS = {"Left": (-1, 0), "Right": (1, 0), "Up": (0, -1), "Down": (0, 1)}


class PreviewFrame(ttk.Frame):
    def __init__(self, parent, on_crop_update=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_crop_update = on_crop_update
        self.crop_box = None
        self.aspect = None
        self.source_size = None
        self.display_scale = 1.0
        self._drag = None
        self.input_photo = None
        self.output_photo = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)

        ttk.Label(self, text="Input Preview").grid(row=0, column=0, pady=(5, 0))

        self.input_text = ttk.Label(self, text="No image selected")
        self.input_text.grid(row=1, column=0, padx=5, pady=5)
        self.canvas = tk.Canvas(self, width=1, height=1, highlightthickness=0, borderwidth=0)
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Key>", self._on_key_press)

        ttk.Label(self, text="Output Preview").grid(row=2, column=0, pady=(10, 0))
        self.output_preview_label = ttk.Label(self, text="No output yet")
        self.output_preview_label.grid(row=3, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))

    def set_input_image(self, image, source_size):
        """Show a proxy of the source and reset the crop overlay."""
        self.source_size = source_size
        fit = min(DISPLAY_MAX / image.width, DISPLAY_MAX / image.height)
        shown = (max(1, round(image.width * fit)), max(1, round(image.height * fit)))
        self.display_scale = shown[0] / source_size[0]
        self.input_photo = ImageTk.PhotoImage(image.resize(shown, Image.Resampling.LANCZOS))
        self.canvas.delete("all")
        self.canvas.configure(width=shown[0], height=shown[1])
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.input_photo, tags="photo")
        for index in range(4):
            self.canvas.create_rectangle(0, 0, 0, 0, fill="black", stipple="gray50",
                                         outline="", tags=("crop", f"shade{index}"))
        self.canvas.create_rectangle(0, 0, 0, 0, outline="red", width=2, tags=("crop", "box"))
        for corner in CORNERS:
            self.canvas.create_rectangle(0, 0, 0, 0, fill="white", outline="red",
                                         tags=("crop", f"handle_{corner}"))
        self.input_text.grid_remove()
        self.canvas.grid(row=1, column=0, padx=5, pady=5)
        self.crop_box = None
        self._drag = None
        self._draw_box()

    def clear_input(self):
        self.source_size = None
        self.crop_box = None
        self.aspect = None
        self._drag = None
        self.input_photo = None
        self.canvas.delete("all")
        self.canvas.grid_remove()
        self.input_text.grid()

    def set_crop_overlay(self, box, aspect):
        """Show box (source coordinates) or hide the overlay when box is None."""
        self.crop_box = None if box is None else Box(*box)
        self.aspect = aspect
        self._drag = None
        self._draw_box()

    def to_display(self, box):
        return box.scaled(self.display_scale).as_tuple()

    def _draw_box(self):
        if self.crop_box is None or self.source_size is None:
            self.canvas.itemconfigure("crop", state="hidden")
            return
        self.canvas.itemconfigure("crop", state="normal")
        left, top, right, bottom = self.to_display(self.crop_box)
        width = self.source_size[0] * self.display_scale
        height = self.source_size[1] * self.display_scale
        shades = [(0, 0, width, top), (0, bottom, width, height),
                  (0, top, left, bottom), (right, top, width, bottom)]
        for index, rect in enumerate(shades):
            self.canvas.coords(f"shade{index}", *rect)
        self.canvas.coords("box", left, top, right, bottom)
        half = HANDLE_PX / 2
        for name, (x, y) in self._display_corners().items():
            self.canvas.coords(f"handle_{name}", x - half, y - half, x + half, y + half)

    def _display_corners(self):
        left, top, right, bottom = self.to_display(self.crop_box)
        return {"nw": (left, top), "ne": (right, top), "sw": (left, bottom), "se": (right, bottom)}

    def _active(self):
        return self.crop_box is not None and self.source_size is not None and bool(self.aspect)

    def _to_source(self, event):
        return event.x / self.display_scale, event.y / self.display_scale

    def _handle_at(self, event):
        for name, (x, y) in self._display_corners().items():
            if abs(event.x - x) <= HANDLE_PX and abs(event.y - y) <= HANDLE_PX:
                return name
        return None

    def _on_mouse_down(self, event):
        self.canvas.focus_set()
        if not self._active():
            return
        handle = self._handle_at(event)
        if handle is not None:
            self._drag = ("resize", handle)
            return
        x, y = self._to_source(event)
        box = self.crop_box
        if box.left <= x <= box.right and box.top <= y <= box.bottom:
            self._drag = ("move", (x - box.left, y - box.top))

    def _on_mouse_drag(self, event):
        if self._drag is None or not self._active():
            return
        x, y = self._to_source(event)
        kind, detail = self._drag
        if kind == "move":
            self.crop_box = self._moved_to(x - detail[0], y - detail[1])
        else:
            self.crop_box = self._resized_to(detail, x, y)
        self._draw_box()

    def _on_mouse_up(self, event):
        if self._drag is None:
            return
        self._drag = None
        self._notify()

    def _moved_to(self, left, top):
        width, height = self.crop_box.width, self.crop_box.height
        src_w, src_h = self.source_size
        left = max(0.0, min(left, src_w - width))
        top = max(0.0, min(top, src_h - height))
        return Box(left, top, left + width, top + height)

    def _resized_to(self, handle, x, y):
        sign_x, sign_y = CORNERS[handle]
        box = self.crop_box
        anchor_x = box.right if sign_x < 0 else box.left
        anchor_y = box.bottom if sign_y < 0 else box.top
        src_w, src_h = self.source_size
        room_x = anchor_x if sign_x < 0 else src_w - anchor_x
        room_y = anchor_y if sign_y < 0 else src_h - anchor_y
        wanted_w = (x - anchor_x) * sign_x
        wanted_h = (y - anchor_y) * sign_y
        min_w = MIN_BOX_PX / self.display_scale
        width = max(min_w, min(wanted_w, wanted_h * self.aspect))
        width = min(width, room_x, room_y * self.aspect)
        height = width / self.aspect
        other_x = anchor_x + sign_x * width
        other_y = anchor_y + sign_y * height
        return Box(min(anchor_x, other_x), min(anchor_y, other_y),
                   max(anchor_x, other_x), max(anchor_y, other_y))

    def _on_key_press(self, event):
        if not self._active() or event.keysym not in ARROWS:
            return
        step = max(1.0, KEY_STEP_PX / self.display_scale)
        step_x, step_y = ARROWS[event.keysym]
        box = self.crop_box
        if event.state & SHIFT_MASK:
            grow = step * (step_x - step_y)
            width = max(MIN_BOX_PX / self.display_scale, box.width + 2 * grow)
            height = width / self.aspect
            centre_x = (box.left + box.right) / 2
            centre_y = (box.top + box.bottom) / 2
            wanted = Box(centre_x - width / 2, centre_y - height / 2,
                         centre_x + width / 2, centre_y + height / 2)
            self.crop_box = clamp_box(wanted, self.source_size, self.aspect)
        else:
            self.crop_box = self._moved_to(box.left + step_x * step, box.top + step_y * step)
        self._draw_box()
        self._notify()

    def _notify(self):
        if self.on_crop_update:
            self.on_crop_update(self.crop_box.as_tuple())

    def update_output_preview(self, image):
        """Update the output preview with a new image."""
        try:
            if image:
                fit = min(DISPLAY_MAX / image.width, DISPLAY_MAX / image.height)
                size = (max(1, round(image.width * fit)), max(1, round(image.height * fit)))
                photo = ImageTk.PhotoImage(image.resize(size, Image.Resampling.LANCZOS))
                self.output_preview_label.configure(image=photo, text="")
                self.output_photo = photo
            else:
                self.output_preview_label.configure(image="", text="No output yet")
                self.output_photo = None
        except (ValueError, OSError, tk.TclError) as error:
            self.output_preview_label.configure(image="", text=f"Error loading preview: {error}")
            self.output_photo = None
