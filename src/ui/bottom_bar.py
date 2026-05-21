from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, 
    QComboBox, QFrame, QButtonGroup, QPlainTextEdit, QColorDialog, QProgressBar
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QColor, QFontDatabase, QFont
from PySide6.QtCore import Qt, Signal, QByteArray, QPoint
from typing import Optional
from .icons import SVG_TEMPLATE, ICONS

class TextSettingsWidget(QWidget):
    accepted = Signal(str, dict)
    rejected = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("键入文本或表情符号")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #fff;")
        layout.addWidget(title)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("在此输入...")
        self.text_edit.setFixedHeight(60)
        self.text_edit.setStyleSheet("""
            QPlainTextEdit { 
                background: #1a1a1a; color: #eee; border: 1px solid #444; 
                border-radius: 4px; padding: 5px; 
            }
        """)
        layout.addWidget(self.text_edit)

        # Font and Weight
        font_layout = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.addItems(QFontDatabase().families())
        self.font_combo.setCurrentText("Arial")
        
        self.weight_combo = QComboBox()
        self.weight_combo.addItems(["Regular", "Bold", "Italic"])
        
        font_layout.addWidget(self.font_combo, 2)
        font_layout.addWidget(self.weight_combo, 1)
        layout.addLayout(font_layout)

        # Alignment and Color
        align_layout = QHBoxLayout()
        
        self.align_group = QButtonGroup(self)
        alignments = [("L", "left"), ("C", "center"), ("R", "right")]
        for i, (label, mode) in enumerate(alignments):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(30)
            btn.setProperty("mode", mode)
            if mode == "center":
                btn.setChecked(True)
            self.align_group.addButton(btn, i)
            align_layout.addWidget(btn)
        
        align_layout.addStretch()

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.current_color = QColor(0, 0, 0)
        self.update_color_button()
        self.color_btn.clicked.connect(self.choose_color)
        align_layout.addWidget(self.color_btn)
        
        layout.addLayout(align_layout)

        # Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("大小"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(10, 200)
        self.size_slider.setValue(40)
        size_layout.addWidget(self.size_slider)
        layout.addLayout(size_layout)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.rejected.emit)
        
        ok_btn = QPushButton("确认")
        ok_btn.setStyleSheet("background: #007aff; color: white; font-weight: bold;")
        ok_btn.clicked.connect(self.on_ok)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def update_color_button(self):
        self.color_btn.setStyleSheet(f"background-color: {self.current_color.name()}; border: 1px solid #666; border-radius: 4px;")

    def choose_color(self):
        from .popover import ActionPopover
        parent = self.parentWidget()
        while parent:
            if isinstance(parent, ActionPopover):
                break
            parent = parent.parentWidget()
            
        if parent:
            parent.block_close = True
            
        try:
            color = QColorDialog.getColor(self.current_color, self, "选择颜色", QColorDialog.ShowAlphaChannel)
            if color.isValid():
                self.current_color = color
                self.update_color_button()
        finally:
            if parent:
                parent.block_close = False

    def on_ok(self):
        text = self.text_edit.toPlainText()
        if not text:
            self.rejected.emit()
            return
            
        params = {
            "font_name": self.font_combo.currentText(),
            "font_size": self.size_slider.value(),
            "color": (self.current_color.red(), self.current_color.green(), self.current_color.blue()),
            "weight": self.weight_combo.currentText(),
            "alignment": self.align_group.checkedButton().property("mode")
        }
        self.accepted.emit(text, params)

