from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget, QLabel, QGraphicsEllipseItem, QGraphicsRectItem
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap, QWheelEvent, QMouseEvent, QPen, QPainterPath
from PySide6.QtCore import Qt, Signal, QPointF, QTimer, QPoint, QRectF
import numpy as np
import time
from typing import Optional

class IconifyCanvas(QGraphicsView):
    mask_updated = Signal(object)
    file_dropped = Signal(str)
    canvas_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Make the view itself transparent
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.viewport().setAttribute(Qt.WA_TranslucentBackground)
        
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.setFixedSize(450, 450)
        
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        
        self.setup_background()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.image_item: Optional[QGraphicsPixmapItem] = None
        self.bg_color_item: Optional[QGraphicsRectItem] = None
        self.preview_item: Optional[QGraphicsPixmapItem] = None
        self.bg_color = QColor(0, 0, 0, 0)  # Transparent by default
        
        # Dynamic Render Quality Timer
        self.zoom_timer = QTimer()
        self.zoom_timer.setSingleShot(True)
        self.zoom_timer.timeout.connect(self.restore_render_quality)
        self.is_zooming = False

        # Placeholder
        self.placeholder_label = QLabel("Click or Drag Image Here")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888; font-size: 14px; background: transparent;")
        self.placeholder_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.placeholder_proxy = self.scene.addWidget(self.placeholder_label)
        self.placeholder_proxy.setPos(-self.placeholder_label.width()/2, -self.placeholder_label.height()/2)
        
        # Cursor State
        self.brush_size = 20
        self.brush_shape = "Circle"
        self.brush_cursor = QGraphicsEllipseItem() 
        self.brush_cursor.setPen(QPen(QColor(255, 255, 255), 1.5)) 
        self.brush_cursor.setBrush(QBrush(QColor(0, 122, 255, 60))) 
        self.brush_cursor.setZValue(1000)
        self.brush_cursor.hide()
        self.scene.addItem(self.brush_cursor)

        self.current_tool = "pointer"
        self.current_mode = "bg"
        self.is_drawing = False
        self.is_panning = False
        self.pan_start_pos = QPoint()
        self.pan_sensitivity = 0.6  # Controlled sensitivity for smooth dragging
        self.fit_scale = 1.0
        self.last_point: Optional[QPointF] = None
        
        # Initialize default cursor to OpenHandCursor for pointer tool
        self.setCursor(Qt.OpenHandCursor)
        self.setMouseTracking(True)
        
        # Enable Drag and Drop
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def restore_render_quality(self):
        self.is_zooming = False
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.viewport().update()

    def setup_background(self) -> None:
        size = 20
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.fill(QColor(0, 0, 0, 0)) # Explicitly fully transparent
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        
        # Tile 1: Extreme subtle white/glass
        color1 = QColor(255, 255, 255, 5)
        # Tile 2: Extreme subtle purple tint
        color2 = QColor(191, 90, 242, 7)
        
        painter.fillRect(0, 0, size, size, color1)
        painter.fillRect(size, size, size, size, color1)
        painter.fillRect(size, 0, size, size, color2)
        painter.fillRect(0, size, size, size, color2)
        painter.end()
        self.setBackgroundBrush(QBrush(pixmap))

    def set_tool(self, tool_name: str) -> None:
        self.current_tool = tool_name
        if tool_name == "pointer":
            self.setCursor(Qt.OpenHandCursor)
            self.brush_cursor.hide()
        elif tool_name in ["brush", "eraser"]:
            self.setCursor(Qt.BlankCursor) 
            self.update_brush_cursor()
            self.brush_cursor.show()
        else:
            self.setCursor(Qt.CrossCursor)
            self.brush_cursor.hide()

    def set_mode(self, mode: str) -> None:
        self.current_mode = mode
        color = QColor(255, 102, 0, 60) if mode == "wm" else QColor(0, 122, 255, 60)
        self.brush_cursor.setBrush(QBrush(color))

    def set_brush_size(self, size: int) -> None:
        self.brush_size = size
        self.update_brush_cursor()

    def set_brush_shape(self, shape: str) -> None:
        self.brush_shape = shape
        old_pos = self.brush_cursor.pos()
        old_visible = self.brush_cursor.isVisible()
        self.scene.removeItem(self.brush_cursor)
        if shape == "Square": self.brush_cursor = QGraphicsRectItem()
        else: self.brush_cursor = QGraphicsEllipseItem()
        self.brush_cursor.setPen(QPen(QColor(255, 255, 255), 1.5)) 
        color = QColor(255, 102, 0, 60) if self.current_mode == "wm" else QColor(0, 122, 255, 60)
        self.brush_cursor.setBrush(QBrush(color)) 
        self.brush_cursor.setZValue(1000)
        self.brush_cursor.setPos(old_pos)
        if old_visible: self.brush_cursor.show()
        else: self.brush_cursor.hide()
        self.scene.addItem(self.brush_cursor)
        self.update_brush_cursor()

    def update_brush_cursor(self) -> None:
        radius = self.brush_size
        if self.brush_shape == "Ellipse":
            self.brush_cursor.setRect(-radius, -radius // 2, radius * 2, radius)
        else:
            self.brush_cursor.setRect(-radius, -radius, radius * 2, radius * 2)

    def add_image(self, pixmap: QPixmap) -> QGraphicsPixmapItem:
        for item in self.scene.items():
            if item != self.placeholder_proxy and item != self.brush_cursor:
                self.scene.removeItem(item)
        self.placeholder_proxy.hide()
        self.bg_color_item = None
        self.preview_item = None
        
        # Background color rectangle (behind the image, Z=0)
        rect = QRectF(-pixmap.width() / 2, -pixmap.height() / 2, pixmap.width(), pixmap.height())
        self.bg_color_item = QGraphicsRectItem(rect)
        self.bg_color_item.setBrush(QBrush(self.bg_color))
        self.bg_color_item.setPen(QPen(Qt.NoPen))
        self.bg_color_item.setZValue(0)
        self.scene.addItem(self.bg_color_item)
        
        # Main image (Z=1)
        self.image_item = self.scene.addPixmap(pixmap)
        self.image_item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        self.image_item.setZValue(1)
        
        # Add a subtle "glass" shadow/glow to the image
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(255, 255, 255, 30))
        shadow.setOffset(0, 0)
        self.image_item.setGraphicsEffect(shadow)
        
        self.resetTransform()
        self.fit_in_view()
        return self.image_item

    def set_bg_color(self, color: QColor) -> None:
        """Set the background color behind the image."""
        self.bg_color = color
        if self.bg_color_item:
            self.bg_color_item.setBrush(QBrush(color))

    def show_preview(self, pixmap: QPixmap) -> None:
        """Show a styled preview overlay on top of the image."""
        # Remove existing preview
        if self.preview_item:
            self.scene.removeItem(self.preview_item)
            self.preview_item = None
        
        if pixmap is None:
            return
        
        # Hide the original image so only the styled preview + bg color are visible
        if self.image_item:
            self.image_item.hide()
            
        self.preview_item = self.scene.addPixmap(pixmap)
        self.preview_item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        self.preview_item.setZValue(2)  # On top of everything
        
        # Hide the background color item for previews so the template shape is visible
        if self.bg_color_item:
            self.bg_color_item.hide()

        # Scale view down to fit the new preview item
        self.fit_in_view()

    def clear_preview(self) -> None:
        """Remove the styled preview overlay and restore the original image."""
        if self.preview_item:
            self.scene.removeItem(self.preview_item)
            self.preview_item = None
        
        # Show the original image again
        if self.image_item:
            self.image_item.show()
            # Restore bg_color_item to match original image dimensions and show it
            if self.bg_color_item:
                pm = self.image_item.pixmap()
                rect = QRectF(-pm.width() / 2, -pm.height() / 2, pm.width(), pm.height())
                self.bg_color_item.setRect(rect)
                self.bg_color_item.show()

        # Restore scale to fit main image dimensions
        self.fit_in_view()

    def fit_in_view(self) -> None:
        # Scale view dynamically to fit the currently active item (preview or original image)
        active_item = self.preview_item if self.preview_item else self.image_item
        if active_item:
            self.resetTransform()
            view_rect = self.viewport().rect()
            item_rect = active_item.pixmap().rect()
            scale = min(view_rect.width() / (item_rect.width() + 40), 
                        view_rect.height() / (item_rect.height() + 40))
            self.fit_scale = min(1.0, scale)
            if self.fit_scale < 1.0:
                self.scale(self.fit_scale, self.fit_scale)
            self.centerOn(active_item)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.image_item:
            return
        if not self.is_zooming:
            self.is_zooming = True
            self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.zoom_timer.start(150)

        current_scale = self.transform().m11()
        zoom_in = event.angleDelta().y() > 0
        
        # Calculate dynamic minimum scale limit: e.g., 0.5 of self.fit_scale
        min_scale = getattr(self, 'fit_scale', 1.0) * 0.5
        max_scale = 50.0  # Allow zoom in up to 50x
        
        if not zoom_in and current_scale <= min_scale:
            return
        if zoom_in and current_scale >= max_scale:
            return

        # Dampen zoom speed: 1.05 per standard notch (120 units)
        angle = event.angleDelta().y()
        zoom_factor = 1.0 + (abs(angle) / 1200.0) # ~1.1 at standard notch
        # Let's slow it down to ~1.05
        zoom_factor = 1.0 + (abs(angle) / 2400.0) 
        
        if angle < 0:
            zoom_factor = 1.0 / zoom_factor
            
        new_scale = current_scale * zoom_factor
        
        # Clamp scale to bounds
        if new_scale < min_scale:
            zoom_factor = min_scale / current_scale
        elif new_scale > max_scale:
            zoom_factor = max_scale / current_scale

        self.scale(zoom_factor, zoom_factor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.image_item:
            self.fit_in_view()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier) and event.key() == Qt.Key_0:
            self.fit_in_view()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.image_item is None:
            if event.button() == Qt.LeftButton:
                self.canvas_clicked.emit()
            return
        if event.button() == Qt.LeftButton:
            if self.current_tool == "pointer":
                self.is_panning = True
                self.pan_start_pos = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
            else:
                self.is_drawing = True
                self.last_point = self.mapToScene(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if getattr(self, 'is_panning', False):
            delta = event.pos() - self.pan_start_pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x() * self.pan_sensitivity))
            v_bar.setValue(v_bar.value() - int(delta.y() * self.pan_sensitivity))
            self.pan_start_pos = event.pos()
            return

        pos_scene = self.mapToScene(event.pos())
        if self.current_tool in ["brush", "eraser"]:
            self.brush_cursor.setPos(pos_scene)

        if self.is_drawing and self.image_item and self.current_tool in ["brush", "eraser"]:
            local_start = self.image_item.mapFromScene(self.last_point)
            local_end = self.image_item.mapFromScene(pos_scene)
            offset_x, offset_y = self.image_item.pixmap().width()/2, self.image_item.pixmap().height()/2
            start = (int(local_start.x() + offset_x), int(local_start.y() + offset_y))
            end = (int(local_end.x() + offset_x), int(local_end.y() + offset_y))
            value = 255 if self.current_tool == "brush" else 0
            self.mask_updated.emit((self.current_mode, "brush", start, end, self.brush_size, value, self.brush_shape))
            self.last_point = pos_scene

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if getattr(self, 'is_panning', False):
            self.is_panning = False
            if self.current_tool == "pointer":
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return

        if self.is_drawing:
            self.is_drawing = False
            if self.current_tool in ["brush", "eraser"]:
                self.mask_updated.emit((self.current_mode, "brush_release"))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.accept()
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.accept()
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')):
                event.acceptProposedAction()
                self.file_dropped.emit(file_path)
                break
