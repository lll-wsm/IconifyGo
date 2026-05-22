from PIL import Image, ImageDraw
import numpy as np
import cv2
import os
import os
from src.utils.paths import get_resource_path

class DocumentStyleEngine:
    def __init__(self, size: int = 1024):
        self.size = size
        self.template_path = get_resource_path(os.path.join("res", "documents.png"))

        self._cache: dict = {}

    def get_document_background(self, color: tuple = (255, 255, 255)) -> Image.Image:
        """Loads and caches the document template image at standard size with dynamic color tinting."""
        if color in self._cache:
            return self._cache[color].copy()

        if os.path.exists(self.template_path):
            template = Image.open(self.template_path).convert("RGBA")
            if template.size != (self.size, self.size):
                template = template.resize((self.size, self.size), Image.Resampling.LANCZOS)
            
            if color != (255, 255, 255):
                from PIL import ImageOps
                r, g, b, a = template.split()
                gray = ImageOps.grayscale(template)
                tinted = ImageOps.colorize(gray, black="#000000", white="#ffffff", mid=color)
                tinted = tinted.convert("RGBA")
                tinted.putalpha(a)
                base = tinted
            else:
                base = template
            self._cache[color] = base
        else:
            # Fallback to procedural document shape
            self._cache[color] = self._create_fallback_document(color)
            
        return self._cache[color].copy()

    def _create_fallback_document(self, color: tuple) -> Image.Image:
        """Procedural fallback if PNG is not found."""
        base = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)
        width, height = int(self.size * 0.7), int(self.size * 0.9)
        padding_x = (self.size - width) // 2
        padding_y = (self.size - height) // 2
        
        # Ensure color format is RGB
        fill_color = color[:3]
        if len(fill_color) < 3:
            fill_color = (255, 255, 255)
            
        draw.rectangle(
            [padding_x, padding_y, padding_x + width, padding_y + height], 
            fill=fill_color + (255,), 
            outline=(200, 200, 200, 255), 
            width=4
        )
        return base

    def apply_document_style(self, logo_cv: np.ndarray, color: tuple = (255, 255, 255), opacity: float = 1.0, scale: float = 0.5, layout: str = "center", scale_multiplier: float = 1.0) -> np.ndarray:
        """Applies document style using the PNG template."""
        h, w = logo_cv.shape[:2]
        if max(h, w) > 2048:
            scale_down = 2048 / max(h, w)
            logo_cv = cv2.resize(logo_cv, (int(w * scale_down), int(h * scale_down)), interpolation=cv2.INTER_AREA)
            h, w = logo_cv.shape[:2]

        self.size = 1024 # Standardize on template size

        background = self.get_document_background(color)
        
        logo_rgba = cv2.cvtColor(logo_cv, cv2.COLOR_BGRA2RGBA)
        logo_pil = Image.fromarray(logo_rgba)

        # Crop to content to ensure centering is based on the subject
        bbox = logo_pil.getbbox()
        if bbox:
            logo_pil = logo_pil.crop(bbox)

        if opacity < 1.0:
            r, g, b, a = logo_pil.split()
            a = a.point(lambda p: p * opacity)
            logo_pil = Image.merge("RGBA", (r, g, b, a))

        # Bounding box of the document template at 1024x1024
        # Original bbox (54, 5, 420, 488) at 512x512 translates to (108, 10, 840, 976)
        orig_bbox = (108, 10, 840, 976)
        orig_w = orig_bbox[2] - orig_bbox[0] # 732
        orig_h = orig_bbox[3] - orig_bbox[1] # 966
        orig_cx = (orig_bbox[0] + orig_bbox[2]) // 2
        orig_cy = (orig_bbox[1] + orig_bbox[3]) // 2

        bbox_w = int(orig_w * scale_multiplier)
        bbox_h = int(orig_h * scale_multiplier)

        bbox = (
            orig_cx - bbox_w // 2,
            orig_cy - bbox_h // 2,
            orig_cx + bbox_w // 2,
            orig_cy + bbox_h // 2
        )

        if layout == "cover":
            # Scale logo to cover the document bbox (aspect ratio preserving)
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
            
            # Mask this logo with the document template's alpha channel
            bg_alpha = background.split()[3]
            
            masked_logo = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
            masked_logo.paste(logo_full, (0, 0), bg_alpha)
            
            # Composite
            background = Image.alpha_composite(background, masked_logo)
            
        else: # "center"
            center_x = bbox[0] + bbox_w // 2
            center_y = bbox[1] + bbox_h // 2
            
            # Place the logo centered on the document
            target_size = int(min(bbox_w, bbox_h) * scale * scale_multiplier)
            
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
