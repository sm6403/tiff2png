from PIL import Image

__version__ = "0.2.0"

MAX_IMAGE_PIXELS = 500_000_000

# Pillow warns above the limit and raises above twice the limit: error beyond 1000 megapixels.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
