from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, QRect, QSize, QEvent
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPolygon, QPen, QLinearGradient, QCursor

class ActionPopover(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.target_widget = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 15) # Extra bottom margin for arrow
        
        self.setStyleSheet("""
            ActionPopover {
                background: transparent;
            }
            QLabel {
                color: #eeeeee;
                font-size: 11px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 15);
                color: #eeeeee;
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 10);
            }
            QPushButton:checked {
                background-color: #bf5af2;
                border-color: #bf5af2;
            }
            QSlider::groove:horizontal {
                border: 1px solid rgba(255, 255, 255, 20);
                height: 4px;
                background: rgba(255, 255, 255, 15);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #bf5af2;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if getattr(self, "block_close", False):
                super().changeEvent(event)
                return
            if not self.isActiveWindow():
                active_window = QApplication.activeWindow()
                # Close only if the application loses focus to another application (active_window is None)
                if active_window is None:
                    self.close()
        super().changeEvent(event)

    def closeEvent(self, event):
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        super().closeEvent(event)

    def hideEvent(self, event):
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonPress:
            # Check if active window is a modal or independent color dialog/picker
            active_win = QApplication.activeWindow()
            if active_win and type(active_win).__name__ in ("QColorDialog", "QColorPicker"):
                return super().eventFilter(watched, event)

            click_pos = QCursor.pos()
            # If the click is physically inside the popover's geometry, do not close it
            if self.geometry().contains(click_pos):
                return super().eventFilter(watched, event)

            # Check if clicked widget is a descendant of the popover or is/within a QComboBoxListView
            is_descendant = False
            if isinstance(watched, QWidget):
                curr = watched
                while curr:
                    if curr == self or type(curr).__name__ == "QComboBoxListView":
                        is_descendant = True
                        break
                    curr = curr.parentWidget()
            else:
                # If watched is not a QWidget (e.g. a QWindow associated with the popover),
                # do not close the popover. Let the event filter wait for QWidget events.
                return super().eventFilter(watched, event)

            if not is_descendant:
                # Check if click is inside the target widget (the button that opened this popover)
                if hasattr(self, "target_widget") and self.target_widget:
                    target_rect = QRect(
                        self.target_widget.mapToGlobal(QPoint(0, 0)),
                        self.target_widget.size()
                    )
                    if target_rect.contains(click_pos):
                        # Clicked the toggle button itself. Close the popover and eat the event so it doesn't toggle back on
                        self.close()
                        return True
                
                # Clicked outside of everything. Close the popover and let the click propagate
                self.close()
                return False

        return super().eventFilter(watched, event)

    def set_widget(self, widget):
        # Clear existing
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.layout.addWidget(widget)

    def show_above(self, target_widget: QWidget):
        self.target_widget = target_widget
        self.adjustSize()
        target_pos = target_widget.mapToGlobal(QPoint(0, 0))
        target_rect = target_widget.rect()
        
        # Position centered above target
        x = target_pos.x() + (target_rect.width() - self.width()) // 2
        y = target_pos.y() - self.height() - 5
        
        self.move(x, y)
        self.show()
        # Install global event filter on the application to handle clicks outside the popover
        QApplication.instance().installEventFilter(self)

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
        
        # Use premium linear gradient matching the app's theme
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(80, 30, 140, 240))
        gradient.setColorAt(0.5, QColor(40, 15, 80, 245))
        gradient.setColorAt(1.0, QColor(20, 5, 40, 250))
        
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
        painter.drawPath(path)

