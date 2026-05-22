import cv2
import numpy as np
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QFontMetricsF
from PySide6.QtCore import Qt, QRectF

def serialize_text_item(item) -> dict:
    """Serializes an InteractiveTextItem into a plain dictionary of state."""
    return {
        "text": item.text,
        "font_name": item.font_name,
        "font_size": item.font_size,
        "color": (item.color.red(), item.color.green(), item.color.blue(), item.color.alpha()),
        "weight": item.weight,
        "alignment": item.alignment,
        "pos": (item.pos().x(), item.pos().y()),
        "scale": item.scale()
    }

def draw_text_on_np(styled_np: np.ndarray, text_items_data: list, canvas_ref_size: tuple) -> np.ndarray:
    """
    Draws text items on top of a styled numpy array (BGRA).
    styled_np: numpy array of shape (H, W, 4) in BGRA format.
    text_items_data: list of dictionaries, each describing a text item.
    canvas_ref_size: (w_ref, h_ref) of the nominal canvas scene.
    """
    if not text_items_data:
        return styled_np

    h_target, w_target = styled_np.shape[:2]
    w_ref, h_ref = canvas_ref_size
    
    scale_ratio = float(w_target) / float(w_ref) if w_ref > 0 else 1.0
    
    # Convert BGRA to RGBA for QImage to match memory layout of QImage.Format_RGBA8888
    rgba = cv2.cvtColor(styled_np, cv2.COLOR_BGRA2RGBA)
    qimg = QImage(rgba.data, w_target, h_target, 4 * w_target, QImage.Format_RGBA8888).copy()
    
    painter = QPainter(qimg)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    
    for item in text_items_data:
        text = item["text"]
        if not text.strip():
            continue
            
        font_name = item["font_name"]
        font_size = item["font_size"]
        color_tuple = item["color"]  # (r, g, b, a)
        weight = item["weight"]
        alignment = item["alignment"]
        pos = item["pos"]  # (x, y) scene coordinate relative to center
        scale = item["scale"]
        
        painter.save()
        
        # Calculate target position relative to the center of target image
        tx = pos[0] * scale_ratio + w_target / 2.0
        ty = pos[1] * scale_ratio + h_target / 2.0
        
        painter.translate(tx, ty)
        
        # Calculate overall font scale
        s = scale * scale_ratio
        painter.scale(s, s)
        
        # Create font
        font = QFont(font_name)
        font.setPointSize(font_size)
        if weight == "Bold":
            font.setBold(True)
        elif weight == "Italic":
            font.setItalic(True)
            
        painter.setFont(font)
        painter.setPen(QColor(color_tuple[0], color_tuple[1], color_tuple[2], color_tuple[3]))
        
        # Get alignment flags
        align_flag = Qt.AlignVCenter
        if alignment == "left":
            align_flag |= Qt.AlignLeft
        elif alignment == "right":
            align_flag |= Qt.AlignRight
        else:
            align_flag |= Qt.AlignHCenter
            
        # Compute bounding rect using QFontMetricsF to match exactly
        fm = QFontMetricsF(font)
        orig_rect = fm.boundingRect(
            QRectF(0, 0, 10000, 10000),
            align_flag | Qt.TextDontClip,
            text
        )
        orig_rect = QRectF(0, 0, orig_rect.width(), orig_rect.height())
        
        painter.drawText(orig_rect, align_flag | Qt.TextDontClip, text)
        
        painter.restore()
        
    painter.end()
    
    # Convert QImage back to RGBA numpy
    arr_rgba = np.frombuffer(qimg.constBits(), dtype=np.uint8).reshape((h_target, w_target, 4)).copy()
    # Convert RGBA to BGRA numpy
    return cv2.cvtColor(arr_rgba, cv2.COLOR_RGBA2BGRA)
