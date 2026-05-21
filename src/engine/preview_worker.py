# src/engine/preview_worker.py
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import numpy as np
import cv2
from .icon_styles import IconStyleEngine
from .folder_styles import FolderStyleEngine
from .document_styles import DocumentStyleEngine

class PreviewWorker(QThread):
    # Emit QImage instead of QPixmap, as QPixmap is not thread-safe and must only be handled in the main GUI thread.
    style_ready = Signal(str, QImage)

    def __init__(self, rgba_image: np.ndarray, bg_colors: dict):
        super().__init__()
        self.rgba = rgba_image.copy()
        self.preview_size = 512
        self.bg_colors = bg_colors
        self.icon_engine = IconStyleEngine(size=self.preview_size)
        self.folder_engine = FolderStyleEngine(size=self.preview_size)
        self.document_engine = DocumentStyleEngine(size=self.preview_size)

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

    def run(self):
        # 0. Original (No Background)
        if self.isInterruptionRequested(): return
        
        # Crop to content for the original preview
        from PIL import Image
        logo_pil = Image.fromarray(cv2.cvtColor(self.rgba, cv2.COLOR_BGRA2RGBA))
        bbox = logo_pil.getbbox()
        if bbox:
            logo_pil = logo_pil.crop(bbox)
        
        cropped_rgba = np.array(logo_pil.convert("RGBA"))
        
        # Composite background color behind original image if set
        bg_original = self.bg_colors.get("original", (0, 0, 0, 0))
        if bg_original[3] > 0:
            bg_layer = Image.new("RGBA", logo_pil.size, bg_original)
            logo_pil = Image.alpha_composite(bg_layer, logo_pil)
            cropped_rgba = np.array(logo_pil)
            
        cropped_bgra = cv2.cvtColor(cropped_rgba, cv2.COLOR_RGBA2BGRA)
        self.style_ready.emit("original", self._np_to_image(cropped_bgra))

        # 1. App Icons
        for style_id in ["big_sur", "catalina", "classic", "ios", "android"]:
            if self.isInterruptionRequested(): return
            bg = self.bg_colors.get(style_id, (0, 0, 0, 0))
            self.icon_engine.background_color = bg
            styled_np = self.icon_engine.apply_style(self.rgba, style_id)
            if styled_np is not None:
                self.style_ready.emit(style_id, self._np_to_image(styled_np))
                
        # 2. Folders
        if self.isInterruptionRequested(): return
        bg_folder_center = self.bg_colors.get("folder_center", (0, 0, 0, 0))
        hex_folder_center = self._get_hex_color(bg_folder_center)
        folder_center_np = self.folder_engine.apply_folder_style(
            self.rgba, color=hex_folder_center, opacity=1.0, scale=0.675, preset="generic", layout="center"
        )
        if folder_center_np is not None:
            self.style_ready.emit("folder_center", self._np_to_image(folder_center_np))

        if self.isInterruptionRequested(): return
        bg_folder_cover = self.bg_colors.get("folder_cover", (0, 0, 0, 0))
        hex_folder_cover = self._get_hex_color(bg_folder_cover)
        folder_cover_np = self.folder_engine.apply_folder_style(
            self.rgba, color=hex_folder_cover, opacity=1.0, scale=0.675, preset="generic", layout="cover"
        )
        if folder_cover_np is not None:
            self.style_ready.emit("folder_cover", self._np_to_image(folder_cover_np))

        # 3. Documents
        if self.isInterruptionRequested(): return
        bg_doc_center = self.bg_colors.get("document_center", (0, 0, 0, 0))
        doc_center_color = self._get_doc_color(bg_doc_center)
        doc_center_np = self.document_engine.apply_document_style(
            self.rgba, color=doc_center_color, opacity=1.0, scale=0.675, layout="center"
        )
        if doc_center_np is not None:
            self.style_ready.emit("document_center", self._np_to_image(doc_center_np))

        if self.isInterruptionRequested(): return
        bg_doc_cover = self.bg_colors.get("document_cover", (0, 0, 0, 0))
        doc_cover_color = self._get_doc_color(bg_doc_cover)
        doc_cover_np = self.document_engine.apply_document_style(
            self.rgba, color=doc_cover_color, opacity=1.0, scale=0.675, layout="cover"
        )
        if doc_cover_np is not None:
            self.style_ready.emit("document_cover", self._np_to_image(doc_cover_np))

    def _np_to_image(self, np_img: np.ndarray) -> QImage:
        height, width = np_img.shape[:2]
        rgb_img = cv2.cvtColor(np_img, cv2.COLOR_BGRA2RGBA)
        return QImage(rgb_img.data, width, height, 4 * width, QImage.Format_RGBA8888).copy()
