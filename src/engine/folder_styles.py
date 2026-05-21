from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np
import cv2
import os
from typing import Optional, Tuple, Dict

class FolderStyleEngine:
    def __init__(self, size: int = 1024):
        self.size = size
        self.default_color = "#5ac8fa" 
        self._cache: Dict[Tuple[str, str, int], Image.Image] = {}
        # Path to the high-quality template provided by the user
        self.template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "res", "folder.png")

    def create_folder_background(self, color: str = "#5ac8fa", preset: str = "generic") -> Image.Image:
        """Creates a folder background using the provided PNG template."""
        cache_key = (color, preset, self.size)
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        # Try to load the provided PNG template
        if os.path.exists(self.template_path):
            template = Image.open(self.template_path).convert("RGBA")
            if template.size != (self.size, self.size):
                template = template.resize((self.size, self.size), Image.Resampling.LANCZOS)
            
            # If color is not the default macOS blue, we can attempt to tint it
            # For now, we use the template directly as requested.
            # (Optional: Add tinting logic here if needed)
            base = template
        else:
            # Fallback to procedural drawing if template is missing
            base = self._create_fallback_folder(color)

        self._cache[cache_key] = base
        return base.copy()

    def _create_fallback_folder(self, color: str) -> Image.Image:
        """Procedural fallback if PNG is not found."""
        base = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)
        width, height = int(self.size * 0.9), int(self.size * 0.7)
        padding_x, padding_y = (self.size - width) // 2, (self.size - height) // 2
        corner_radius = int(self.size * 0.05)
        
        def hex_to_rgb(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        
        rgb = hex_to_rgb(color)
        draw.rounded_rectangle([padding_x, padding_y, padding_x + width, padding_y + height], 
                                radius=corner_radius, fill=rgb + (255,))
        return base

    def apply_folder_style(self, logo_cv: np.ndarray, color: str = "#5ac8fa", opacity: float = 1.0, scale: float = 0.5, preset: str = "generic", layout: str = "center") -> np.ndarray:
        """Applies folder style using the PNG template."""
        h, w = logo_cv.shape[:2]
        if max(h, w) > 2048:
            scale_down = 2048 / max(h, w)
            logo_cv = cv2.resize(logo_cv, (int(w * scale_down), int(h * scale_down)), interpolation=cv2.INTER_AREA)
            h, w = logo_cv.shape[:2]

        self.size = 1024 # Standardize on template size

        background = self.create_folder_background(color, preset)
        
        logo_rgba = cv2.cvtColor(logo_cv, cv2.COLOR_BGRA2RGBA)
        logo_pil = Image.fromarray(logo_rgba)

        if opacity < 1.0:
            r, g, b, a = logo_pil.split()
            a = a.point(lambda p: p * opacity)
            logo_pil = Image.merge("RGBA", (r, g, b, a))

        if layout == "cover":
            # Bounding box of the folder template at 1024x1024: (28, 109, 996, 932)
            bbox = (28, 109, 996, 932)
            bbox_w = bbox[2] - bbox[0]
            bbox_h = bbox[3] - bbox[1]
            
            # Resize logo to cover the bbox (aspect ratio preserving)
            logo_w, logo_h = logo_pil.size
            aspect = logo_w / logo_h
            bbox_aspect = bbox_w / bbox_h
            
            if aspect > bbox_aspect:
                new_h = bbox_h
                new_w = int(bbox_h * aspect)
            else:
                new_w = bbox_w
                new_h = int(bbox_w / aspect)
                
            logo_resized = logo_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Crop to fit bbox exactly (centered crop)
            crop_x = (new_w - bbox_w) // 2
            crop_y = (new_h - bbox_h) // 2
            logo_cropped = logo_resized.crop((crop_x, crop_y, crop_x + bbox_w, crop_y + bbox_h))
            
            # Create a full-size image with the cropped logo positioned at bbox[0], bbox[1]
            logo_full = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
            logo_full.paste(logo_cropped, (bbox[0], bbox[1]))
            
            # Mask this logo with the folder template's alpha channel
            bg_alpha = background.split()[3]
            
            masked_logo = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
            masked_logo.paste(logo_full, (0, 0), bg_alpha)
            
            # Composite
            background = Image.alpha_composite(background, masked_logo)
        else: # "center"
            # Calibrated placement for the provided folder.png
            # The front flap of this specific PNG is roughly in the bottom 2/3
            area_width = self.size * 0.85
            area_height = self.size * 0.55
            center_x = self.size // 2
            center_y = int(self.size * 0.6) # Shifted down to match the front flap visual center
            
            target_size = int(min(area_width, area_height) * scale)
            
            logo_w, logo_h = logo_pil.size
            aspect = logo_w / logo_h
            if aspect > 1:
                new_w, new_h = target_size, int(target_size / aspect)
            else:
                new_h, new_w = target_size, int(target_size * aspect)
                
            logo_pil = logo_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            offset = (center_x - new_w // 2, center_y - new_h // 2)
            background.paste(logo_pil, offset, logo_pil)

        result_rgba = np.array(background)
        return cv2.cvtColor(result_rgba, cv2.COLOR_RGBA2BGRA)
