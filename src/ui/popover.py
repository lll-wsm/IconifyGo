from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, QRect, QSize, QEvent
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPolygon

class ActionPopover(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 15) # Extra bottom margin for arrow
        
        self.setStyleSheet("""
            ActionPopover {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 12px;
            }
            QLabel { color: #eee; }
        """)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if getattr(self, "block_close", False):
                super().changeEvent(event)
                return
            if not self.isActiveWindow():
                active_window = QApplication.activeWindow()
                # Don't close if opening a color dialog or dropdown menu
                if active_window is not None:
                    win_type = type(active_window).__name__
                    if win_type in ("QColorDialog", "QComboBoxListView", "QMenu", "QColorPicker"):
                        super().changeEvent(event)
                        return
                self.close()
        super().changeEvent(event)

    def set_widget(self, widget):
        # Clear existing
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.layout.addWidget(widget)

    def show_above(self, target_widget: QWidget):
        self.adjustSize()
        target_pos = target_widget.mapToGlobal(QPoint(0, 0))
        target_rect = target_widget.rect()
        
        # Position centered above target
        x = target_pos.x() + (target_rect.width() - self.width()) // 2
        y = target_pos.y() - self.height() - 5
        
        self.move(x, y)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background bubble
        path = QPainterPath()
        rect = self.rect().adjusted(0, 0, 0, -10)
        path.addRoundedRect(rect, 12, 12)
        
        # Draw arrow
        arrow = QPolygon([
            QPoint(self.width() // 2 - 10, self.height() - 10),
            QPoint(self.width() // 2 + 10, self.height() - 10),
            QPoint(self.width() // 2, self.height())
        ])
        path.addPolygon(arrow)
        
        painter.setBrush(QColor("#2a2a2a"))
        painter.setPen(QColor("#444"))
        painter.drawPath(path)
