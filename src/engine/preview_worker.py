# src/engine/preview_worker.py
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import numpy as np
import cv2
from .icon_styles import IconStyleEngine
from .folder_styles import FolderStyleEngine
from .document_styles import DocumentStyleEngine

class PreviewWorker(QThread):
    style_ready = Signal(str, QPixmap)

    def __init__(self, rgba_image: np.ndarray):
        super().__init__()
        self.rgba = rgba_image.copy()
        self.preview_size = 256
        self.icon_engine = IconStyleEngine(size=self.preview_size)
        self.folder_engine = FolderStyleEngine(size=self.preview_size)
        self.document_engine = DocumentStyleEngine(size=self.preview_size)

    def run(self):
        # 1. App Icons
        for style_id in ["big_sur", "catalina", "classic", "ios", "android"]:
            if self.isInterruptionRequested(): return
            styled_np = self.icon_engine.apply_style(self.rgba, style_id)
            if styled_np is not None:
                self.style_ready.emit(style_id, self._np_to_pixmap(styled_np))
                
        # 2. Folders
        if self.isInterruptionRequested(): return
        folder_center_np = self.folder_engine.apply_folder_style(
            self.rgba, color="#5ac8fa", opacity=1.0, scale=0.675, preset="generic", layout="center"
        )
        if folder_center_np is not None:
            self.style_ready.emit("folder_center", self._np_to_pixmap(folder_center_np))

        if self.isInterruptionRequested(): return
        folder_cover_np = self.folder_engine.apply_folder_style(
            self.rgba, color="#5ac8fa", opacity=1.0, scale=0.675, preset="generic", layout="cover"
        )
        if folder_cover_np is not None:
            self.style_ready.emit("folder_cover", self._np_to_pixmap(folder_cover_np))

        # 3. Documents
        if self.isInterruptionRequested(): return
        doc_center_np = self.document_engine.apply_document_style(
            self.rgba, opacity=1.0, scale=0.675, layout="center"
        )
        if doc_center_np is not None:
            self.style_ready.emit("document_center", self._np_to_pixmap(doc_center_np))

        if self.isInterruptionRequested(): return
        doc_cover_np = self.document_engine.apply_document_style(
            self.rgba, opacity=1.0, scale=0.675, layout="cover"
        )
        if doc_cover_np is not None:
            self.style_ready.emit("document_cover", self._np_to_pixmap(doc_cover_np))

    def _np_to_pixmap(self, np_img: np.ndarray) -> QPixmap:
        height, width = np_img.shape[:2]
        rgb_img = cv2.cvtColor(np_img, cv2.COLOR_BGRA2RGBA)
        qimg = QImage(rgb_img.data, width, height, 4 * width, QImage.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimg)
