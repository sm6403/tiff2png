from PIL import Image, ImageDraw
import os
import math

class ImageProcessor:
    def __init__(self):
        self.standard_resolutions = {
            "Custom": None,
            "4K (3840x2160)": (3840, 2160),
            "2K (2560x1440)": (2560, 1440),
            "Full HD (1920x1080)": (1920, 1080),
            "HD (1280x720)": (1280, 720),
            "SVGA (800x600)": (800, 600),
            "VGA (640x480)": (640, 480)
        }

    def format_size(self, size_bytes):
        """Convert size in bytes to human readable format"""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def estimate_png_size(self, img, optimize, scale_factor=1.0):
        """Estimate PNG file size based on image properties and compression settings"""
        # Calculate scaled dimensions
        width, height = img.size
        scaled_width = int(width * scale_factor)
        scaled_height = int(height * scale_factor)
        
        # Base estimation on scaled dimensions and color depth
        if img.mode in ('RGBA', 'LA'):
            bytes_per_pixel = 4
        elif img.mode == 'RGB':
            bytes_per_pixel = 3
        else:
            bytes_per_pixel = 1
        
        # Calculate raw size with scaling
        raw_size = scaled_width * scaled_height * bytes_per_pixel
        
        # Apply optimization factor
        if optimize:
            estimated_size = raw_size * 0.8  # 20% reduction with optimization
        else:
            estimated_size = raw_size
        
        return max(estimated_size, 1024)  # Minimum 1KB

    def calculate_crop_box(self, img, target_width, target_height, scale_factor):
        """Calculate crop box for fill mode"""
        scaled_width = int(img.size[0] * scale_factor)
        scaled_height = int(img.size[1] * scale_factor)
        
        # Calculate crop box to center the image
        left = (scaled_width - target_width) // 2
        top = (scaled_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height
        
        return (left, top, right, bottom)

    def create_preview_with_crop(self, img, crop_box=None, preview_size=(400, 400)):
        """Create a preview image with optional crop box overlay"""
        try:
            # Create a copy of the image
            preview_img = img.copy()
            
            # Calculate scale factor for preview
            scale_factor = min(preview_size[0] / preview_img.size[0],
                             preview_size[1] / preview_img.size[1])
            
            # Scale the image for preview
            preview_width = int(preview_img.size[0] * scale_factor)
            preview_height = int(preview_img.size[1] * scale_factor)
            preview_img = preview_img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
            
            # If we have crop coordinates, draw the crop box
            if crop_box:
                left, top, right, bottom = crop_box
                # Scale the crop coordinates to match the preview size
                left = int(left * scale_factor)
                top = int(top * scale_factor)
                right = int(right * scale_factor)
                bottom = int(bottom * scale_factor)
                
                # Draw the crop box
                draw = ImageDraw.Draw(preview_img)
                draw.rectangle([left, top, right, bottom], outline='red', width=2)
                
                # Draw semi-transparent overlay for cropped areas
                overlay = Image.new('RGBA', preview_img.size, (0, 0, 0, 128))
                draw = ImageDraw.Draw(overlay)
                # Draw overlay everywhere except the crop box
                draw.rectangle([0, 0, preview_img.size[0], preview_img.size[1]], fill=(0, 0, 0, 128))
                draw.rectangle([left, top, right, bottom], fill=(0, 0, 0, 0))
                preview_img = Image.alpha_composite(preview_img.convert('RGBA'), overlay)
            
            return preview_img
            
        except Exception as e:
            raise Exception(f"Error creating preview: {str(e)}")

    def process_image(self, img, scale_factor, target_resolution=None, fill_mode=False,
                     color_mode="auto", dither_method=None, optimize=True, interlace=False,
                     filter_method="auto"):
        """Process an image according to the specified settings"""
        try:
            # Calculate new dimensions
            new_width = int(img.size[0] * scale_factor)
            new_height = int(img.size[1] * scale_factor)
            
            # Resize image if scaling is needed
            if scale_factor != 1.0:
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Apply cropping if fill mode is enabled and a target resolution is specified
            if target_resolution and fill_mode:
                target_width, target_height = target_resolution
                crop_box = self.calculate_crop_box(img, target_width, target_height, scale_factor)
                img = img.crop(crop_box)
            
            # Apply color mode conversion if needed
            if color_mode != "auto":
                if color_mode == "P":
                    # Convert to palette mode with dithering
                    img = img.convert("P", 
                                    palette=Image.Palette.ADAPTIVE,
                                    colors=256,
                                    dither=dither_method)
                else:
                    img = img.convert(color_mode)
            
            return img
            
        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")

    def save_image(self, img, output_path, optimize=True, interlace=False, filter_method="auto"):
        """Save an image with the specified settings"""
        try:
            # Prepare save parameters
            save_params = {
                'format': 'PNG',
                'optimize': optimize,
                'compress_level': 9,  # Always use maximum compression
                'interlace': interlace
            }
            
            # Add filter method if specified
            if filter_method != "auto":
                save_params['filter'] = filter_method
            
            # Save the image
            img.save(output_path, **save_params)
            
        except Exception as e:
            raise Exception(f"Error saving image: {str(e)}") 