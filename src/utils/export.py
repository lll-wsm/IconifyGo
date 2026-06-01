import os
from PIL import Image
from typing import List

def export_icns(pil_image: Image.Image, output_path: str) -> bool:
    """
    Exports a PIL image as a macOS .icns file.
    Pillow handles the necessary resizing internally, but starting with 1024x1024 is ideal.
    """
    try:
        # Ensure the image is square and in RGBA mode
        width, height = pil_image.size
        size = max(width, height)
        
        # Create a new square RGBA image if necessary
        if width != height or pil_image.mode != 'RGBA':
            square_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            # Center the image
            offset = ((size - width) // 2, (size - height) // 2)
            square_img.paste(pil_image, offset)
            pil_image = square_img

        # pillow-icns requires specific sizes if we were doing it manually,
        # but modern Pillow pil_image.save(..., format='ICNS') is quite good.
        # We ensure it's at least 1024 for high-res icons.
        if size < 1024:
            pil_image = pil_image.resize((1024, 1024), Image.Resampling.LANCZOS)
        
        pil_image.save(output_path, format='ICNS')
        return True
    except Exception as e:
        print(f"Error exporting ICNS: {e}")
        return False

def export_ico(pil_image: Image.Image, output_path: str) -> bool:
    """
    Exports a PIL image as a Windows .ico file containing standard sizes.
    """
    try:
        # Ensure the image is square and in RGBA mode
        width, height = pil_image.size
        size = max(width, height)
        
        # Create a new square RGBA image if necessary
        if width != height or pil_image.mode != 'RGBA':
            square_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            # Center the image
            offset = ((size - width) // 2, (size - height) // 2)
            square_img.paste(pil_image, offset)
            pil_image = square_img

        # Windows ICO supports up to 256x256
        ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        
        if size < 256:
            pil_image = pil_image.resize((256, 256), Image.Resampling.LANCZOS)
            
        pil_image.save(output_path, format='ICO', sizes=ico_sizes)
        return True
    except Exception as e:
        print(f"Error exporting ICO: {e}")
        return False

def export_png_set(pil_image: Image.Image, output_dir: str) -> bool:
    """
    Exports a PIL image as a set of PNG files at various sizes,
    including standard macOS icon set, Windows custom app asset sizes, and macOS icon.icns.
    """
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Ensure base image is square for consistency in the set
        width, height = pil_image.size
        max_dim = max(width, height)
        if width != height or pil_image.mode != 'RGBA':
            square_img = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))
            offset = ((max_dim - width) // 2, (max_dim - height) // 2)
            square_img.paste(pil_image, offset)
            base_img = square_img
        else:
            base_img = pil_image

        # Standard macOS sizes
        sizes = [1024, 512, 256, 128, 64, 32, 16]
        for size in sizes:
            resized = base_img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(os.path.join(output_dir, f"icon_{size}x{size}.png"))

        # macOS Retina @2x sizes for standard .iconset compatibility
        retina_sizes = {
            "icon_16x16@2x.png": (32, 32),
            "icon_32x32@2x.png": (64, 64),
            "icon_128x128@2x.png": (256, 256),
            "icon_256x256@2x.png": (512, 512),
            "icon_512x512@2x.png": (1024, 1024),
        }
        for name, size in retina_sizes.items():
            resized = base_img.resize(size, Image.Resampling.LANCZOS)
            resized.save(os.path.join(output_dir, name))

        # Newly requested custom named files (often used for Windows/UWP app packaging)
        custom_sizes = {
            "Square284x284Logo.png": (284, 284),
            "Square71x71Logo.png": (71, 71),
            "32x32.png": (32, 32),
            "Square107x107Logo.png": (107, 107),
            "Square30x30Logo.png": (30, 30),
            "Square89x89Logo.png": (89, 89),
            "Square142x142Logo.png": (142, 142),
            "Square310x310Logo.png": (310, 310),
            "StoreLogo.png": (50, 50),
            "Square44x44Logo.png": (44, 44),
            "Square150x150Logo.png": (150, 150),
            "44x44.png": (44, 44),
            "150x150.png": (150, 150),
        }
        for name, size in custom_sizes.items():
            resized = base_img.resize(size, Image.Resampling.LANCZOS)
            resized.save(os.path.join(output_dir, name))
            
        # Generate macOS icon.icns in the same folder
        export_icns(base_img, os.path.join(output_dir, "icon.icns"))
            
        return True
    except Exception as e:
        print(f"Error exporting PNG set: {e}")
        return False
