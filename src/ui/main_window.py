from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox
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
        self.resize(780, 600)
        self.setStyleSheet("background: #1e1e1e; color: #fff;")

        self.image_processor = ImageProcessor()
        self.bg_worker = None
        self.inpaint_worker = None
        self.preview_worker = None
        self.selected_model = "isnet-general-use"
        self.inpaint_strength = "medium"

        # Timer for throttled refresh of the MAIN CANVAS ONLY (for smooth drawing)
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh_canvas_only)
        self.refresh_interval = 33 # ~30 FPS

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._run_async_preview)

        self.init_ui()

    def init_ui(self) -> None:
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Left Side (Canvas + BottomBar)
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)
        
        self.canvas = IconifyCanvas()
        self.left_layout.addWidget(self.canvas, 1)
        self.left_layout.setAlignment(self.canvas, Qt.AlignCenter)
        
        self.bottom_bar = BottomBar()
        self.left_layout.addWidget(self.bottom_bar)
        
        self.main_layout.addWidget(self.left_widget, 1)
        
        # Right Side (Gallery)
        self.gallery = PreviewGallery()
        self.main_layout.addWidget(self.gallery)
        
        # Connect signals
        self.bottom_bar.remove_bg_clicked.connect(self.remove_background)
        self.bottom_bar.tool_changed.connect(self.canvas.set_tool)
        self.bottom_bar.brush_size_changed.connect(self.canvas.set_brush_size)
        self.bottom_bar.brush_shape_changed.connect(self.canvas.set_brush_shape)
        self.bottom_bar.export_clicked.connect(self.export_result)
        self.bottom_bar.erase_watermark_clicked.connect(self.erase_watermark)
        self.bottom_bar.reset_clicked.connect(self.reset_image)
        self.bottom_bar.text_added.connect(self.on_text_added)

        self.canvas.mask_updated.connect(self.handle_mask_update)
        self.canvas.canvas_clicked.connect(self.open_file)
        self.canvas.file_dropped.connect(self.open_file_from_path)

    def on_text_added(self, text, params):
        self.image_processor.add_text_overlay(text, **params)
        self.refresh_all()

    def reset_image(self) -> None:
        """Reset the image to its original state."""
        if self.image_processor.current_image is None:
            return
        
        if self.image_processor.reset_to_original():
            self.statusBar().showMessage("Reset to original image", 3000)
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
        self.statusBar().showMessage("Removing watermark...")

        self.inpaint_worker = InpaintWorker(params[0], params[1], strength=self.inpaint_strength)
        self.inpaint_worker.finished.connect(self.on_inpaint_done)
        self.inpaint_worker.error.connect(self.on_inpaint_error)
        self.inpaint_worker.start()

    def on_inpaint_done(self, result_image) -> None:
        """Handle successful inpaint result."""
        self.image_processor.apply_inpaint_result(result_image)
        self.refresh_all()
        self.bottom_bar.erase_btn.setEnabled(True)
        self.statusBar().showMessage("Watermark removed successfully", 3000)

    def on_inpaint_error(self, error_msg) -> None:
        """Handle inpaint failure."""
        QMessageBox.critical(self, "Error", f"Watermark removal failed: {error_msg}")
        self.bottom_bar.erase_btn.setEnabled(True)
        self.statusBar().clearMessage()

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

    def _run_async_preview(self):
        rgba = self.image_processor.get_rgba_image(show_watermark=False)
        if rgba is None: return

        # Stop current worker if it's already running
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.requestInterruption()
            self.preview_worker.wait()

        self.preview_worker = PreviewWorker(rgba)
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
            pixmap = self.image_processor.get_qpixmap()
            if pixmap:
                self.canvas.add_image(pixmap)
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
        self.statusBar().showMessage("Removing background...")

        self.bg_worker = RembgWorker(self.image_processor.current_image, model_name=self.selected_model)
        self.bg_worker.finished.connect(self.on_bg_removed)
        self.bg_worker.error.connect(self.on_bg_error)
        self.bg_worker.start()

    def on_bg_removed(self, result_image) -> None:
        self.image_processor.apply_bg_removed_mask(result_image)
        self.refresh_all()
        self.bottom_bar.remove_bg_btn.setEnabled(True)
        self.statusBar().showMessage("Background removed successfully", 3000)

    def on_bg_error(self, error_msg) -> None:
        QMessageBox.critical(self, "Error", f"Background removal failed: {error_msg}")
        self.bottom_bar.remove_bg_btn.setEnabled(True)
        self.statusBar().clearMessage()

    def export_result(self, format_name: str) -> None:
        if self.image_processor.current_image is None:
            QMessageBox.warning(self, "Warning", "Please load and process an image first.")
            return

        rgba = self.image_processor.get_rgba_image()
        selected_style = self.gallery.selected_style_id

        from PIL import Image
        from src.engine.processor import cv2

        styled_np = None
        if selected_style in ["big_sur", "catalina", "classic"]:
            engine = IconStyleEngine()
            styled_np = engine.apply_style(rgba, selected_style)
        elif selected_style == "folder_center":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, layout="center")
        elif selected_style == "folder_cover":
            engine = FolderStyleEngine()
            styled_np = engine.apply_folder_style(rgba, layout="cover")
        elif selected_style == "document_center":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, layout="center")
        elif selected_style == "document_cover":
            engine = DocumentStyleEngine()
            styled_np = engine.apply_document_style(rgba, layout="cover")

        if styled_np is None:
            styled_np = rgba

        styled_rgb = cv2.cvtColor(styled_np, cv2.COLOR_BGRA2RGBA)
        styled_pil = Image.fromarray(styled_rgb)
        
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
