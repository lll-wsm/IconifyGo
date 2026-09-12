"""Authoritative per-platform icon specs used by IconifyGo generators & exporters.

Values follow the public platform documentation:

iOS (App Store Connect / HIG)
    - 1024x1024 square, opaque (NO alpha channel), no pre-rounded corners
      (the system applies the squircle mask itself; App Store Connect rejects
      images that contain transparency).
    - Important content kept inside a central ~80% safe zone.

Android adaptive icon (developer.android.com/studio/write/create-app-icons)
    - Foreground + background layers, each 108x108 dp.
    - The masked (visible) viewport is 72x72 dp; masks may reach as little as
      33dp from the center, so a centered **66dp diameter CIRCLE** (radius 33dp)
      is the safe zone guaranteed not to be clipped (Google Design -
      "Designing Adaptive Icons").  Key logo content must be inscribed in it;
      the outer 18dp ring is bleed for system effects/parallax.

Android legacy / Play Store
    - Legacy launcher icons: square PNGs with alpha, 48 dp per density.
    - Google Play listing icon: 512x512 px, full-square artwork (Play applies
      its own ~30% radius mask), no shadow.

macOS app icon (HIG grid)
    - Source art should fill ~824/1024 (the system grid) with the squircle
      "apple shape"; transparency is allowed, but macOS does NOT round corners
      for you outside the asset pipeline, so pre-shaped art is what the tool
      exports into .icns/.iconset.

Windows (UWP/MSIX) base asset sizes (learn.microsoft.com/.../app-icon-construction)
    - Square44x44Logo etc. are base dp; exports provide scale-100..scale-400.
"""

# ---------------------------------------------------------------------------
# Android adaptive icons
# ---------------------------------------------------------------------------
#: dp size of each adaptive-icon layer canvas (foreground & background).
ANDROID_ADAPTIVE_LAYER_DP = 108
#: dp diameter of the guaranteed-visible (masked) viewport.
ANDROID_MASK_VIEWPORT_DP = 72
#: dp diameter of the never-clipped safe zone: a centered CIRCLE of this
#: diameter inside the 108dp layer (radius 33dp = the minimum mask reach).
ANDROID_SAFE_ZONE_DP = 66
#: safe-zone radius in dp (half of the diameter above).
ANDROID_SAFE_RADIUS_DP = ANDROID_SAFE_ZONE_DP / 2.0

#: px per dp at each generalized density (dpi / 160).
ANDROID_DENSITIES_DPX = {
    "mdpi": 1.0,    # ~160 dpi  -> 108 px layers, 66 px safe zone
    "hdpi": 1.5,    # ~240 dpi  -> 162 px
    "xhdpi": 2.0,   # ~320 dpi  -> 216 px
    "xxhdpi": 3.0,  # ~480 dpi  -> 324 px
    "xxxhdpi": 4.0, # ~640 dpi  -> 432 px
}

#: legacy launcher icon px at each density (48 dp * scale).
ANDROID_LEGACY_SIZES = {d: int(48 * s) for d, s in ANDROID_DENSITIES_DPX.items()}
#: 48x48 legacy source can be up-scaled safely; keep a single clean source size.
ANDROID_LEGACY_DP = 48

#: Play Store listing icon (512x512 full-bleed square PNG, no alpha, sRGB).
PLAY_STORE_ICON_SIZE = 512

# ---------------------------------------------------------------------------
# iOS
# ---------------------------------------------------------------------------
#: master export size for iOS app icons (must be >= 1024 per App Store Connect).
IOS_MASTER_SIZE = 1024

# ---------------------------------------------------------------------------
# macOS .iconset (10 files) -> iconutil
# ---------------------------------------------------------------------------
#: {"filename": (pixel_width, pixel_height)} with @2x handled by iconutil.
ICONSET_FILES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]

# ---------------------------------------------------------------------------
# Windows .ico multi-size (Vista+ max 256)
# ---------------------------------------------------------------------------
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

# ---------------------------------------------------------------------------
# Windows app package (UWP / MSIX) base asset sizes, at scale-100
# ---------------------------------------------------------------------------
WINDOWS_APP_ASSETS = [
    ("Square44x44Logo", 44),
    ("Square71x71Logo", 71),
    ("Square107x107Logo", 107),
    ("Square150x150Logo", 150),
    ("Square284x284Logo", 284),
    ("Square310x310Logo", 310),
    ("Square30x30Logo", 30),
    ("Square89x89Logo", 89),
    ("Square142x142Logo", 142),
    ("StoreLogo", 50),
]
