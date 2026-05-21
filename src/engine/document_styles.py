from PIL import Image, ImageDraw
import numpy as np
import cv2
import os
from typing import Optional

class DocumentStyleEngine:
    def __init__(self, size: int = 1024):
        self.size = size
        self.template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "res", "documents.png"
        )
        self._cache: Optional[Image.Image] = None

    def get_document_background(self) -> Image.Image:
        """Loads and caches the document template image at standard size."""
        if self._cache is not None:
            return self._cache.copy()

        if os.path.exists(self.template_path):
            template = Image.open(self.template_path).convert("RGBA")
            if template.size != (self.size, self.size):
                template = template.resize((self.size, self.size), Image.Resampling.LANCZOS)
            self._cache = template
        else:
            # Fallback to procedural document shape
            self._cache = self._create_fallback_document()
            
        return self._cache.copy()

    def _create_fallback_document(self) -> Image.Image:
        """Procedural fallback if PNG is not found."""
        base = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)
        width, height = int(self.size * 0.7), int(self.size * 0.9)
        padding_x = (self.size - width) // 2
        padding_y = (self.size - height) // 2
        
        draw.rectangle(
            [padding_x, padding_y, padding_x + width, padding_y + height], 
            fill=(255, 255, 255, 255), 
            outline=(200, 200, 200, 255), 
            width=4
        )
        return base

    def apply_document_style(self, logo_cv: np.ndarray, opacity: float = 1.0, scale: float = 0.5, layout: str = "center") -> np.ndarray:
        """Applies document style using the PNG template."""
        h, w = logo_cv.shape[:2]
        if max(h, w) > 2048:
            scale_down = 2048 / max(h, w)
            logo_cv = cv2.resize(logo_cv, (int(w * scale_down), int(h * scale_down)), interpolation=cv2.INTER_AREA)
            h, w = logo_cv.shape[:2]

        self.size = 1024 # Standardize on template size

        background = self.get_document_background()
        
        logo_rgba = cv2.cvtColor(logo_cv, cv2.COLOR_BGRA2RGBA)
        logo_pil = Image.fromarray(logo_rgba)

        if opacity < 1.0:
            r, g, b, a = logo_pil.split()
            a = a.point(lambda p: p * opacity)
            logo_pil = Image.merge("RGBA", (r, g, b, a))

        # Bounding box of the document template at 1024x1024
        # Original bbox (54, 5, 420, 488) at 512x512 translates to (108, 10, 840, 976)
        bbox = (108, 10, 840, 976)
        bbox_w = bbox[2] - bbox[0] # 732
        bbox_h = bbox[3] - bbox[1] # 966

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
            center_x = bbox[0] + bbox_w // 2 # 474
            center_y = bbox[1] + bbox_h // 2 # 493
            
            # Place the logo centered on the document
            target_size = int(min(bbox_w, bbox_h) * scale)
            
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
