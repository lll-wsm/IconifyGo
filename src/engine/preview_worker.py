# src/engine/preview_worker.py
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import numpy as np
import cv2
from src.engine.style_render import render_style_1024, render_original_native

class PreviewWorker(QThread):
    # Emit QImage instead of QPixmap, as QPixmap is not thread-safe and must only be handled in the main GUI thread.
    style_ready = Signal(str, QImage)

    def __init__(self, rgba_image: np.ndarray, bg_colors: dict, subject_scales: dict = None,
                 text_items_data: list = None, canvas_ref_size: tuple = (512, 512)):
        super().__init__()
        self.rgba = rgba_image.copy()
        self.preview_size = 512  # downscale target for the gallery
        self.bg_colors = bg_colors
        self.subject_scales = subject_scales if subject_scales is not None else {}
        self.text_items_data = text_items_data if text_items_data is not None else []
        self.canvas_ref_size = canvas_ref_size

    def _get_hex_color(self, bg_tuple: tuple) -> str:
        a = bg_tuple[3] if len(bg_tuple) >= 4 else 255
        if a == 0:
            return "#5ac8fa"
        else:
            r, g, b = bg_tuple[:3]
            return f"#{r:02x}{g:02x}{b:02x}"

    def _get_doc_color(self, bg_tuple: tuple) -> tuple:
        a = bg_tuple[3] if len(bg_tuple) >= 4 else 255
        if a == 0:
            return (255, 255, 255)
        else:
            return bg_tuple[:3]

    def _np_to_image(self, np_img: np.ndarray) -> QImage:
        height, width = np_img.shape[:2]
        rgb_img = cv2.cvtColor(np_img, cv2.COLOR_BGRA2RGBA)
        return QImage(rgb_img.data, width, height, 4 * width, QImage.Format_RGBA8888).copy()

    def _prepare_base(self):
        """Return BGRA subject numpy (unmodified; engines crop internally)."""
        return self.rgba

    def run(self):
        # 0. Original (No Background)
        if self.isInterruptionRequested(): return

        # original: subject with optional bg composite (native size, WYSIWYG
        # with the Original Size PNG export).
        bg_original = self.bg_colors.get("original", (0, 0, 0, 0))
        native = render_original_native(
            self.rgba, bg=bg_original,
            text_items_data=self.text_items_data,
            canvas_ref_size=self.canvas_ref_size)
        if self.isInterruptionRequested(): return
        # fit original into preview square
        h, w = native.shape[:2]
        canvas = np.zeros((self.preview_size, self.preview_size, 4), dtype=np.uint8)
        scale = min(1.0, self.preview_size / max(w, h))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        if (nw, nh) != (w, h):
            native = cv2.resize(native, (nw, nh), interpolation=cv2.INTER_AREA)
        h, w = native.shape[:2]
        canvas[(self.preview_size - h) // 2:(self.preview_size - h) // 2 + h,
               (self.preview_size - w) // 2:(self.preview_size - w) // 2 + w] = native
        self.style_ready.emit("original", self._np_to_image(canvas))

        # 1-3. All styled styles render through the SAME 1024 pipeline as export
        def _emit(style_id, np_bgra):
            """Downscale the 1024 render to the gallery size and emit."""
            if self.isInterruptionRequested():
                return
            h, w = np_bgra.shape[:2]
            if (w, h) != (self.preview_size, self.preview_size):
                np_bgra = cv2.resize(np_bgra, (self.preview_size, self.preview_size),
                                     interpolation=cv2.INTER_AREA)
            self.style_ready.emit(style_id, self._np_to_image(np_bgra))

        for style_id in ["big_sur", "catalina", "classic", "ios", "android",
                         "folder_center", "folder_cover",
                         "document_center", "document_cover"]:
            if self.isInterruptionRequested(): return
            bg = self.bg_colors.get(style_id, (0, 0, 0, 0))
            scale_mult = self.subject_scales.get(style_id, 1.0)
            try:
                styled_np = render_style_1024(
                    self.rgba, style_id,
                    bg=bg,
                    scale_multiplier=scale_mult,
                    text_items_data=self.text_items_data,
                    canvas_ref_size=self.canvas_ref_size,
                    hex_color=self._get_hex_color(bg),
                    doc_color=self._get_doc_color(bg),
                )
            except Exception as e:
                print(f"preview render error {style_id}: {e}")
                continue
            _emit(style_id, styled_np)
