"""Single source of truth for rendering a styled 1024 master image.

Used by the main canvas preview, the right-side gallery thumbnails and the
export pipeline so that "what you see is what you export".

All styles return a 1024x1024 BGRA numpy image, with iOS already flattened to
a fully opaque full-bleed image (alpha=255 everywhere).
"""
import numpy as np
import cv2

from PIL import Image

from src.engine.icon_styles import IconStyleEngine
from src.engine.folder_styles import FolderStyleEngine
from src.engine.document_styles import DocumentStyleEngine
from src.utils.text_renderer import draw_text_on_np

#: list of style ids the icon engine knows (app icon plates).
ICON_STYLES = ("big_sur", "catalina", "classic", "ios", "android")


def render_original_native(subject_rgba: np.ndarray,
                           bg: tuple = (0, 0, 0, 0),
                           text_items_data: list = None,
                           canvas_ref_size: tuple = (1024, 1024)) -> np.ndarray:
    """Render the 'original / no background' output at native subject size.

    Used by the export (Original Size PNG) and by the gallery thumbnail so the
    artwork is identical (subject + optional flat bg + text overlays).
    Returns BGRA numpy at the subject's native resolution.
    """
    if text_items_data is None:
        text_items_data = []
    if subject_rgba is None or subject_rgba.size == 0:
        subject_rgba = np.zeros((1, 1, 4), dtype=np.uint8)
    out = subject_rgba.copy()
    if text_items_data:
        out = draw_text_on_np(out, text_items_data, canvas_ref_size)
    if len(bg) >= 4 and bg[3] > 0:
        pil = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGRA2RGBA))
        bg_layer = Image.new("RGBA", pil.size, tuple(bg))
        out = cv2.cvtColor(np.array(Image.alpha_composite(bg_layer, pil)),
                           cv2.COLOR_RGBA2BGRA)
    return out


def render_style_1024(subject_rgba: np.ndarray,
                      style_id: str,
                      bg: tuple = (0, 0, 0, 0),
                      scale_multiplier: float = 1.0,
                      text_items_data: list = None,
                      canvas_ref_size: tuple = (1024, 1024),
                      hex_color: str = "#5ac8fa",
                      doc_color: tuple = (255, 255, 255)) -> np.ndarray:
    """Render one platform style at 1024 (BGRA numpy).

    subject_rgba: BGRA subject image (may be empty 1x1 for text-only).
    style_id: big_sur / catalina / classic / ios / android / folder_* /
              document_* / original.
    bg: chosen background QColor as (r, g, b, a).
    Returns 1024x1024 BGRA.  iOS output is opaque full-bleed (alpha=255).
    """
    if text_items_data is None:
        text_items_data = []
    if canvas_ref_size is None:
        canvas_ref_size = (1024, 1024)

    if subject_rgba is None or subject_rgba.size == 0:
        subject_rgba = np.zeros((1, 1, 4), dtype=np.uint8)

    styled_np = None
    if style_id in ICON_STYLES:
        if style_id == "android":
            # Android export & preview share the adaptive-icon composition so
            # the editor shows exactly the square background + foreground the
            # Android Icon Set export produces (no pre-rounded circle).
            # When the user hasn't picked a background colour, default to a
            # neutral white (NOT a hard-coded blue) for the square layer.
            engine = IconStyleEngine(size=1024)
            engine.background_color = bg
            bg_rgb = bg[:3] if len(bg) >= 4 and bg[3] > 0 else (255, 255, 255)
            # glyph: tight-cropped subject (logo + later text overlay)
            glyph_bgra = engine.make_glyph(subject_rgba)
            from src.utils.export import _android_composite_preview
            styled_np = _android_composite_preview(glyph_bgra, bg_rgb)
        else:
            engine = IconStyleEngine(size=1024)
            engine.background_color = bg
            styled_np = engine.apply_style(subject_rgba, style_id,
                                           scale_multiplier=scale_multiplier)
    elif style_id == "folder_center":
        engine = FolderStyleEngine()
        styled_np = engine.apply_folder_style(
            subject_rgba, color=hex_color, layout="center",
            scale_multiplier=scale_multiplier)
    elif style_id == "folder_cover":
        engine = FolderStyleEngine()
        styled_np = engine.apply_folder_style(
            subject_rgba, color=hex_color, layout="cover",
            scale_multiplier=scale_multiplier)
    elif style_id == "document_center":
        engine = DocumentStyleEngine()
        styled_np = engine.apply_document_style(
            subject_rgba, color=doc_color, layout="center",
            scale_multiplier=scale_multiplier)
    elif style_id == "document_cover":
        engine = DocumentStyleEngine()
        styled_np = engine.apply_document_style(
            subject_rgba, color=doc_color, layout="cover",
            scale_multiplier=scale_multiplier)
    else:  # original
        styled_np = subject_rgba.copy()

    # All engines (and the original fallback) return at least 1x1; pad/scale to
    # a full-bleed 1024 canvas.  For the "original" style we keep the image at
    # its native size on a transparent 1024 canvas (only used as a preview; the
    # export path special-cases original-size PNGs anyway).
    if style_id == "original":
        h, w = styled_np.shape[:2]
        canvas = np.zeros((1024, 1024, 4), dtype=np.uint8)
        # center-fit, cap at 1024
        scale = min(1.0, 1024 / max(w, h))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        if (nw, nh) != (w, h):
            styled_np = cv2.resize(styled_np, (nw, nh),
                                   interpolation=cv2.INTER_AREA)
        h, w = styled_np.shape[:2]
        canvas[(1024 - h) // 2:(1024 - h) // 2 + h,
               (1024 - w) // 2:(1024 - w) // 2 + w] = styled_np
        styled_np = canvas
    elif styled_np.shape[0] != 1024 or styled_np.shape[1] != 1024:
        styled_np = cv2.resize(styled_np, (1024, 1024),
                               interpolation=cv2.INTER_AREA)

    # Text overlays are drawn on the same 1024 canvas in both preview & export.
    if text_items_data:
        styled_np = draw_text_on_np(styled_np, text_items_data, canvas_ref_size)

    # iOS: full-bleed opaque (no alpha anywhere) - mirrors the export rule.
    if style_id == "ios":
        rgba_pil = Image.fromarray(cv2.cvtColor(styled_np, cv2.COLOR_BGRA2RGBA))
        base_rgb = bg[:3] if len(bg) >= 3 and bg[3] > 0 else (255, 255, 255)
        opaque = Image.new("RGBA", rgba_pil.size, (*base_rgb, 255))
        merged = Image.alpha_composite(opaque, rgba_pil).convert("RGB")
        styled_np = cv2.cvtColor(np.array(merged), cv2.COLOR_RGB2BGRA)
        styled_np[..., 3] = 255

    return styled_np
