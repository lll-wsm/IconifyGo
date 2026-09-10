"""Platform-correct icon exporters for IconifyGo.

Design: everything exports from a 1024 full-bleed square master so all target
pipelines (macOS .iconset/.icns, iOS 1024 opaque PNG, Android adaptive layers,
Windows .ico / UWP assets) receive spec-correct input.
"""
import os
import platform
import shutil
import subprocess
import tempfile
from collections import Counter

import numpy as np
from PIL import Image

from src.engine.icon_presets import (
    ANDROID_ADAPTIVE_LAYER_DP,
    ANDROID_DENSITIES_DPX,
    ANDROID_SAFE_ZONE_DP,
    ICO_SIZES,
    ICONSET_FILES,
    IOS_MASTER_SIZE,
    PLAY_STORE_ICON_SIZE,
    WINDOWS_APP_ASSETS,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _to_square_rgba(pil_image: Image.Image) -> Image.Image:
    """Return a square RGBA image with content centered on transparent pad."""
    rgba = pil_image.convert("RGBA") if pil_image.mode != "RGBA" else pil_image
    w, h = rgba.size
    if w == h:
        return rgba
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(rgba, ((side - w) // 2, (side - h) // 2))
    return canvas


def _fit_square(pil_image: Image.Image, size: int) -> Image.Image:
    """Center-fit any image into a `size`x`size` RGBA canvas (letterboxed)."""
    rgba = _to_square_rgba(pil_image)
    if rgba.size[0] != size:
        rgba = rgba.resize((size, size), Image.Resampling.LANCZOS)
    return rgba


def _paste_centered(canvas: Image.Image, content: Image.Image, scale: float,
                    cx: float = 0.5, cy: float = 0.5) -> Image.Image:
    """Paste `content` (RGBA) centered on `canvas` (RGBA).  `scale` is the
    fraction of the canvas side that the content's bounding box will occupy.

    Resizing is done premultiplied (and un-premultiplied afterwards) so the
    transparent halo around a cutout never becomes a dark fringe on downscale.
    """
    cw, ch = canvas.size
    target = max(1, int(min(cw, ch) * scale))
    w, h = content.size
    aspect = w / h
    if aspect >= 1:
        nw, nh = target, max(1, int(target / aspect))
    else:
        nh, nw = target, max(1, int(target * aspect))
    content = _unpremultiply(
        _premultiply(content).resize((nw, nh), Image.Resampling.LANCZOS))
    ox = int(cw * cx - nw / 2)
    oy = int(ch * cy - nh / 2)
    canvas.alpha_composite(content, (ox, oy))
    return canvas


def _premultiply(pil_rgba: Image.Image) -> Image.Image:
    """Premultiply colour channels by alpha (float, straight -> premultiplied)."""
    arr = np.array(pil_rgba.convert("RGBA")).astype(np.float32)
    a = arr[..., 3:4] / 255.0
    arr[..., :3] *= a
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _unpremultiply(pil_rgba: Image.Image) -> Image.Image:
    """Undo premultiplication (premultiplied -> straight alpha)."""
    arr = np.array(pil_rgba.convert("RGBA")).astype(np.float32)
    a = arr[..., 3:4] / 255.0
    a[a == 0] = 1.0  # avoid div-by-zero on fully transparent pixels
    arr[..., :3] = np.clip(arr[..., :3] / a, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _opaque_rgb(pil_image: Image.Image) -> Image.Image:
    """Flatten onto white, drop alpha (iOS / Play Store safe)."""
    rgba = pil_image.convert("RGBA")
    base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(base, rgba).convert("RGB")


def _dominant_color(pil_rgba: Image.Image) -> tuple:
    """Return the modal opaque RGB (used as Android background when the user
    has not supplied an explicit flat bg color)."""
    small = pil_rgba.convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
    a = np.array(small)
    opaque = a[a[..., 3] > 200]
    if len(opaque) == 0:
        return (255, 255, 255)
    q = opaque[..., :3] // 24 * 24
    return Counter(map(tuple, q)).most_common(1)[0][0]


def _cutout_bg(pil_rgba: Image.Image, bg_rgb: tuple) -> Image.Image:
    """Turn a flat-colored composition into a transparent cutout (glyph +
    overlays) for Android adaptive foregrounds.

    Pixels close to the background color become transparent; a 1px alpha
    erosion removes the anti-aliased fringe along the glyph edges.
    """
    arr = np.array(pil_rgba.convert("RGBA")).astype(np.int16)
    dist = (np.abs(arr[..., 0] - bg_rgb[0]) +
            np.abs(arr[..., 1] - bg_rgb[1]) +
            np.abs(arr[..., 2] - bg_rgb[2]))
    match = (dist <= 30) & (arr[..., 3] > 250)
    arr[match, 3] = 0
    out = Image.fromarray(arr.astype(np.uint8), "RGBA")

    a = np.array(out.getchannel("A"))
    if a.max() > 0:
        import cv2
        a = cv2.erode(a, np.ones((3, 3), np.uint8), iterations=1)
        out.putalpha(Image.fromarray(a))
    return out


def _android_composite_preview(glyph_bgra: np.ndarray,
                               bg_rgb: tuple) -> np.ndarray:
    """Compose the Android icon the way a launcher shows it: square solid
    background + glyph (logo) centered at the legacy 48dp scale (~62% of the
    canvas).  Shared by the editor preview AND the Android Icon Set export so
    the two are pixel-identical.

    glyph_bgra: tight-cropped BGRA subject (logo, no plate).
    bg_rgb: opaque (r,g,b) of the square background layer.
    Returns BGRA 1024x1024.
    """
    import cv2
    glyph_rgba = cv2.cvtColor(glyph_bgra, cv2.COLOR_BGRA2RGBA)
    glyph = Image.fromarray(glyph_rgba)
    bg = Image.new("RGBA", (1024, 1024), (*bg_rgb, 255))
    layer = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    _paste_centered(layer, glyph, 0.62)   # legacy launcher 48dp scale
    composed = Image.alpha_composite(bg, layer)
    out = np.array(composed)
    return cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA)



def _iconutil_verify(icns_path: str) -> bool:
    """Structural sanity check: expand the .icns via Apple's iconutil into a
    temp .iconset (macOS only).  Best-effort; never blocks an export."""
    if not _is_macos():
        return True
    exe = shutil.which("iconutil")
    if not exe:
        return True
    tmp = os.path.join(tempfile.gettempdir(), "__ig_verify.iconset")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        res = subprocess.run([exe, "-c", "iconset", "-o", tmp, icns_path],
                             capture_output=True, text=True, timeout=120)
        return res.returncode == 0
    except Exception:
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# public exporters
# ---------------------------------------------------------------------------


def export_icns(pil_image: Image.Image, output_path: str) -> bool:
    """Export a full-bleed square as a macOS .icns (all standard sizes)."""
    try:
        rgba = _fit_square(pil_image, IOS_MASTER_SIZE)
        rgba.save(output_path, format="ICNS")
        _iconutil_verify(output_path)
        return True
    except Exception as e:
        print(f"Error exporting ICNS: {e}")
        return False


def export_ico(pil_image: Image.Image, output_path: str) -> bool:
    """Export a Windows .ico containing the standard sizes up to 256px."""
    try:
        rgba = _fit_square(pil_image, max(ICO_SIZES))
        rgba.save(output_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
        return True
    except Exception as e:
        print(f"Error exporting ICO: {e}")
        return False


def export_iconset_dir(pil_image: Image.Image, output_dir: str) -> bool:
    """Write the 10-file macOS .iconset directory (ready for `iconutil -c icns`)."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        rgba = _fit_square(pil_image, IOS_MASTER_SIZE)
        for fname, px in ICONSET_FILES:
            rgba.resize((px, px), Image.Resampling.LANCZOS).save(
                os.path.join(output_dir, fname))
        return True
    except Exception as e:
        print(f"Error exporting iconset: {e}")
        return False


def export_android_set(pil_image: Image.Image, output_dir: str,
                       bg_rgb: tuple = None) -> bool:
    """Platform-correct Android asset set.

    `pil_image` is either a transparent *glyph* of the subject (recommended —
    logo/text with transparent padding) or a full-bleed flat composition.  For
    a glyph the adaptive foreground is that glyph placed in the 66dp safe zone;
    for a flat composition it is chroma-keyed first.

    * res/mipmap-{mdpi..xxxhdpi}/ic_launcher_foreground.png — glyph fitted into
      the 66dp safe zone on a transparent layer;
    * .../ic_launcher_background.png — solid `bg_rgb` layer;
    * .../ic_launcher.png — legacy full square (bg + glyph);
    * res/mipmap-anydpi-v26/ic_launcher.xml — adaptive-icon manifest;
    * play_store_512.png — 512x512 full-bleed, opaque, sRGB.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        src = pil_image.convert("RGBA")
        # If it has transparency it's a glyph; if fully opaque it's a flat
        # plate/composition that we key on bg_rgb to obtain the glyph.
        alpha = np.array(src.getchannel("A"))
        if alpha.min() >= 250:
            if bg_rgb is None:
                bg_rgb = _dominant_color(src)
            glyph = _cutout_bg(src, bg_rgb)
        else:
            glyph = src
        if bg_rgb is None:
            bg_rgb = _dominant_color(src)

        # Crop the glyph to its visible content so placement/scaling below is
        # based on the logo, not on any transparent padding (matches the
        # editor preview exactly; also avoids dark fringe from resizing
        # transparent padding).
        # NOTE: crop the tight glyph directly — do NOT square-pad first, as
        # padding then re-cropping with the pre-pad bbox shifted the content
        # and clipped the bottom/right of non-square logos.
        bb = glyph.getbbox()
        if bb:
            glyph = glyph.crop(bb)
        bg = Image.new("RGBA", (IOS_MASTER_SIZE, IOS_MASTER_SIZE),
                       (*bg_rgb, 255))

        # adaptive foreground: glyph fitted to fill 100% of layer; the
        # *placed* result inside the safe zone is handled by the density size.
        safe_scale = ANDROID_SAFE_ZONE_DP / ANDROID_ADAPTIVE_LAYER_DP  # 66/108
        res_dir = os.path.join(output_dir, "res")
        for density, s in ANDROID_DENSITIES_DPX.items():
            layer_px = int(ANDROID_ADAPTIVE_LAYER_DP * s)
            d_dir = os.path.join(res_dir, f"mipmap-{density}")
            os.makedirs(d_dir, exist_ok=True)

            # adaptive foreground: transparent canvas, glyph within safe zone
            fg_layer = Image.new("RGBA", (layer_px, layer_px), (0, 0, 0, 0))
            _paste_centered(fg_layer, glyph, safe_scale)
            fg_layer.save(os.path.join(d_dir, "ic_launcher_foreground.png"))

            bg.resize((layer_px, layer_px), Image.Resampling.LANCZOS).save(
                os.path.join(d_dir, "ic_launcher_background.png"))

            # legacy launcher: square bg + glyph (full square, no clip)
            bg_small = bg.resize((layer_px, layer_px), Image.Resampling.LANCZOS)
            fg_comp = Image.new("RGBA", (layer_px, layer_px), (0, 0, 0, 0))
            _paste_centered(fg_comp, glyph, 0.62)
            Image.alpha_composite(bg_small, fg_comp).save(
                os.path.join(d_dir, "ic_launcher.png"))

        # Play Store listing icon (full square, no alpha, no shadow)
        layer1024 = Image.new("RGBA", (IOS_MASTER_SIZE, IOS_MASTER_SIZE),
                              (0, 0, 0, 0))
        _paste_centered(layer1024, glyph, 0.9)
        play = Image.alpha_composite(bg, layer1024)
        play_rgb = Image.alpha_composite(
            Image.new("RGBA", play.size, (*bg_rgb, 255)), play).convert("RGB")
        play_rgb.resize((PLAY_STORE_ICON_SIZE, PLAY_STORE_ICON_SIZE),
                        Image.Resampling.LANCZOS).save(
            os.path.join(output_dir, "play_store_512.png"))

        # adaptive-icon XML manifest
        v26 = os.path.join(res_dir, "mipmap-anydpi-v26")
        os.makedirs(v26, exist_ok=True)
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@mipmap/ic_launcher_background"/>\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_foreground"/>\n'
            '</adaptive-icon>\n'
        )
        with open(os.path.join(v26, "ic_launcher.xml"), "w") as f:
            f.write(xml)
        return True
    except Exception as e:
        print(f"Error exporting Android set: {e}")
        return False


def export_png_set(pil_image: Image.Image, output_dir: str,
                   bg_rgb: tuple = None, glyph: Image.Image = None) -> bool:
    """Full multi-platform asset set (macOS + iOS + Android + Windows).

    `pil_image` is the styled *plate* (used for macOS/iOS/Windows).  When
    `glyph` (transparent subject) is given it is used for the Android adaptive
    layer; otherwise Android is derived from the plate (flat styles only).
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        full = _fit_square(pil_image, IOS_MASTER_SIZE)

        # macOS: iconset files (+ icns on macOS)
        mac_dir = os.path.join(output_dir, "macOS.iconset")
        os.makedirs(mac_dir, exist_ok=True)
        for fname, px in ICONSET_FILES:
            full.resize((px, px), Image.Resampling.LANCZOS).save(
                os.path.join(mac_dir, fname))
        if _is_macos():
            export_icns(full, os.path.join(output_dir, "macOS.icns"))

        # iOS: opaque 1024
        _opaque_rgb(full).save(os.path.join(output_dir, "iOS_App_Icon_1024.png"))

        # Android
        if glyph is not None:
            export_android_set(glyph, os.path.join(output_dir, "Android"), bg_rgb)
        else:
            export_android_set(full, os.path.join(output_dir, "Android"), bg_rgb)

        # Windows: base UWP asset sizes (+ one scale-400)
        win_dir = os.path.join(output_dir, "Windows")
        os.makedirs(win_dir, exist_ok=True)
        for name, px in WINDOWS_APP_ASSETS:
            full.resize((px, px), Image.Resampling.LANCZOS).save(
                os.path.join(win_dir, f"{name}.png"))
        full.resize((44 * 4, 44 * 4), Image.Resampling.LANCZOS).save(
            os.path.join(win_dir, "Square44x44Logo.scale-400.png"))

        full.save(os.path.join(output_dir, "icon_1024x1024.png"))
        return True
    except Exception as e:
        print(f"Error exporting PNG set: {e}")
        return False
