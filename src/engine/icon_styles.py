from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import cv2
from typing import Optional, Tuple, Dict, Callable

class IconStyleEngine:
    def __init__(self, size: int = 1024):
        self.size = size
        self.background_color = (255, 255, 255, 255)
        self._cache: Dict[Tuple[str, int], Image.Image] = {}
        self._style_registry: Dict[str, Tuple[Callable[[], Image.Image], float]] = {
            "big_sur": (self.create_big_sur_background, 0.6),
            "catalina": (self.create_catalina_background, 0.65),
            "classic": (self.create_classic_background, 0.6),
        }

    def create_big_sur_background(self) -> Image.Image:
        """Creates a Big Sur style squircle background with a subtle gradient and shadow."""
        base = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        
        # Big Sur Squircle parameters
        # In a 1024x1024 canvas, the icon is usually around 824x824
        icon_size = int(self.size * 0.8)
        padding = (self.size - icon_size) // 2
        corner_radius = int(icon_size * 0.22) # Approximate squircle radius
        
        rect = [padding, padding, padding + icon_size, padding + icon_size]
        
        # Shadow (very subtle)
        shadow_offset = int(self.size * 0.02)
        shadow_blur = int(self.size * 0.04)
        shadow_mask = Image.new("L", (self.size, self.size), 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        shadow_draw.rounded_rectangle(rect, radius=corner_radius, fill=100)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(shadow_blur))
        
        shadow = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 255))
        base.paste(shadow, (0, shadow_offset), shadow_mask)

        # Gradient Background
        # Vertical gradient from light gray (top) to white (bottom)
        gradient = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(gradient)
        for i in range(padding, padding + icon_size):
            # i goes from padding to padding + icon_size
            # progress goes from 0.0 to 1.0
            progress = (i - padding) / icon_size
            # Gray value goes from 240 (light gray) to 255 (white)
            gray = int(240 + progress * 15)
            g_draw.line([(padding, i), (padding + icon_size, i)], fill=(gray, gray, gray, 255))
        
        # Mask for the squircle
        mask = Image.new("L", (self.size, self.size), 0)
        m_draw = ImageDraw.Draw(mask)
        m_draw.rounded_rectangle(rect, radius=corner_radius, fill=255)
        
        base.paste(gradient, (0, 0), mask)
        
        # Border (subtle)
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle(rect, radius=corner_radius, outline=(200, 200, 200, 255), width=2)
        
        return base

    def create_catalina_background(self) -> Image.Image:
        """Creates a Catalina style circular background."""
        base = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        
        icon_size = int(self.size * 0.85)
        padding = (self.size - icon_size) // 2
        rect = [padding, padding, padding + icon_size, padding + icon_size]
        
        # Shadow
        shadow_blur = int(self.size * 0.02)
        shadow_mask = Image.new("L", (self.size, self.size), 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        shadow_draw.ellipse(rect, fill=80)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(shadow_blur))
        
        shadow = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 255))
        base.paste(shadow, (0, int(self.size * 0.01)), shadow_mask)

        # Gradient (subtle top-to-bottom for circular icons)
        mask = Image.new("L", (self.size, self.size), 0)
        m_draw = ImageDraw.Draw(mask)
        m_draw.ellipse(rect, fill=255)
        
        gradient = Image.new("RGBA", (self.size, self.size), (250, 250, 250, 255))
        g_draw = ImageDraw.Draw(gradient)
        for i in range(padding, padding + icon_size):
            progress = (i - padding) / icon_size
            gray = int(250 + progress * 5)
            g_draw.line([(padding, i), (padding + icon_size, i)], fill=(gray, gray, gray, 255))

        base.paste(gradient, (0, 0), mask)
        
        draw = ImageDraw.Draw(base)
        draw.ellipse(rect, outline=(220, 220, 220, 255), width=2)
        
        return base

    def create_classic_background(self) -> Image.Image:
        """Creates a Classic style rectangular background with rounded corners."""
        base = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        
        # Usually rectangular icons are full size or slightly padded
        icon_width = int(self.size * 0.9)
        icon_height = int(self.size * 0.7)
        padding_x = (self.size - icon_width) // 2
        padding_y = (self.size - icon_height) // 2
        corner_radius = int(self.size * 0.05)
        
        rect = [padding_x, padding_y, padding_x + icon_width, padding_y + icon_height]
        
        # Shadow
        shadow_blur = int(self.size * 0.02)
        shadow_mask = Image.new("L", (self.size, self.size), 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        shadow_draw.rounded_rectangle(rect, radius=corner_radius, fill=60)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(shadow_blur))
        
        shadow = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 255))
        base.paste(shadow, (0, int(self.size * 0.01)), shadow_mask)

        mask = Image.new("L", (self.size, self.size), 0)
        m_draw = ImageDraw.Draw(mask)
        m_draw.rounded_rectangle(rect, radius=corner_radius, fill=255)
        
        bg = Image.new("RGBA", (self.size, self.size), (255, 255, 255, 255))
        base.paste(bg, (0, 0), mask)
        
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle(rect, radius=corner_radius, outline=(200, 200, 200, 255), width=2)
        
        return base

    def get_background(self, style_name: str) -> Tuple[Optional[Image.Image], float]:
        """Gets background from cache or creates it."""
        if style_name not in self._style_registry:
            return None, 1.0
            
        cache_key = (style_name, self.size)
        if cache_key not in self._cache:
            create_func, content_scale = self._style_registry[style_name]
            self._cache[cache_key] = create_func()
            
        return self._cache[cache_key].copy(), self._style_registry[style_name][1]

    def apply_style(self, logo_cv: np.ndarray, style_name: str) -> np.ndarray:
        """
        Applies a macOS style to a logo image.
        logo_cv: RGBA numpy array (OpenCV format)
        Returns: RGBA numpy array
        """
        if style_name == "none" or not style_name:
            return logo_cv

        # Update engine size if logo size is significantly different
        h, w = logo_cv.shape[:2]
        max_dim = max(h, w)
        if abs(self.size - (max_dim / 0.6)) > 50: # roughly estimate background size
            self.size = int(max_dim / 0.6)
            # Cache is still valid for other sizes, but we want a good base size

        background, content_scale = self.get_background(style_name)
        if background is None:
            return logo_cv

        # Convert OpenCV (BGRA) to PIL (RGBA)
        logo_rgba = cv2.cvtColor(logo_cv, cv2.COLOR_BGRA2RGBA)
        logo_pil = Image.fromarray(logo_rgba)
        
        # Resize logo to fit inside background
        bg_w, bg_h = background.size
        target_size = int(min(bg_w, bg_h) * content_scale)
        
        logo_w, logo_h = logo_pil.size
        aspect = logo_w / logo_h
        
        if aspect > 1:
            new_w = target_size
            new_h = int(target_size / aspect)
        else:
            new_h = target_size
            new_w = int(target_size * aspect)
            
        logo_pil = logo_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Center logo on background
        offset = ((bg_w - new_w) // 2, (bg_h - new_h) // 2)
        
        # Composite
        background.paste(logo_pil, offset, logo_pil)
        
        # Convert back to OpenCV (BGRA)
        result_rgba = np.array(background)
        result_bgra = cv2.cvtColor(result_rgba, cv2.COLOR_RGBA2BGRA)
        
        return result_bgra
