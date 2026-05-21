from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QFrame
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal
from typing import Optional, List

class PreviewItem(QFrame):
    clicked = Signal(str) # Emits style_id

    def __init__(self, label: str, style_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.style_id = style_id
        self.selected = False
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.set_selected(False)
        
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(100, 100)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.preview_label)
        
        self.text_label = QLabel(label)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet("color: #999; font-size: 10px; border: none; background: transparent;")
        self.layout.addWidget(self.text_label)

    def set_pixmap(self, pixmap: QPixmap):
        self.preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.style_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.setStyleSheet("background: #3c3c3c; border-radius: 8px; border: 2px solid #007aff;")
        else:
            self.setStyleSheet("background: #333; border-radius: 8px; border: 1px solid #444;")

class PreviewGallery(QScrollArea):
    style_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFixedWidth(160)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: #252526; }")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: #252526;")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(15)
        
        self.previews = {}
        self.selected_style_id = "big_sur"
        self.setup_previews()
        
        self.setWidget(self.container)
        self.select_style("big_sur")

    def setup_previews(self):
        # App Icons
        styles = [
            ("macOS Big Sur", "big_sur"),
            ("macOS Catalina", "catalina"),
            ("macOS Classic", "classic")
        ]
        for label, style_id in styles:
            item = PreviewItem(label, style_id)
            self.layout.addWidget(item)
            self.previews[style_id] = item
            item.clicked.connect(self.on_item_clicked)
            
        # Folders
        folders = [
            ("Folder (Center)", "folder_center"),
            ("Folder (Cover)", "folder_cover")
        ]
        for label, style_id in folders:
            item = PreviewItem(label, style_id)
            self.layout.addWidget(item)
            self.previews[style_id] = item
            item.clicked.connect(self.on_item_clicked)

        # Documents
        documents = [
            ("Document (Center)", "document_center"),
            ("Document (Cover)", "document_cover")
        ]
        for label, style_id in documents:
            item = PreviewItem(label, style_id)
            self.layout.addWidget(item)
            self.previews[style_id] = item
            item.clicked.connect(self.on_item_clicked)
            
        self.layout.addStretch()

    def on_item_clicked(self, style_id: str):
        self.select_style(style_id)
        self.style_selected.emit(style_id)

    def select_style(self, style_id: str):
        self.selected_style_id = style_id
        for s_id, item in self.previews.items():
            item.set_selected(s_id == style_id)

    def update_style_preview(self, style_id: str, pixmap: QPixmap):
        if style_id in self.previews:
            self.previews[style_id].set_pixmap(pixmap)
