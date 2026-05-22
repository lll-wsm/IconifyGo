# src/ui/icons.py

# Template with placeholder for color
SVG_TEMPLATE = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="{path}" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

ICONS = {
    "pointer": "M4 4l7.07 16.97 2.51-7.39 7.39-2.51L4 4z",
    "brush": "M18 8V6a2 2 0 00-2-2H4a2 2 0 00-2 2v7a3 3 0 003 3 2 2 0 012 2v1a2 2 0 002 2h4a2 2 0 002-2v-5",
    "eraser": "M20 20H7L3 16C2 15 2 14 3 13L13 3C14 2 15 2 16 3L21 8C22 9 22 10 21 11L15 17",
    "sparkles": "M12 3v3m0 12v3M5.6 5.6l2.1 2.1m8.6 8.6l2.1 2.1M3 12h3m12 0h3M5.6 18.4l2.1-2.1m8.6-8.6l2.1-2.1",
    "broom": "M3 21l18-18M19 8l2 2-2 2M5 14l-2 2 2 2",
    "export": "M12 19V5m0 0L7 10m5-5l5 5M5 19h14",
    "reset": "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8m0 0V3m0 5h5",
    "shape": "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
    "size": "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3",
    "scale": "M15 3h6v6M9 21H3v-6M21 3L14 10M3 21l7-7",
    "text": "M5 7h14M12 7v12",
    "palette": "M12 2a10 10 0 000 20h1.5a1.5 1.5 0 001.12-2.5A1.5 1.5 0 0116 18h-2a10 10 0 01-2-20zM7 12a1 1 0 100-2M9.5 8a1 1 0 100-2M14.5 8a1 1 0 100-2M17 12a1 1 0 100-2",
    "pencil": "M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z",
    "wm_brush": "M18 4l2 2-10 10-3 1-1-3L16 4z M6 18a2 2 0 01-2-2c0-2 2-4 2-4s2 2 2 4a2 2 0 01-2 2z",
    "wm_eraser": "M20 20H7L3 16C2 15 2 14 3 13L13 3C14 2 15 2 16 3L21 8C22 9 22 10 21 11L15 17 M5 7a1.5 1.5 0 01-1.5-1.5c0-1.5 1.5-3 1.5-3s1.5 1.5 1.5 1.5A1.5 1.5 0 015 7z"
}

