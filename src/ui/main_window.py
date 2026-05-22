from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QPushButton, QDialog, QLabel
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QImage, QPainter
from src.ui.bottom_bar import BottomBar
from src.ui.preview_gallery import PreviewGallery
from src.ui.canvas import IconifyCanvas, InteractiveTextItem
from src.engine.processor import ImageProcessor
from src.engine.rembg_worker import RembgWorker
from src.engine.inpaint_worker import InpaintWorker
from src.engine.preview_worker import PreviewWorker
from src.engine.icon_styles import IconStyleEngine
from src.engine.folder_styles import FolderStyleEngine
from src.engine.document_styles import DocumentStyleEngine
from src.utils.export import export_icns, export_png_set
from src.utils.text_renderer import serialize_text_item, draw_text_on_np
import numpy as np

class ModernMessageBox(QDialog):
    def __init__(self, parent=None, title="Notification", text="", is_error=False, is_warning=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.drag_pos = QPoint()
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1) # Space for border
        
        # Central styled widget
        self.container = QWidget()
        self.container.setObjectName("Container")
        
        # Color schemes based on warning/error/info
        if is_error:
            border_color = "rgba(255, 69, 58, 0.5)" # Reddish border
            title_color = "#ff453a"
        elif is_warning:
            border_color = "rgba(255, 159, 10, 0.5)" # Orangey border
            title_color = "#ff9f0a"
        else:
            border_color = "rgba(191, 90, 242, 0.4)" # Purple border
            title_color = "#bf5af2"
            
        self.container.setStyleSheet(f"""
            #Container {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 rgba(80, 30, 140, 235), 
                    stop:0.5 rgba(40, 15, 80, 245), 
                    stop:1 rgba(20, 5, 40, 250));
                border: 1px solid {border_color};
                border-radius: 16px;
            }}
            QLabel {{
                color: #ffffff;
                background: transparent;
            }}
        """)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(24, 20, 24, 18)
        container_layout.setSpacing(14)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {title_color};")
        container_layout.addWidget(self.title_label)
        
        # Text/Message
        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 13px; color: #e5e5e7; line-height: 18px;")
        container_layout.addWidget(self.message_label)
        
        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        # OK Button
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background: #bf5af2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #d07cff;
            }
            QPushButton:pressed {
                background: #a745db;
            }
        """)
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)
        
        container_layout.addLayout(btn_layout)
        layout.addWidget(self.container)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    @staticmethod
    def show_info(parent, title, text):
        box = ModernMessageBox(parent, title, text, is_error=False, is_warning=False)
        box.exec()
        
    @staticmethod
    def show_warning(parent, title, text):
        box = ModernMessageBox(parent, title, text, is_error=False, is_warning=True)
        box.exec()
        
    @staticmethod
    def show_error(parent, title, text):
        box = ModernMessageBox(parent, title, text, is_error=True, is_warning=False)
        box.exec()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("IconifyGo")
        self.setFixedSize(510, 555) # Tight initial size: 450(canvas) + 60(margins)
        
        # Enable Glass/Translucent background

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
            #CentralWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 rgba(80, 30, 140, 200), 
                    stop:0.5 rgba(40, 15, 80, 220), 
                    stop:1 rgba(20, 5, 40, 240));
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 20px;
            }
            QLabel { color: white; }
        """)

        self.image_processor = ImageProcessor()
        self.bg_worker = None
        self.inpaint_worker = None
        self.preview_worker = None
        self.selected_model = "isnet-general-use"
        self.inpaint_strength = "medium"
        self.style_bg_colors = {}
        self.style_subject_scales = {}

        # Timer for throttled refresh of the MAIN CANVAS ONLY (for smooth drawing)
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh_canvas_only)
        self.refresh_interval = 33 # ~30 FPS

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._run_async_preview)

        self.init_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def init_ui(self) -> None:
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Left Side (Canvas + BottomBar)
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 30, 0, 0) # 30px top margin, 0px left/right/bottom margins so bottom bar spans window width
        self.left_layout.setSpacing(30) # 30px gap below canvas (equidistant from top)
        
        self.canvas = IconifyCanvas()
        self.left_layout.addWidget(self.canvas)
        self.left_layout.setAlignment(self.canvas, Qt.AlignCenter)
        
        self.bottom_bar = BottomBar()
        self.left_layout.addWidget(self.bottom_bar)
        
        self.main_layout.addWidget(self.left_widget, 1)

        # macOS Style Traffic Lights (Top Left)
        self.controls_widget = QWidget(self.central_widget)
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(15, 15, 0, 0)
        self.controls_layout.setSpacing(8)
        
        # Close (Red)
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(12, 12)
        self.close_btn.setStyleSheet("""
            QPushButton { 
                background-color: #ff5f56; 
                border-radius: 6px; 
                border: none; 
                color: transparent;
                font-size: 9px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover { 
                background-color: #ff7b72; 
                color: rgba(0, 0, 0, 150);
            }
        """)
        self.close_btn.clicked.connect(self.close)
        
        # Minimize (Yellow)
        self.min_btn = QPushButton("-")
        self.min_btn.setFixedSize(12, 12)
        self.min_btn.setStyleSheet("""
            QPushButton { 
                background-color: #ffbd2e; 
                border-radius: 6px; 
                border: none; 
                color: transparent;
                font-size: 14px;
                font-weight: bold;
                padding-bottom: 3px;
            }
            QPushButton:hover { 
                background-color: #ffcf67; 
                color: rgba(0, 0, 0, 150);
            }
        """)
        self.min_btn.clicked.connect(self.showMinimized)
        
        # Maximize (Green - Disabled)
        self.max_btn = QPushButton()
        self.max_btn.setFixedSize(12, 12)
        self.max_btn.setEnabled(False)
        self.max_btn.setStyleSheet("""
            QPushButton { background-color: #4d4d4d; border-radius: 6px; border: none; }
        """)
        
        self.controls_layout.addWidget(self.close_btn)
        self.controls_layout.addWidget(self.min_btn)
        self.controls_layout.addWidget(self.max_btn)
        self.controls_widget.adjustSize()
        self.controls_widget.move(0, 0)
        
        # Right Side (Gallery)
        self.gallery = PreviewGallery()
        self.main_layout.addWidget(self.gallery)
        self.gallery.hide() # Hide by default
        
        # Connect signals
        self.bottom_bar.remove_bg_clicked.connect(self.remove_background)
        self.bottom_bar.tool_changed.connect(self.set_active_tool)
        self.bottom_bar.wm_tool_changed.connect(self.set_wm_tool)
        self.bottom_bar.brush_size_changed.connect(self.canvas.set_brush_size)
        self.bottom_bar.brush_shape_changed.connect(self.canvas.set_brush_shape)
        self.bottom_bar.export_clicked.connect(self.export_result)
        self.bottom_bar.erase_watermark_clicked.connect(self.erase_watermark)
        self.bottom_bar.reset_clicked.connect(self.reset_image)
        self.bottom_bar.text_added.connect(self.on_text_added)
        self.bottom_bar.bg_color_changed.connect(self.on_bg_color_changed)
        self.bottom_bar.sketch_clicked.connect(self.apply_sketch)

        self.canvas.mask_updated.connect(self.handle_mask_update)
        self.canvas.canvas_clicked.connect(self.open_file)
        self.canvas.file_dropped.connect(self.open_file_from_path)
        self.gallery.style_selected.connect(self.on_preview_style_selected)
        self.bottom_bar.subject_scale_changed.connect(self.on_subject_scale_changed)
        self.canvas.text_item_changed.connect(self.refresh_all)
        self.canvas.text_item_double_clicked.connect(self.on_text_item_double_clicked)

    def on_text_added(self, text, params):
        item = InteractiveTextItem(
            text=text,
            font_name=params.get("font_name", "Arial"),
            font_size=params.get("font_size", 40),
            color=params.get("color", (255, 255, 255)),
            weight=params.get("weight", "Regular"),
            alignment=params.get("alignment", "center")
        )
        # Center the text item on the scene (0, 0)
        orig_w = item.orig_rect.width()
        orig_h = item.orig_rect.height()
        item.setPos(-orig_w / 2.0, -orig_h / 2.0)

        self.canvas.scene.addItem(item)
        self.canvas.scene.clearSelection()
        item.setSelected(True)
        self.bottom_bar.set_tool("pointer")
        self.canvas.set_tool("pointer")

        # Hide the placeholder label since we added text
        self.canvas.update_placeholder_visibility()

        # Show gallery and adjust window size if hidden
        if self.gallery.isHidden():
            self.style_bg_colors = {}
            self.gallery.select_style("original")
            self.setFixedSize(710, 555)
            self.gallery.show()

        self.refresh_all()

    def on_text_item_double_clicked(self, item: InteractiveTextItem):
        from src.ui.popover import ActionPopover
        from src.ui.bottom_bar import TextSettingsWidget
        from PySide6.QtGui import QColor

        popover = ActionPopover(self)
        content = TextSettingsWidget()
        content.set_values(
            text=item.text,
            font_name=item.font_name,
            font_size=item.font_size,
            color=item.color,
            weight=item.weight,
            alignment=item.alignment
        )

        def on_accepted(text, params):
            if not text.strip():
                self.canvas.scene.removeItem(item)
                self.canvas.update_placeholder_visibility()
            else:
                item.text = text
                item.font_name = params.get("font_name", "Arial")
                item.font_size = params.get("font_size", 40)
                item.color = QColor(*params.get("color", (255, 255, 255)))
                item.weight = params.get("weight", "Regular")
                item.alignment = params.get("alignment", "center")
                item.update_font()
                item.update()
            self.refresh_all()
            popover.close()

        content.accepted.connect(on_accepted)
        content.rejected.connect(popover.close)
        popover.set_widget(content)
        popover.show_above(self.bottom_bar.text_btn)

    def on_subject_scale_changed(self, scale: float) -> None:
        selected_style = self.gallery.selected_style_id
        if selected_style and selected_style != "original":
            self.style_subject_scales[selected_style] = scale
            self.on_preview_style_selected(selected_style)
            self.preview_timer.start(300)

    def reset_image(self) -> None:
        """Reset the image to its original state."""
        if self.image_processor.current_image is None:
            return
        
        if self.image_processor.reset_to_original():
            self.bottom_bar.show_message("Reset to original image", 3000)
            self.refresh_all()
        else:
            ModernMessageBox.show_warning(self, "Warning", "No original image to restore.")

    def erase_watermark(self, strength: str) -> None:
        """Trigger async inpainting on the current image using the watermark mask."""
        self.inpaint_strength = strength
        self.canvas.set_mode('wm')
        if self.image_processor.current_image is None:
            return

        params = self.image_processor.get_inpaint_params()
        if params is None:
            return

        self.bottom_bar.erase_btn.setEnabled(False)
        self.bottom_bar.show_message("Removing watermark...", 0)  # Use 0 timeout to prevent auto-clear
        self.bottom_bar.set_progress_active(True)

        self.inpaint_worker = InpaintWorker(params[0], params[1], strength=self.inpaint_strength)
        self.inpaint_worker.progress.connect(lambda msg: self.bottom_bar.show_message(msg, 0))
        self.inpaint_worker.finished.connect(self.on_inpaint_done)
        self.inpaint_worker.error.connect(self.on_inpaint_error)
        self.inpaint_worker.start()

    def on_inpaint_done(self, result_image) -> None:
        """Handle successful inpaint result."""
        self.image_processor.apply_inpaint_result(result_image)
        self.refresh_all()
        self.bottom_bar.erase_btn.setEnabled(True)
        self.bottom_bar.show_message("Watermark removed successfully", 3000)
        self.bottom_bar.set_progress_active(False)
        # Reset tool to pointer and mode to bg on successful completion
        self.set_active_tool("pointer")
        pointer_btn = self.bottom_bar.tool_group.button(0)
        if pointer_btn:
            pointer_btn.setChecked(True)

    def on_inpaint_error(self, error_msg) -> None:
        """Handle inpaint failure."""
        ModernMessageBox.show_error(self, "Error", f"Watermark removal failed: {error_msg}")
        self.bottom_bar.erase_btn.setEnabled(True)
        self.bottom_bar.set_progress_active(False)

    def set_active_tool(self, tool_name: str) -> None:
        """Set the active canvas tool for background removal mode."""
        self.canvas.set_mode('bg')
        self.canvas.set_tool(tool_name)
        self.bottom_bar.erase_btn.setChecked(False)

    def set_wm_tool(self, tool_name: str) -> None:
        """Set the active canvas tool for watermark removal mode."""
        self.canvas.set_mode('wm')
        self.canvas.set_tool(tool_name)
        self.bottom_bar.erase_btn.setChecked(True)
        self.bottom_bar.clear_regular_tools()

    def handle_mask_update(self, update_info: tuple) -> None:
        if self.image_processor.current_image is None:
            return

        mode, tool_name = update_info[0], update_info[1]
        if tool_name == "brush":
            # Now supports mode and shape argument: (mode, "brush", start, end, radius, value, shape)
            _, _, start, end, radius, value, shape = update_info
            
            if mode == "wm":
                self.image_processor.brush_on_watermark_mask(start, end, radius, value, shape)
            else:
                self.image_processor.brush_on_mask(start, end, radius, value, shape)
                
            if not self.refresh_timer.isActive():
                self.refresh_timer.start(self.refresh_interval)
        elif tool_name == "brush_release":
            # Expensive full refresh ONLY when the user stops drawing
            self.refresh_all()

    def refresh_canvas_only(self) -> None:
        """Lightweight refresh of the main editing area only."""
        pixmap = self.image_processor.get_qpixmap()
        if pixmap:
            if self.canvas.image_item:
                self.canvas.image_item.setPixmap(pixmap)
            else:
                self.canvas.add_image(pixmap)

    def refresh_all(self) -> None:
        """Refreshes both the editing canvas and the preview gallery."""
        self.refresh_canvas_only()
        # Trigger debounced async update
        self.preview_timer.start(300)

    def on_bg_color_changed(self, color) -> None:
        """Handle background color change from the toolbar palette button."""
        from PySide6.QtGui import QColor
        if isinstance(color, QColor):
            selected_style = self.gallery.selected_style_id
            self.style_bg_colors[selected_style] = color
            self.canvas.set_bg_color(color)
            self.bottom_bar.current_bg_color = color
            # Re-generate active styled preview if any
            if selected_style != "original":
                self.on_preview_style_selected(selected_style)
            # Re-generate the gallery previews in the sidebar to reflect the new background color
            self._run_async_preview()

    def get_canvas_ref_size(self) -> tuple:
        if self.canvas.preview_item and self.canvas.preview_item.pixmap():
            pm = self.canvas.preview_item.pixmap()
            return pm.width(), pm.height()
        elif self.canvas.image_item and self.canvas.image_item.pixmap():
            pm = self.canvas.image_item.pixmap()
            return pm.width(), pm.height()
        else:
            return 512, 512

    def get_subject_image_with_text(self) -> Optional[np.ndarray]:
        import numpy as np
        import cv2
        rgba = self.image_processor.get_rgba_image(show_watermark=False)
        text_items = [item for item in self.canvas.scene.items() if isinstance(item, InteractiveTextItem) and item.text.strip()]
        
        if rgba is None:
            if not text_items:
                return None
            # No image, but we have text items! Create a transparent 512x512 canvas
            h, w = 512, 512
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
        else:
            if not text_items:
                return rgba
            h, w = rgba.shape[:2]

        from typing import Optional

        # Convert BGRA (which rgba is) to RGBA so QImage(..., QImage.Format_RGBA8888) matches memory structure
        rgba_rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)
        qimg = QImage(rgba_rgba.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()

        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        for item in text_items:
            painter.save()

            # Calculate local position on the image
            pos = item.pos()
            tx = pos.x() + w / 2.0
            ty = pos.y() + h / 2.0

            # Translate to the item's position on the image
            painter.translate(tx, ty)

            # Apply the item's scale
            s = item.scale()
            painter.scale(s, s)

            # Paint the item in rendering mode
            item.rendering_mode = True
            item.paint(painter, None, None)
            item.rendering_mode = False

            painter.restore()

        painter.end()

        # Convert QImage back to RGBA numpy array
        arr_rgba = np.frombuffer(qimg.constBits(), dtype=np.uint8).reshape((h, w, 4)).copy()
        # Convert RGBA back to BGRA numpy array
        arr = cv2.cvtColor(arr_rgba, cv2.COLOR_RGBA2BGRA)
        return arr

    def on_preview_style_selected(self, style_id: str) -> None:
        """Generate styled image and display it in the canvas when a preview is clicked."""
        from PySide6.QtGui import QColor
        bg = self.style_bg_colors.get(style_id, QColor(0, 0, 0, 0))
        self.canvas.set_bg_color(bg)
        self.bottom_bar.current_bg_color = bg

        if style_id == "original":
            self.bottom_bar.scale_btn.setEnabled(False)
            self.bottom_bar.set_subject_scale(1.0)
        else:
            self.bottom_bar.scale_btn.setEnabled(True)
            scale = self.style_subject_scales.get(style_id, 1.0)
            self.bottom_bar.set_subject_scale(scale)

        if style_id == "original":
            self.canvas.clear_preview()
            return

        rgba = self.image_processor.get_rgba_image(show_watermark=False)
        if rgba is None:
            rgba = np.zeros((1, 1, 4), dtype=np.uint8)

        import cv2
        from PySide6.QtGui import QImage, QPixmap

        # Get customized background color and format it for different engines
        bg_tuple = (bg.red(), bg.green(), bg.blue(), bg.alpha())
        if bg.alpha() == 0:
            hex_color = "#5ac8fa"
            doc_color = (255, 255, 255)
        else:
            r, g, b = bg_tuple[:3]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            doc_color = (r, g, b)

        scale_mult = self.style_subject_scales.get(style_id, 1.0)

        styled_np = None
        if style_id in ["big_sur", "catalina", "classic", "ios", "android"]:
            engine = IconStyleEngine()
            engine.background_color = bg_tuple
            styled_np = engine.apply_style(rgba, style_id, scale_multiplier=scale_mult)
        elif style_id == "folder_center":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, color=hex_color, layout="center", scale_multiplier=scale_mult)
        elif style_id == "folder_cover":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, color=hex_color, layout="cover", scale_multiplier=scale_mult)
        elif style_id == "document_center":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, color=doc_color, layout="center", scale_multiplier=scale_mult)
        elif style_id == "document_cover":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, color=doc_color, layout="cover", scale_multiplier=scale_mult)

        if styled_np is None:
            self.canvas.clear_preview()
            return

        # Convert BGRA numpy to QPixmap
        height, width = styled_np.shape[:2]
        rgb_img = cv2.cvtColor(styled_np, cv2.COLOR_BGRA2RGBA)
        qimg = QImage(rgb_img.data, width, height, 4 * width, QImage.Format_RGBA8888).copy()
        pixmap = QPixmap.fromImage(qimg)
        self.canvas.show_preview(pixmap)

    def _run_async_preview(self):
        rgba = self.image_processor.get_rgba_image(show_watermark=False)
        text_items = [item for item in self.canvas.scene.items() if isinstance(item, InteractiveTextItem) and item.text.strip()]
        
        if rgba is None and not text_items:
            # If no subject is available (no image and no text), hide the gallery
            self.canvas.clear_preview()
            if not self.gallery.isHidden() and self.image_processor.current_image is None:
                self.gallery.hide()
                self.setFixedSize(510, 555)
            return

        if rgba is None:
            rgba = np.zeros((1, 1, 4), dtype=np.uint8)

        # Stop current worker if it's already running
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.requestInterruption()
            self.preview_worker.wait()

        # Build style-specific background colors map for the preview generator
        from PySide6.QtGui import QColor
        bg_colors_dict = {}
        for s_id in ["original", "big_sur", "catalina", "classic", "ios", "android",
                     "folder_center", "folder_cover", "document_center", "document_cover"]:
            qcolor = self.style_bg_colors.get(s_id, QColor(0, 0, 0, 0))
            bg_colors_dict[s_id] = (qcolor.red(), qcolor.green(), qcolor.blue(), qcolor.alpha())

        text_items_data = [serialize_text_item(item) for item in text_items]
        canvas_ref_size = self.get_canvas_ref_size()

        self.preview_worker = PreviewWorker(
            rgba_image=rgba,
            bg_colors=bg_colors_dict,
            subject_scales=self.style_subject_scales,
            text_items_data=text_items_data,
            canvas_ref_size=canvas_ref_size
        )
        self.preview_worker.style_ready.connect(self.gallery.update_style_preview)
        self.preview_worker.start()

    def open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
        )
        if file_path:
            self.open_file_from_path(file_path)

    def open_file_from_path(self, file_path: str) -> None:
        if self.image_processor.load_image(file_path):
            self.style_bg_colors = {}
            self.gallery.select_style("original")
            pixmap = self.image_processor.get_qpixmap()
            if pixmap:
                self.canvas.add_image(pixmap)
            self.setFixedSize(710, 555) # Expand width for gallery (510 + 200)
            self.gallery.show() # Reveal gallery
            self.refresh_all()
        else:
            ModernMessageBox.show_error(self, "Error", f"Could not load image: {file_path}")

    def remove_background(self, model_name: str) -> None:
        self.selected_model = model_name
        self.canvas.set_mode('bg')
        if self.image_processor.current_image is None:
            ModernMessageBox.show_warning(self, "Warning", "Please load an image first.")
            return

        self.bottom_bar.remove_bg_btn.setEnabled(False)
        self.bottom_bar.show_message("Removing background...")
        self.bottom_bar.set_progress_active(True)

        self.bg_worker = RembgWorker(self.image_processor.current_image, model_name=self.selected_model)
        self.bg_worker.finished.connect(self.on_bg_removed)
        self.bg_worker.error.connect(self.on_bg_error)
        self.bg_worker.start()

    def on_bg_removed(self, result_image) -> None:
        self.image_processor.apply_bg_removed_mask(result_image)
        self.refresh_all()
        self.bottom_bar.remove_bg_btn.setEnabled(True)
        self.bottom_bar.show_message("Background removed successfully", 3000)
        self.bottom_bar.set_progress_active(False)

    def on_bg_error(self, error_msg) -> None:
        ModernMessageBox.show_error(self, "Error", f"Background removal failed: {error_msg}")
        self.bottom_bar.remove_bg_btn.setEnabled(True)
        self.bottom_bar.set_progress_active(False)

    def apply_sketch(self, kernel_size: int) -> None:
        """Applies pencil sketch filter with specified kernel size to the current image."""
        if self.image_processor.current_image is None:
            ModernMessageBox.show_warning(self, "Warning", "Please load an image first.")
            return

        if kernel_size == 0:
            if self.image_processor.restore_pre_sketch():
                self.bottom_bar.show_message("Restored original image", 3000)
                self.refresh_all()
            else:
                self.bottom_bar.show_message("Already at original image", 3000)
            return

        self.image_processor.apply_sketch_filter(kernel_size)
        self.bottom_bar.show_message("Converted to sketch style", 3000)
        self.refresh_all()

    def export_result(self, format_name: str) -> None:
        rgba = self.image_processor.get_rgba_image(show_watermark=False)
        text_items = [item for item in self.canvas.scene.items() if isinstance(item, InteractiveTextItem) and item.text.strip()]
        
        if rgba is None and not text_items:
            ModernMessageBox.show_warning(self, "Warning", "Please load an image or add text first.")
            return

        selected_style = self.gallery.selected_style_id

        from PIL import Image
        from src.engine.processor import cv2
        from PySide6.QtGui import QColor
        import numpy as np

        # Get customized background color and format it for different engines
        bg = self.style_bg_colors.get(selected_style, QColor(0, 0, 0, 0))
        bg_tuple = (bg.red(), bg.green(), bg.blue(), bg.alpha())
        if bg.alpha() == 0:
            hex_color = "#5ac8fa"
            doc_color = (255, 255, 255)
        else:
            r, g, b = bg_tuple[:3]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            doc_color = (r, g, b)

        # Get style-specific scale
        scale_mult = self.style_subject_scales.get(selected_style, 1.0)

        subject_rgba = rgba if rgba is not None else np.zeros((1, 1, 4), dtype=np.uint8)

        styled_np = None
        if selected_style in ["big_sur", "catalina", "classic", "ios", "android"]:
            engine = IconStyleEngine()
            engine.background_color = bg_tuple
            styled_np = engine.apply_style(subject_rgba, selected_style, scale_multiplier=scale_mult)
        elif selected_style == "folder_center":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(subject_rgba, color=hex_color, layout="center", scale_multiplier=scale_mult)
        elif selected_style == "folder_cover":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(subject_rgba, color=hex_color, layout="cover", scale_multiplier=scale_mult)
        elif selected_style == "document_center":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(subject_rgba, color=doc_color, layout="center", scale_multiplier=scale_mult)
        elif selected_style == "document_cover":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(subject_rgba, color=doc_color, layout="cover", scale_multiplier=scale_mult)

        if styled_np is None:
            if rgba is not None:
                styled_np = rgba.copy()
            else:
                styled_np = np.zeros((1024, 1024, 4), dtype=np.uint8)

        if text_items:
            text_items_data = [serialize_text_item(item) for item in text_items]
            canvas_ref_size = self.get_canvas_ref_size()
            styled_np = draw_text_on_np(styled_np, text_items_data, canvas_ref_size)

        styled_rgb = cv2.cvtColor(styled_np, cv2.COLOR_BGRA2RGBA)
        styled_pil = Image.fromarray(styled_rgb)
        
        # Composite background color behind original image if set
        if selected_style == "original":
            if bg.alpha() > 0:
                bg_layer = Image.new("RGBA", styled_pil.size, (bg.red(), bg.green(), bg.blue(), bg.alpha()))
                styled_pil = Image.alpha_composite(bg_layer, styled_pil)
        
        if ".icns" in format_name:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save ICNS Icon", "", "macOS Icon (*.icns)")
            if file_path:
                if export_icns(styled_pil, file_path):
                    ModernMessageBox.show_info(self, "Success", "Exported successfully")
        else:
            dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if dir_path:
                if export_png_set(styled_pil, dir_path):
                    ModernMessageBox.show_info(self, "Success", "Exported PNG set")

    def closeEvent(self, event) -> None:
        """Gracefully stop all background threads and timers on close to prevent segmentation faults."""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        if hasattr(self, 'preview_timer'):
            self.preview_timer.stop()
        if hasattr(self, 'canvas'):
            if hasattr(self.canvas, 'zoom_timer'):
                self.canvas.zoom_timer.stop()
            if hasattr(self.canvas, 'cleanup'):
                self.canvas.cleanup()

        # Shutdown workers
        for worker_name in ['bg_worker', 'inpaint_worker', 'preview_worker']:
            worker = getattr(self, worker_name, None)
            if worker and worker.isRunning():
                worker.requestInterruption()
                # Wait up to 1 second for the thread to exit cleanly, then terminate if it hangs
                if not worker.wait(1000):
                    worker.terminate()
                    worker.wait()

        event.accept()
