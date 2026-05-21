from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, 
    QComboBox, QFrame, QButtonGroup, QMenu, QPlainTextEdit, QColorDialog
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QColor, QAction, QFontDatabase, QFont
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
            bg_color = QColor(255, 255, 255, 30) if not self.isChecked() else QColor(0, 122, 255, 40)
            painter.setBrush(bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 6, 6)
            
        # Prepare SVG
        color = "#007aff" if self.isChecked() else "#eeeeee"
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        self.setFixedHeight(65)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 0, 15, 0)
        self.layout.setSpacing(15)

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
        line1.setFrameShadow(QFrame.Sunken)
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
        self.erase_btn.setCheckable(False)
        self.erase_btn.clicked.connect(self.show_inpaint_menu)
        self.layout.addWidget(self.erase_btn)

        self.text_btn = SvgIconButton("text", "Add Text or Emoji")
        self.text_btn.setCheckable(False)
        self.text_btn.clicked.connect(self.show_text_menu)
        self.layout.addWidget(self.text_btn)

        self.reset_btn = SvgIconButton("reset", "Reset to Original Image")
        self.reset_btn.setCheckable(False)
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        self.layout.addWidget(self.reset_btn)

        self.layout.addStretch()

        # 4. Export Button (Compact)
        self.export_btn = SvgIconButton("export", "Export Result")
        self.export_btn.setCheckable(False)
        self.export_btn.clicked.connect(self.show_export_menu)
        self.layout.addWidget(self.export_btn)

    def _create_styled_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2a2a2a; color: #eee; border: 1px solid #444; border-radius: 6px; padding: 5px; }
            QMenu::item { padding: 5px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #007aff; }
        """)
        return menu

    def show_model_menu(self):
        menu = self._create_styled_menu()
        models = ["isnet-general-use", "u2net", "birefnet-general"]
        for m in models:
            action = QAction(m, self)
            action.triggered.connect(lambda checked, name=m: self.remove_bg_clicked.emit(name))
            menu.addAction(action)
        
        pos = self.remove_bg_btn.mapToGlobal(self.remove_bg_btn.rect().topLeft())
        menu.exec(pos - QPoint(0, menu.sizeHint().height()))

    def show_inpaint_menu(self):
        menu = self._create_styled_menu()
        strengths = ["Light", "Medium", "Strong"]
        for s in strengths:
            action = QAction(s, self)
            action.triggered.connect(lambda checked, name=s.lower(): self.erase_watermark_clicked.emit(name))
            menu.addAction(action)
        
        pos = self.erase_btn.mapToGlobal(self.erase_btn.rect().topLeft())
        menu.exec(pos - QPoint(0, menu.sizeHint().height()))

    def show_export_menu(self):
        menu = self._create_styled_menu()
        
        icns_action = QAction("macOS Icon (.icns)", self)
        icns_action.triggered.connect(lambda: self.export_clicked.emit(".icns"))
        
        png_action = QAction("PNG Image Set", self)
        png_action.triggered.connect(lambda: self.export_clicked.emit("PNG"))
        
        menu.addAction(icns_action)
        menu.addAction(png_action)
        
        # Show menu above the button
        # Force a layout update to ensure sizeHint is accurate
        menu.adjustSize()
        pos = self.export_btn.mapToGlobal(self.export_btn.rect().topLeft())
        menu.exec(pos - QPoint(0, menu.sizeHint().height()))

    def show_shape_menu(self):
        from .popover import ActionPopover
        popover = ActionPopover(self)
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setSpacing(5)
        for s in ["Circle", "Square", "Ellipse"]:
            btn = QPushButton(s)
            btn.setStyleSheet("padding: 5px 10px; background: #333; color: #eee; border: 1px solid #444; border-radius: 4px;")
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