class SvgIconButton(QPushButton):
    def __init__(self, icon_name, tooltip="", parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setToolTip(tooltip)
        self.setFixedSize(24, 24)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("border: none; background: transparent; border-radius: 6px;")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw subtle background if checked or hovered
        if self.isChecked() or self.underMouse():
            bg_color = QColor(255, 255, 255, 30) if not self.isChecked() else QColor(191, 90, 242, 60)
            painter.setBrush(bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 6, 6)
            
        # Prepare SVG
        color = "#bf5af2" if self.isChecked() else "#eeeeee"
        svg_data = SVG_TEMPLATE.format(path=ICONS[self.icon_name], color=color)
        
        renderer = QSvgRenderer(QByteArray(svg_data.encode()))
        
        # Center the icon
        margin = 5
        renderer.render(painter, self.rect().adjusted(margin, margin, -margin, -margin))
        painter.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

class BottomBar(QWidget):
    tool_changed = Signal(str)
    brush_size_changed = Signal(int)
    brush_shape_changed = Signal(str)
    remove_bg_clicked = Signal(str)
    export_clicked = Signal(str)
    erase_watermark_clicked = Signal(str)
    reset_clicked = Signal()
    text_added = Signal(str, dict)
    bg_color_changed = Signal(object)  # QColor
    sketch_clicked = Signal(int)
    wm_tool_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_bg_color = QColor(0, 0, 0, 0)
        self.init_ui()

    def init_ui(self) -> None:
        self.setFixedHeight(75) # Slightly taller to accommodate status label
        self.main_container = QVBoxLayout(self)
        self.main_container.setContentsMargins(0, 0, 0, 0)
        self.main_container.setSpacing(0)

        # 1. Top Bar (Tools)
        self.bar_widget = QWidget()
        self.bar_widget.setObjectName("BottomBarWidget")
        self.bar_widget.setFixedHeight(55)
        self.bar_widget.setStyleSheet("""
            #BottomBarWidget { 
                background: transparent; 
                border-top: 1px solid rgba(255, 255, 255, 10);
            }
        """)
        self.layout = QHBoxLayout(self.bar_widget)
        self.layout.setContentsMargins(15, 0, 15, 0)
        self.layout.setSpacing(15)
        self.main_container.addWidget(self.bar_widget)

        # 2. Bottom Status Label & Progress
        self.status_container = QWidget()
        self.status_container.setFixedHeight(20)
        self.status_layout = QHBoxLayout(self.status_container)
        self.status_layout.setContentsMargins(15, 0, 15, 0)
        self.status_layout.setSpacing(10)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 120); font-size: 10px; background: transparent;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: rgba(255, 255, 255, 10); border: none; border-radius: 1px; }
            QProgressBar::chunk { background-color: #bf5af2; border-radius: 1px; }
        """)
        self.progress_bar.hide()
        
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addWidget(self.progress_bar, 1) # Progress bar takes remaining space
        
        self.status_container.setObjectName("BottomStatusContainer")
        self.status_container.setStyleSheet("""
            #BottomStatusContainer {
                background: transparent;
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            }
        """)
        self.main_container.addWidget(self.status_container)

        # 1. Mask Tools Group (Iconified)
        self.tool_group = QButtonGroup(self)
        self.tool_layout = QHBoxLayout()
        self.tool_layout.setSpacing(5)
        
        tools = [
            ("pointer", "pointer", "Pointer Tool"),
            ("brush", "brush", "Brush Tool"),
            ("eraser", "eraser", "Eraser Tool")
        ]
        
        for i, (icon_name, name, tooltip) in enumerate(tools):
            btn = SvgIconButton(icon_name, tooltip)
            if name == "pointer":
                btn.setChecked(True)
            self.tool_group.addButton(btn, i)
            self.tool_layout.addWidget(btn)
            btn.clicked.connect(lambda checked, n=name: self.tool_changed.emit(n))
        
        self.layout.addLayout(self.tool_layout)

        # Separator
        line1 = QFrame()
        line1.setFrameShape(QFrame.VLine)
        line1.setFixedWidth(1)
        line1.setStyleSheet("background-color: rgba(255, 255, 255, 15); border: none;")
        self.layout.addWidget(line1)

        # 2. Brush Settings
        self.brush_layout = QHBoxLayout()
        self.brush_layout.setSpacing(8)
        
        self.shape_btn = SvgIconButton("shape", "Brush Shape")
        self.shape_btn.setCheckable(False)
        self.shape_btn.clicked.connect(self.show_shape_menu)
        self.brush_layout.addWidget(self.shape_btn)

        self.size_btn = SvgIconButton("size", "Brush Size")
        self.size_btn.setCheckable(False)
        self.size_btn.clicked.connect(self.show_size_menu)
        self.brush_layout.addWidget(self.size_btn)
        
        self.layout.addLayout(self.brush_layout)

        # 3. Action Buttons (Iconified)
        self.remove_bg_btn = SvgIconButton("sparkles", "Auto Remove Background")
        self.remove_bg_btn.setCheckable(False)
        self.remove_bg_btn.clicked.connect(self.show_model_menu)
        self.layout.addWidget(self.remove_bg_btn)

        self.erase_btn = SvgIconButton("broom", "Erase Watermark")
        self.erase_btn.setCheckable(True)
        self.erase_btn.clicked.connect(self.show_inpaint_menu)
        self.layout.addWidget(self.erase_btn)

        self.text_btn = SvgIconButton("text", "Add Text or Emoji")
        self.text_btn.setCheckable(False)
        self.text_btn.clicked.connect(self.show_text_menu)
        self.layout.addWidget(self.text_btn)

        self.sketch_btn = SvgIconButton("pencil", "Convert to Sketch Style")
        self.sketch_btn.setCheckable(False)
        self.sketch_btn.clicked.connect(self.show_sketch_menu)
        self.layout.addWidget(self.sketch_btn)

        self.reset_btn = SvgIconButton("reset", "Reset to Original Image")
        self.reset_btn.setCheckable(False)
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        self.layout.addWidget(self.reset_btn)

        self.palette_btn = SvgIconButton("palette", "Background Color")
        self.palette_btn.setCheckable(False)
        self.palette_btn.clicked.connect(self.show_bg_color_picker)
        self.layout.addWidget(self.palette_btn)

        self.layout.addStretch()

        # 4. Export Button (Compact)
        self.export_btn = SvgIconButton("export", "Export Result")
        self.export_btn.setCheckable(False)
        self.export_btn.clicked.connect(self.show_export_menu)
        self.layout.addWidget(self.export_btn)

    def show_message(self, message: str, timeout: int = 3000):
        self.status_label.setText(message)
        if timeout > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(timeout, lambda: self.status_label.setText("") if self.status_label.text() == message else None)

    def set_progress_active(self, active: bool):
        self.progress_bar.setVisible(active)

    def show_model_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        title = QLabel("选择抠图模型")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #fff;")
        layout.addWidget(title)
        
        models = ["isnet-general-use", "u2net", "birefnet-general"]
        for m in models:
            btn = QPushButton(m)
            btn.clicked.connect(lambda checked, name=m: [self.remove_bg_clicked.emit(name), popover.close()])
            layout.addWidget(btn)
            
        popover.set_widget(content)
        popover.show_above(self.remove_bg_btn)

    def clear_regular_tools(self) -> None:
        """Uncheck all background/pointer tools without emitting signals."""
        self.tool_group.setExclusive(False)
        for btn in self.tool_group.buttons():
            btn.setChecked(False)
        self.tool_group.setExclusive(True)

    def show_inpaint_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        
        # Sync the erase_btn checked state when popover is closed
        original_close_event = popover.closeEvent
        def on_popover_close(event):
            main_win = self.window()
            if hasattr(main_win, "canvas"):
                self.erase_btn.setChecked(main_win.canvas.current_mode == "wm")
            original_close_event(event)
        popover.closeEvent = on_popover_close
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        title = QLabel("水印绘制与去除")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #fff;")
        layout.addWidget(title)
        
        # Tool buttons row
        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)
        
        wm_brush = SvgIconButton("wm_brush", "Watermark Brush (绘制遮罩)", content)
        wm_brush.setCheckable(True)
        
        wm_eraser = SvgIconButton("wm_eraser", "Watermark Eraser (擦除遮罩)", content)
        wm_eraser.setCheckable(True)
        
        main_win = self.window()
        if hasattr(main_win, "canvas"):
            wm_brush.setChecked(main_win.canvas.current_mode == "wm" and main_win.canvas.current_tool == "brush")
            wm_eraser.setChecked(main_win.canvas.current_mode == "wm" and main_win.canvas.current_tool == "eraser")
        
        wm_group = QButtonGroup(content)
        wm_group.addButton(wm_brush)
        wm_group.addButton(wm_eraser)
        
        wm_brush.clicked.connect(lambda: [self.wm_tool_changed.emit("brush"), popover.close()])
        wm_eraser.clicked.connect(lambda: [self.wm_tool_changed.emit("eraser"), popover.close()])
        
        tool_row.addWidget(wm_brush)
        tool_row.addWidget(wm_eraser)
        tool_row.addStretch()
        
        layout.addLayout(tool_row)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 15); border: none; min-height: 1px; max-height: 1px;")
        layout.addWidget(line)
        
        strength_title = QLabel("传统算法去除 (渐进修复)")
        strength_title.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 150);")
        layout.addWidget(strength_title)
        
        strength_row = QHBoxLayout()
        strength_row.setSpacing(6)
        
        strengths = [("Light", "light"), ("Medium", "medium"), ("Strong", "strong")]
        for label, val in strengths:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, v=val: [self.erase_watermark_clicked.emit(v), popover.close()])
            strength_row.addWidget(btn)
            
        layout.addLayout(strength_row)
        
        # AI option section
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("background-color: rgba(255, 255, 255, 15); border: none; min-height: 1px; max-height: 1px;")
        layout.addWidget(line2)
        
        ai_title = QLabel("AI 智能去水印 (首次需下载模型)")
        ai_title.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 150);")
        layout.addWidget(ai_title)
        
        ai_row = QHBoxLayout()
        ai_btn = QPushButton("AI 智能擦除")
        ai_btn.setStyleSheet("background: #007aff; color: white; font-weight: bold; padding: 4px 12px;")
        ai_btn.clicked.connect(lambda checked: [self.erase_watermark_clicked.emit("ai"), popover.close()])
        ai_row.addWidget(ai_btn)
        layout.addLayout(ai_row)
        
        popover.set_widget(content)
        popover.show_above(self.erase_btn)

    def show_export_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        title = QLabel("导出格式")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #fff;")
        layout.addWidget(title)
        
        exports = [
            ("macOS Icon (.icns)", ".icns"),
            ("PNG Image Set", "PNG")
        ]
        for label, val in exports:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, v=val: [self.export_clicked.emit(v), popover.close()])
            layout.addWidget(btn)
            
        popover.set_widget(content)
        popover.show_above(self.export_btn)

    def show_shape_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setSpacing(5)
        for s in ["Circle", "Square", "Ellipse"]:
            btn = QPushButton(s)
            btn.clicked.connect(lambda checked, shape=s: [self.brush_shape_changed.emit(shape), popover.close()])
            layout.addWidget(btn)
        popover.set_widget(content)
        popover.show_above(self.shape_btn)

    def show_size_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        content = QWidget()
        content.setFixedWidth(150)
        layout = QVBoxLayout(content)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(1, 100)
        slider.setValue(20) # Default
        slider.valueChanged.connect(self.brush_size_changed.emit)
        layout.addWidget(QLabel("Brush Size"))
        layout.addWidget(slider)
        popover.set_widget(content)
        popover.show_above(self.size_btn)

    def show_text_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        content = TextSettingsWidget()
        content.accepted.connect(lambda text, params: [self.text_added.emit(text, params), popover.close()])
        content.rejected.connect(popover.close)
        popover.set_widget(content)
        popover.show_above(self.text_btn)

    def show_bg_color_picker(self):
        initial_color = self.current_bg_color
        if initial_color.alpha() == 0:
            initial_color = QColor(255, 255, 255, 255)
        color = QColorDialog.getColor(
            initial_color,
            self,
            "选择背景颜色",
            QColorDialog.ShowAlphaChannel
        )
        if color.isValid():
            self.bg_color_changed.emit(color)

    def show_sketch_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        title = QLabel("素描风格转换")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #fff;")
        layout.addWidget(title)
        
        options = [
            ("Fine Detail (精细)", 9),
            ("Classic Sketch (经典)", 21),
            ("Bold Sketch (浓重)", 51),
            ("Restore Original (恢复原图)", 0)
        ]
        
        for name, kernel_size in options:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, k_size=kernel_size: [self.sketch_clicked.emit(k_size), popover.close()])
            layout.addWidget(btn)
            
        popover.set_widget(content)
        popover.show_above(self.sketch_btn)
