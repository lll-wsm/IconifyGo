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

def export_png_set(pil_image: Image.Image, output_dir: str) -> bool:
    """
    Exports a PIL image as a set of PNG files at various sizes.
    """
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        sizes = [1024, 512, 256, 128, 64, 32, 16]
        
        # Ensure base image is square for consistency in the set
        width, height = pil_image.size
        max_dim = max(width, height)
        if width != height:
            square_img = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))
            offset = ((max_dim - width) // 2, (max_dim - height) // 2)
            square_img.paste(pil_image, offset)
            base_img = square_img
        else:
            base_img = pil_image

        for size in sizes:
            resized = base_img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(os.path.join(output_dir, f"icon_{size}x{size}.png"))
            
        return True
    except Exception as e:
        print(f"Error exporting PNG set: {e}")
        return False
