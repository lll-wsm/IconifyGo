from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QPushButton
from PySide6.QtCore import QTimer, Qt
from src.ui.bottom_bar import BottomBar
from src.ui.preview_gallery import PreviewGallery
from src.ui.canvas import IconifyCanvas
from src.engine.processor import ImageProcessor
from src.engine.rembg_worker import RembgWorker
from src.engine.inpaint_worker import InpaintWorker
from src.engine.preview_worker import PreviewWorker
from src.engine.icon_styles import IconStyleEngine
from src.engine.folder_styles import FolderStyleEngine
from src.engine.document_styles import DocumentStyleEngine
from src.utils.export import export_icns, export_png_set

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("IconifyGo")
        self.resize(510, 555) # Tight initial size: 450(canvas) + 60(margins)
        
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
        self.bottom_bar.tool_changed.connect(self.canvas.set_tool)
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

    def on_text_added(self, text, params):
        self.image_processor.add_text_overlay(text, **params)
        self.refresh_all()

    def reset_image(self) -> None:
        """Reset the image to its original state."""
        if self.image_processor.current_image is None:
            return
        
        if self.image_processor.reset_to_original():
            self.bottom_bar.show_message("Reset to original image", 3000)
            self.refresh_all()
        else:
            QMessageBox.warning(self, "Warning", "No original image to restore.")

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
        self.bottom_bar.show_message("Removing watermark...")
        self.bottom_bar.set_progress_active(True)

        self.inpaint_worker = InpaintWorker(params[0], params[1], strength=self.inpaint_strength)
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

    def on_inpaint_error(self, error_msg) -> None:
        """Handle inpaint failure."""
        QMessageBox.critical(self, "Error", f"Watermark removal failed: {error_msg}")
        self.bottom_bar.erase_btn.setEnabled(True)
        self.bottom_bar.set_progress_active(False)

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

    def on_preview_style_selected(self, style_id: str) -> None:
        """Generate styled image and display it in the canvas when a preview is clicked."""
        from PySide6.QtGui import QColor
        bg = self.style_bg_colors.get(style_id, QColor(0, 0, 0, 0))
        self.canvas.set_bg_color(bg)
        self.bottom_bar.current_bg_color = bg

        rgba = self.image_processor.get_rgba_image(show_watermark=False)
        if rgba is None:
            return

        if style_id == "original":
            self.canvas.clear_preview()
            return

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

        styled_np = None
        if style_id in ["big_sur", "catalina", "classic", "ios", "android"]:
            engine = IconStyleEngine()
            engine.background_color = bg_tuple
            styled_np = engine.apply_style(rgba, style_id)
        elif style_id == "folder_center":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, color=hex_color, layout="center")
        elif style_id == "folder_cover":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, color=hex_color, layout="cover")
        elif style_id == "document_center":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, color=doc_color, layout="center")
        elif style_id == "document_cover":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, color=doc_color, layout="cover")

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
        if rgba is None: return

        # Stop current worker if it's already running
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.requestInterruption()
            self.preview_worker.wait()

        # Always pass transparent background color to the preview generator
        # so the gallery previews in the sidebar always show their default style/color.
        self.preview_worker = PreviewWorker(rgba, (0, 0, 0, 0))
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
            self.resize(710, 555) # Expand width for gallery (510 + 200)
            self.gallery.show() # Reveal gallery
            self.refresh_all()
        else:
            QMessageBox.critical(self, "Error", f"Could not load image: {file_path}")

    def remove_background(self, model_name: str) -> None:
        self.selected_model = model_name
        self.canvas.set_mode('bg')
        if self.image_processor.current_image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
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
        QMessageBox.critical(self, "Error", f"Background removal failed: {error_msg}")
        self.bottom_bar.remove_bg_btn.setEnabled(True)
        self.bottom_bar.set_progress_active(False)

    def apply_sketch(self, kernel_size: int) -> None:
        """Applies pencil sketch filter with specified kernel size to the current image."""
        if self.image_processor.current_image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return

        self.image_processor.apply_sketch_filter(kernel_size)
        self.bottom_bar.show_message("Converted to sketch style", 3000)
        self.refresh_all()

    def export_result(self, format_name: str) -> None:
        if self.image_processor.current_image is None:
            QMessageBox.warning(self, "Warning", "Please load and process an image first.")
            return

        rgba = self.image_processor.get_rgba_image()
        selected_style = self.gallery.selected_style_id

        from PIL import Image
        from src.engine.processor import cv2
        from PySide6.QtGui import QColor

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

        styled_np = None
        if selected_style in ["big_sur", "catalina", "classic", "ios", "android"]:
            engine = IconStyleEngine()
            engine.background_color = bg_tuple
            styled_np = engine.apply_style(rgba, selected_style)
        elif selected_style == "folder_center":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, color=hex_color, layout="center")
        elif selected_style == "folder_cover":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, color=hex_color, layout="cover")
        elif selected_style == "document_center":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, color=doc_color, layout="center")
        elif selected_style == "document_cover":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, color=doc_color, layout="cover")

        if styled_np is None:
            styled_np = rgba

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
                    QMessageBox.information(self, "Success", "Exported successfully")
        else:
            dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if dir_path:
                if export_png_set(styled_pil, dir_path):
                    QMessageBox.information(self, "Success", "Exported PNG set")
