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
    "text": "M5 7h14M12 7v12"
}
