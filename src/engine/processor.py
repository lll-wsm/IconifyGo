import cv2
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage, QPixmap
from typing import Optional
from .folder_styles import FolderStyleEngine

class ImageProcessor:
    def __init__(self):
        self.current_image: Optional[np.ndarray] = None
        self.original_image: Optional[np.ndarray] = None
        self.pre_sketch_image: Optional[np.ndarray] = None
        self.mask: Optional[np.ndarray] = None
        self.watermark_mask: Optional[np.ndarray] = None
        self.original_path: Optional[str] = None
        
        # Style settings
        self.mode = "icon"  # "icon" or "folder"
        self.folder_color = "#5ac8fa"
        self.folder_opacity = 0.9
        self.folder_scale = 0.675
        self.folder_engine = FolderStyleEngine()

    def load_image(self, file_path: str) -> bool:
        """Loads an image from a file path using OpenCV."""
        try:
            image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                raise ValueError(f"Could not load image at {file_path}")
            
            self.original_image = image.copy()
            self.set_image(image)
            self.original_path = file_path
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False

    def reset_to_original(self) -> bool:
        """Resets the processor state back to the original imported image."""
        if self.original_image is not None:
            self.set_image(self.original_image.copy())
            return True
        elif self.original_path is not None:
            return self.load_image(self.original_path)
        return False

    def set_image(self, image: np.ndarray) -> None:
        """Sets the current working image and initializes the mask."""
        if image.dtype == np.uint16:
            image = (image >> 8).astype(np.uint8)
        elif image.dtype != np.uint8:
            image = cv2.convertScaleAbs(image)

        self.current_image = image
        self.pre_sketch_image = None
        if len(image.shape) > 2 and image.shape[2] == 4:
            self.mask = image[:, :, 3].copy()
        else:
            self.mask = np.full(image.shape[:2], 255, dtype=np.uint8)
        
        # Initialize watermark mask
        self.watermark_mask = np.zeros(image.shape[:2], dtype=np.uint8)

    def apply_bg_removed_mask(self, result_image: np.ndarray) -> None:
        """Applies the background removal result mask without overwriting the current BGR image colors.
        This enables the brush tool to restore the original background colors when painting.
        """
        if len(result_image.shape) > 2 and result_image.shape[2] == 4:
            self.mask = result_image[:, :, 3].copy()
        else:
            self.mask = np.full(result_image.shape[:2], 255, dtype=np.uint8)

    def get_rgba_image(self, show_watermark: bool = False) -> Optional[np.ndarray]:
        """Combines the current image with the mask to return an RGBA image.
        If show_watermark is True, overlays the watermark mask with orange.
        """
        if self.current_image is None or self.mask is None:
            return None
        
        # Ensure base is BGR
        if len(self.current_image.shape) == 2: # Grayscale
            bgr = cv2.cvtColor(self.current_image, cv2.COLOR_GRAY2BGR)
        elif self.current_image.shape[2] == 4:
            bgr = self.current_image[:, :, :3]
        else:
            bgr = self.current_image

        rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = self.mask

        # Overlay watermark mask for visual feedback
        if show_watermark and self.watermark_mask is not None:
            # Create an orange overlay (B=0, G=102, R=255)
            orange = np.array([0, 102, 255, 255], dtype=np.uint8)
            wm_indices = self.watermark_mask > 0
            
            # Blend the orange overlay with the existing image (50% opacity)
            # We only blend color channels, keeping the original alpha or full opacity for the mark
            alpha = 0.5
            rgba[wm_indices, :3] = (rgba[wm_indices, :3] * (1 - alpha) + orange[:3] * alpha).astype(np.uint8)
            # Ensure the marking itself is visible even if the underlying image is transparent
            # (Optional: set alpha to at least 128 where watermark is present)
            rgba[wm_indices, 3] = np.maximum(rgba[wm_indices, 3], 128)

        return rgba

    def draw_on_mask(self, points: np.ndarray, value: int) -> None:
        """Draws a filled polygon on the mask."""
        if self.mask is not None:
            cv2.fillPoly(self.mask, [points], value)

    def brush_on_mask(self, start: tuple, end: tuple, radius: int, value: int, shape: str = "Circle") -> None:
        """Draws a line (brush stroke) on the mask with the specified shape."""
        if self.mask is None:
            return
        self._draw_brush(self.mask, start, end, radius, value, shape)

    def brush_on_watermark_mask(self, start: tuple, end: tuple, radius: int, value: int, shape: str = "Circle") -> None:
        """Draws a line (brush stroke) on the watermark mask with the specified shape."""
        if self.watermark_mask is None:
            return
        self._draw_brush(self.watermark_mask, start, end, radius, value, shape)

    def _draw_brush(self, target_mask: np.ndarray, start: tuple, end: tuple, radius: int, value: int, shape: str = "Circle") -> None:
        """Internal helper to draw brush strokes on a mask."""
        if shape == "Circle":
            cv2.line(target_mask, start, end, value, radius * 2)
            cv2.circle(target_mask, start, radius, value, -1)
            cv2.circle(target_mask, end, radius, value, -1)
        elif shape == "Square":
            cv2.line(target_mask, start, end, value, radius * 2)
            cv2.rectangle(target_mask, (start[0]-radius, start[1]-radius), 
                           (start[0]+radius, start[1]+radius), value, -1)
            cv2.rectangle(target_mask, (end[0]-radius, end[1]-radius), 
                           (end[0]+radius, end[1]+radius), value, -1)
        elif shape == "Ellipse":
            cv2.line(target_mask, start, end, value, radius * 2)
            cv2.ellipse(target_mask, start, (radius, radius // 2), 0, 0, 360, value, -1)
            cv2.ellipse(target_mask, end, (radius, radius // 2), 0, 0, 360, value, -1)

    def execute_inpaint(self, strength: str = "medium") -> None:
        """Applies progressive peeling (onion-skin) inpainting to the current image using the watermark mask.

        Uses mask dilation for full watermark coverage, a progressive erosion loop,
        and a seamless feathering blend to remove watermark and prevent blur/wave artifacts.

        Args:
            strength: Inpainting strength — 'light', 'medium', or 'strong'.
        """
        if self.current_image is None or self.watermark_mask is None:
            return
        if np.count_nonzero(self.watermark_mask) == 0:
            return

        from .inpaint_worker import InpaintWorker
        self.current_image = InpaintWorker._perform_inpaint(
            self.current_image, self.watermark_mask, strength
        )

        # Clear watermark mask after execution
        self.watermark_mask.fill(0)

    def get_inpaint_params(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Returns copies of the current image and watermark mask for async InpaintWorker use.

        Returns:
            A tuple of (image_copy, watermark_mask_copy), or None if either is unavailable
            or the mask is empty.
        """
        if self.current_image is None or self.watermark_mask is None:
            return None
        if np.count_nonzero(self.watermark_mask) == 0:
            return None
        return (self.current_image.copy(), self.watermark_mask.copy())

    def apply_inpaint_result(self, result_image: np.ndarray) -> None:
        """Applies the result from an async InpaintWorker back to the processor state.

        Args:
            result_image: The inpainted image returned by InpaintWorker.
        """
        self.current_image = result_image
        self.pre_sketch_image = None
        if self.watermark_mask is not None:
            self.watermark_mask.fill(0)

    def apply_sketch_filter(self, kernel_size: int = 21) -> None:
        """Converts the active current_image (subject) into a pencil sketch style.
        The background mask is preserved.
        """
        if self.current_image is None:
            return

        # Backup the pre-sketch image if not already backed up
        if self.pre_sketch_image is None:
            self.pre_sketch_image = self.current_image.copy()

        # Always work on the pre-sketch image to avoid cumulative filter degradation
        base_img = self.pre_sketch_image

        # Ensure base image is BGR
        if len(base_img.shape) == 2:  # Grayscale
            bgr = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGR)
        elif base_img.shape[2] == 4:
            bgr = base_img[:, :, :3]
        else:
            bgr = base_img

        # 1. Convert to grayscale
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # 2. Invert the grayscale image
        gray_inv = 255 - gray

        # 3. Apply Gaussian Blur to the inverted image
        # Kernel size must be odd and positive (e.g. 9, 21, 51)
        blur = cv2.GaussianBlur(gray_inv, (kernel_size, kernel_size), 0)

        # 4. Blend using color dodge
        sketch = cv2.divide(gray, 255 - blur, scale=256)

        # Convert back to 3-channel BGR
        sketch_bgr = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        # If current_image was 4-channel RGBA/BGRA, preserve the alpha channel
        if len(self.current_image.shape) == 2:
            self.current_image = sketch.copy()
        elif self.current_image.shape[2] == 4:
            self.current_image = self.pre_sketch_image.copy()
            self.current_image[:, :, :3] = sketch_bgr
        else:
            self.current_image = sketch_bgr.copy()

    def restore_pre_sketch(self) -> bool:
        """Restores the image to the state before the sketch filter was applied."""
        if self.pre_sketch_image is not None:
            self.current_image = self.pre_sketch_image.copy()
            self.pre_sketch_image = None
            return True
        return False

    def apply_current_style(self) -> None:
        """Applies the current mode's style (e.g., folder background) to the image."""
        if self.current_image is None or self.mode != "folder":
            return

        logo_rgba = self.get_rgba_image()
        if logo_rgba is not None:
            styled_image = self.folder_engine.apply_folder_style(
                logo_rgba, 
                color=self.folder_color,
                opacity=self.folder_opacity,
                scale=self.folder_scale
            )
            self.set_image(styled_image)

    def get_qimage(self, show_watermark: bool = True) -> Optional[QImage]:
        """Converts the current RGBA image to a PySide6 QImage."""
        rgba_image = self.get_rgba_image(show_watermark=show_watermark)
        if rgba_image is None:
            return None

        height, width = rgba_image.shape[:2]
        rgb_image = cv2.cvtColor(rgba_image, cv2.COLOR_BGRA2RGBA)
        
        bytes_per_line = 4 * width
        return QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format_RGBA8888).copy()

    def get_qpixmap(self, show_watermark: bool = True) -> Optional[QPixmap]:
        """Converts the current image to a QPixmap."""
        qimage = self.get_qimage(show_watermark=show_watermark)
        if qimage:
            return QPixmap.fromImage(qimage)
        return None

    def get_pil_image(self, show_watermark: bool = False) -> Optional[Image.Image]:
        """Converts the current RGBA image to a PIL Image."""
        rgba_image = self.get_rgba_image(show_watermark=show_watermark)
        if rgba_image is None:
            return None
        rgba_rgb = cv2.cvtColor(rgba_image, cv2.COLOR_BGRA2RGBA)
        return Image.fromarray(rgba_rgb)

    def add_text_overlay(self, text: str, font_name: str = "Arial", font_size: int = 40, 
                         color: tuple = (255, 255, 255), weight: str = "Regular",
                         alignment: str = "center") -> None:
        """Renders text onto the current image using PIL."""
        from PIL import ImageDraw, ImageFont, Image

        is_new_canvas = False
        if self.current_image is None:
            is_new_canvas = True
            size = 512
            self.current_image = np.zeros((size, size, 4), dtype=np.uint8)
            self.mask = np.zeros((size, size), dtype=np.uint8)
            self.watermark_mask = np.zeros((size, size), dtype=np.uint8)
            self.original_image = self.current_image.copy()

        # Target dimensions
        w, h = self.current_image.shape[1], self.current_image.shape[0]
        
        # Calculate target box size based on font_size parameter as scale
        # font_size default is 40. scale_factor = font_size / 80
        # target_box_size = min(w, h) * scale_factor
        scale_factor = font_size / 80.0
        target_box_size = max(10.0, min(w, h) * scale_factor)

        # Detect if we should use Emoji font
        is_emoji_text = any(
            0x1F300 <= ord(c) <= 0x1F9FF or
            0x2600 <= ord(c) <= 0x27BF or
            0x1F000 <= ord(c) <= 0x1F6FF
            for c in text
        )

        # --- Font loading with glyph validation ---
        base_render_size = 200

        def _font_can_render(font_obj, text_to_check):
            """Check if the font can render all non-ASCII chars by comparing
            each character's bbox against the .notdef glyph bbox."""
            try:
                notdef_bbox = font_obj.getbbox("\uFFFE")
            except Exception:
                return True  # If we can't detect, assume OK
            for c in text_to_check:
                if ord(c) <= 127 or c.isspace():
                    continue
                try:
                    char_bbox = font_obj.getbbox(c)
                    if char_bbox is None:
                        return False
                    if notdef_bbox is not None and char_bbox == notdef_bbox:
                        return False
                except Exception:
                    return False
            return True

        def _try_load_font(path, size):
            """Try loading a font file, return font object or None."""
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                return None

        font = None
        
        # If emoji, try Apple Color Emoji first (fixed pre-rendered bitmap size)
        if is_emoji_text:
            font = _try_load_font("/System/Library/Fonts/Apple Color Emoji.ttc", 160)

        # Try the user-requested font name
        if font is None:
            font_file_base = font_name.replace(" ", "")
            attempts = []
            if weight == "Bold":
                attempts.append(f"{font_file_base}-Bold.ttf")
                attempts.append(f"{font_file_base}Bold.ttf")
            elif weight == "Italic":
                attempts.append(f"{font_file_base}-Italic.ttf")
            attempts.extend([
                f"{font_file_base}.ttf", f"{font_file_base}.ttc",
                f"{font_name}.ttf", f"{font_name}.ttc",
            ])
            
            # Search in system font directories
            search_dirs = [
                "",  # bare name (PIL resolves via fontconfig)
                "/System/Library/Fonts/",
                "/System/Library/Fonts/Supplemental/",
                "/Library/Fonts/",
            ]
            for attempt in attempts:
                for d in search_dirs:
                    candidate = _try_load_font(d + attempt, base_render_size)
                    if candidate is not None and _font_can_render(candidate, text):
                        font = candidate
                        break
                if font is not None:
                    break

        # Broad-coverage Unicode fallback fonts (ordered by coverage breadth)
        if font is None:
            unicode_fallbacks = [
                "/Library/Fonts/Arial Unicode.ttf",
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Supplemental/Songti.ttc",
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            for fb in unicode_fallbacks:
                candidate = _try_load_font(fb, base_render_size)
                if candidate is not None and _font_can_render(candidate, text):
                    font = candidate
                    break
            # If no font passes validation, use the first one that loads
            if font is None:
                for fb in unicode_fallbacks:
                    candidate = _try_load_font(fb, base_render_size)
                    if candidate is not None:
                        font = candidate
                        break

        if font is None:
            font = ImageFont.load_default()

        # Render onto a temporary high-resolution transparent canvas
        temp_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Draw centered on temp canvas initially
        try:
            bbox = temp_draw.textbbox((0, 0), text, font=font, align=alignment)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = temp_draw.textsize(text, font=font)
            bbox = (0, 0, tw, th)

        tx = (w - tw) // 2 - bbox[0]
        ty = (h - th) // 2 - bbox[1]
        
        temp_draw.text((tx, ty), text, font=font, fill=color, align=alignment, embedded_color=True)

        # Get exact bounding box of the rendered text/emoji
        bbox_actual = temp_img.getbbox()
        if bbox_actual is None:
            # Nothing was rendered, use a default fallback
            bbox_actual = (w // 4, h // 4, 3 * w // 4, 3 * h // 4)

        # Crop and resize
        text_w = bbox_actual[2] - bbox_actual[0]
        text_h = bbox_actual[3] - bbox_actual[1]
        
        text_crop = temp_img.crop(bbox_actual)
        
        # Scale to match target box size (1/2 canvas at default scale)
        max_dim = max(text_w, text_h, 1)
        scale = target_box_size / max_dim
        new_tw = int(text_w * scale)
        new_th = int(text_h * scale)
        new_tw = max(1, new_tw)
        new_th = max(1, new_th)
        
        text_resized = text_crop.resize((new_tw, new_th), Image.Resampling.LANCZOS)

        # Create final canvas
        if self.current_image is not None and not is_new_canvas:
            final_img = self.get_pil_image()
        else:
            final_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        
        # Paste centered
        px = (w - new_tw) // 2
        py = (h - new_th) // 2
        
        # Paste with alpha transparency
        final_img.paste(text_resized, (px, py), text_resized)

        # Convert back to NumPy BGRA/BGR
        new_img = np.array(final_img)
        self.pre_sketch_image = None
        if new_img.shape[2] == 4:
            self.current_image = cv2.cvtColor(new_img, cv2.COLOR_RGBA2BGRA)
            self.mask = self.current_image[:, :, 3].copy()
        else:
            self.current_image = cv2.cvtColor(new_img, cv2.COLOR_RGB2BGR)
