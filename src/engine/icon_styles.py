from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import cv2
from typing import Optional, Tuple, Dict, Callable

# Android Adaptive Icon: safe zone = 66/108 of the layer canvas (the inner
# 66x66dp that masks never clip).  Used so the editor preview places the
# subject exactly like the exported foreground layer.
ANDROID_SAFE_SCALE = 66.0 / 108.0  # 0.611

# macOS HIG icon grid: ~824 of the 1024 canvas is the standard "apple shape"
# art box; macOS does not round corners for you, so we pre-shape the squircle.
_MACOS_CONTENT = 824.0 / 1024.0


class IconStyleEngine:
    def __init__(self, size: int = 1024):
        self.size = size
        self.min_size = size
        self.background_color = (255, 255, 255, 255)
        self._cache: Dict[Tuple[str, int, Tuple[int, ...]], Image.Image] = {}
        self._style_registry: Dict[str, Tuple[Callable[[], Image.Image], float]] = {
            "big_sur": (self.create_big_sur_background, 0.62),
            "catalina": (self.create_catalina_background, 0.6),
            "classic": (self.create_classic_background, 0.6),
            "ios": (self.create_ios_background, 0.78),
            "android": (self.create_android_background, 0.611),  # 66/108 safe zone
        }

    def _rgb_from_bg(self, fallback=(255, 255, 255)):
        """Return an opaque RGB triple: honor alpha>0, else white."""
        c = self.background_color
        if len(c) >= 4 and c[3] == 0:
            return fallback
        return c[:3]

    # ------------------------------------------------------------------
    # iOS — full-bleed, opaque, no pre-rounded corners, no alpha anywhere
    # ------------------------------------------------------------------
    def create_ios_background(self) -> Image.Image:
        """Full-bleed opaque iOS icon canvas (1024x1024, alpha = 255).

        iOS requires square edge-to-edge artwork with *no* alpha and *no*
        pre-rendered corner rounding — the system applies its own squircle
        mask (and App Store Connect rejects transparency).  So the returned
        image must never contain a transparent pixel.
        """
        r, g, b = self._rgb_from_bg()
        # Solid base guarantees full opacity for every pixel.
        return Image.new("RGB", (self.size, self.size), (r, g, b))

    # ------------------------------------------------------------------
    # Android — full-bleed square background (Adaptive Icon spec).
    #
    # Android 8.0+ Adaptive Icons: the launcher masks square layers itself.
    # Foreground & background are BOTH square 108x108dp canvases (never
    # pre-rounded/circular); the central 72x72dp is the visible viewport and
    # 66x66dp is the guaranteed safe zone.  The editor preview therefore shows
    # a full-bleed square plate (== the exported background layer) with the
    # subject placed inside the safe zone, so preview == export.
    # ------------------------------------------------------------------
    def create_android_background(self) -> Image.Image:
        """Full-bleed square background layer for an Android Adaptive Icon.

        The device launcher applies its own mask (circle/squircle/square); the
        layer itself must be square and fully opaque so nothing is lost under
        the mask.  Alpha = 255 everywhere except where a subtle plate is drawn.
        """
        r, g, b = self._rgb_from_bg(fallback=(60, 60, 60))
        # Full-bleed opaque square (exactly the adaptive background layer).
        return Image.new("RGBA", (self.size, self.size), (r, g, b, 255))

    def create_big_sur_background(self) -> Image.Image:
        """Big Sur style squircle with subtle gradient and soft shadow.

        Icon body matches the macOS grid (≈824/1024).  The corner is a
        superellipse-like path (n=5) instead of a plain rounded rectangle, and
        the drop shadow is drawn offset so its edges never collide with the
        1024 canvas borders.
        """
        side = self.size
        base = Image.new("RGBA", (side, side), (0, 0, 0, 0))

        # Superellipse body inset to the macOS content grid (~824 px).
        inset = (side - int(side * _MACOS_CONTENT)) // 2  # ~100px
        rect = (inset, inset, side - inset, side - inset)
        n = 5.0

        def superellipse(rect, n):
            x0, y0, x1, y1 = rect
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            a, b = (x1 - x0) / 2.0, (y1 - y0) / 2.0
            pts = []
            steps = 400
            for i in range(steps):
                t = 2.0 * np.pi * i / steps
                px = cx + a * np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2.0 / n)
                py = cy + b * np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2.0 / n)
                pts.append((px, py))
            return pts

        # Shadow: paste offset inside so it is not clipped by canvas edges.
        shadow_off = int(side * 0.012)
        blur = int(side * 0.02)
        sh_rect = (inset, inset + shadow_off, side - inset, side - inset + shadow_off)
        sh_mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(sh_mask).polygon(superellipse(sh_rect, n), fill=90)
        sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(blur))
        shadow = Image.new("RGBA", (side, side), (0, 0, 0, 255))
        base.paste(shadow, (0, 0), sh_mask)

        # Gradient body.
        gradient = self._create_gradient_background(list(rect), 0.94)
        body_mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(body_mask).polygon(superellipse(rect, n), fill=255)
        base.paste(gradient, (0, 0), body_mask)

        return base

    def create_catalina_background(self) -> Image.Image:
        """Catalina-style circular icon with a soft shadow and gradient."""
        side = self.size
        base = Image.new("RGBA", (side, side), (0, 0, 0, 0))

        size = int(side * 0.85)
        pad = (side - size) // 2
        rect = (pad, pad, pad + size, pad + size)

        # shadow inside canvas
        blur = int(side * 0.02)
        sh_rect = (pad, pad + int(side * 0.01), pad + size, pad + size + int(side * 0.01))
        sh_mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(sh_mask).ellipse(sh_rect, fill=70)
        sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(blur))
        base.paste(Image.new("RGBA", (side, side), (0, 0, 0, 255)), (0, 0), sh_mask)

        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).ellipse(rect, fill=255)
        gradient = self._create_gradient_background(list(rect), 0.98)
        base.paste(gradient, (0, 0), mask)

        ImageDraw.Draw(base).ellipse(rect, outline=(220, 220, 220, 255), width=2)
        return base

    def create_classic_background(self) -> Image.Image:
        """Classic rounded-rectangle icon (pre-Big Sur macOS style)."""
        side = self.size
        base = Image.new("RGBA", (side, side), (0, 0, 0, 0))

        w = int(side * 0.9)
        h = int(side * 0.7)
        pad_x = (side - w) // 2
        pad_y = (side - h) // 2
        radius = int(side * 0.05)
        rect = (pad_x, pad_y, pad_x + w, pad_y + h)

        # shadow
        blur = int(side * 0.02)
        sh_rect = (pad_x, pad_y + int(side * 0.01), pad_x + w, pad_y + h + int(side * 0.01))
        sh_mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(sh_mask).rounded_rectangle(sh_rect, radius=radius, fill=60)
        sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(blur))
        base.paste(Image.new("RGBA", (side, side), (0, 0, 0, 255)), (0, 0), sh_mask)

        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).rounded_rectangle(rect, radius=radius, fill=255)
        bg = Image.new("RGBA", (side, side), self._rgb_from_bg())
        base.paste(bg, (0, 0), mask)
        return base

    # ------------------------------------------------------------------
    # generic gradient helper
    # ------------------------------------------------------------------
    def _create_gradient_background(self, rect, factor: float) -> Image.Image:
        padding = rect[1]
        icon_size = rect[3] - rect[1]
        bg = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(bg)

        r, g, b = self._rgb_from_bg()
        for i in range(padding, padding + icon_size):
            progress = (i - padding) / icon_size
            current_factor = factor + progress * (1.0 - factor)
            curr_r = int(max(0, min(255, r * current_factor)))
            curr_g = int(max(0, min(255, g * current_factor)))
            curr_b = int(max(0, min(255, b * current_factor)))
            g_draw.line([(rect[0], i), (rect[2], i)], fill=(curr_r, curr_g, curr_b, 255))
        return bg

    # ------------------------------------------------------------------
    # cache / apply
    # ------------------------------------------------------------------
    def get_background(self, style_name: str) -> Tuple[Optional[Image.Image], float]:
        if style_name not in self._style_registry:
            return None, 1.0

        # All iOS pixels must be opaque; ignore the alpha of a user color pick.
        bg_color = self._rgb_from_bg() + (255,) if style_name == "ios" else self.background_color
        if len(bg_color) >= 4 and bg_color[3] == 0:
            bg_color = (255, 255, 255, 255)

        cache_key = (style_name, self.size, bg_color)
        if cache_key not in self._cache:
            original = self.background_color
            self.background_color = bg_color
            create_func, _ = self._style_registry[style_name]
            self._cache[cache_key] = create_func()
            self.background_color = original
        return self._cache[cache_key].copy(), self._style_registry[style_name][1]

    def make_glyph(self, logo_cv: np.ndarray) -> np.ndarray:
        """Return a tight-cropped RGBA glyph of the subject (transparent
        padding removed).  Android adaptive exporters do all placement/sizing
        from this tight glyph (they fit it into the safe zone)."""
        h, w = logo_cv.shape[:2]
        logo_rgba = cv2.cvtColor(logo_cv, cv2.COLOR_BGRA2RGBA)
        pil = Image.fromarray(logo_rgba)
        bbox = pil.getbbox()
        if bbox:
            pil = pil.crop(bbox)
        out = np.array(pil)
        return cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA)

    def apply_style(self, logo_cv: np.ndarray, style_name: str, scale_multiplier: float = 1.0) -> np.ndarray:
        """Applies a platform style to a logo (RGBA numpy). Returns RGBA numpy."""
        if style_name == "none" or not style_name:
            return logo_cv

        h, w = logo_cv.shape[:2]
        max_dim = max(h, w)
        if abs(self.size - (max_dim / 0.6)) > 50:
            self.size = max(self.min_size, int(max_dim / 0.6))

        background, content_scale = self.get_background(style_name)
        if background is None:
            return logo_cv

        logo_rgba = cv2.cvtColor(logo_cv, cv2.COLOR_BGRA2RGBA)
        logo_pil = Image.fromarray(logo_rgba)

        bbox = logo_pil.getbbox()
        if bbox:
            logo_pil = logo_pil.crop(bbox)

        bg_w, bg_h = background.size
        target_size = int(min(bg_w, bg_h) * content_scale * scale_multiplier)
        lw, lh = logo_pil.size
        aspect = lw / lh
        if aspect > 1:
            new_w, new_h = target_size, max(1, int(target_size / aspect))
        else:
            new_h, new_w = target_size, max(1, int(target_size * aspect))
        logo_pil = logo_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center the subject.
        offset = ((bg_w - new_w) // 2, (bg_h - new_h) // 2)
        background = background.convert("RGBA") if background.mode != "RGBA" else background
        background.paste(logo_pil, offset, logo_pil)

        result_rgba = np.array(background)
        if style_name == "ios":
            # Full-bleed iOS artwork must be 100% opaque everywhere; the
            # anti-aliased logo edge pixels already blend onto the opaque bg,
            # so any residual partial alpha must be flattened to 255.
            result_rgba[..., 3] = 255
        return cv2.cvtColor(result_rgba, cv2.COLOR_RGBA2BGRA)
