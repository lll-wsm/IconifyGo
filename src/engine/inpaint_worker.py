import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal


class InpaintWorker(QThread):
    """QThread-based worker for watermark removal via multi-pass inpainting.

    Takes an image and a watermark mask, then performs iterative inpainting
    with adaptive radius to achieve clean watermark removal.

    Signals:
        finished(np.ndarray): Emitted with the inpainted image on success.
        error(str): Emitted with an error message on failure.
    """

    finished = Signal(np.ndarray)
    error = Signal(str)

    # Strength-to-factor mapping for adaptive radius calculation
    STRENGTH_FACTORS = {
        "light": 0.08,
        "medium": 0.15,
        "strong": 0.25,
    }

    def __init__(self, image: np.ndarray, watermark_mask: np.ndarray, strength: str = "medium"):
        super().__init__()
        self.image = image
        self.watermark_mask = watermark_mask
        self.strength = strength if strength in self.STRENGTH_FACTORS else "medium"

    def run(self):
        try:
            if self.image is None:
                raise ValueError("No image provided to InpaintWorker")
            if self.watermark_mask is None:
                raise ValueError("No watermark mask provided to InpaintWorker")

            result = self._perform_inpaint(self.image, self.watermark_mask, self.strength)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    @classmethod
    def _perform_inpaint(cls, image: np.ndarray, watermark_mask: np.ndarray, strength: str) -> np.ndarray:
        """Core inpainting logic — usable both from the worker thread and synchronously.

        Args:
            image: Input image (BGR or BGRA, np.uint8).
            watermark_mask: Binary mask where non-zero pixels mark watermark regions.
            strength: One of 'light', 'medium', 'strong'.

        Returns:
            The inpainted image with the same number of channels as the input.
        """
        # Determine if the image has an alpha channel
        has_alpha = len(image.shape) > 2 and image.shape[2] == 4
        if has_alpha:
            bgr = image[:, :, :3].copy()
            alpha_channel = image[:, :, 3].copy()
        else:
            bgr = image.copy()
            alpha_channel = None

        # --- Mask pre-processing ---
        # Dilate the watermark mask to ensure full watermark coverage
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.dilate(watermark_mask, dilate_kernel, iterations=2)

        # --- Adaptive radius calculation ---
        mask_area = int(np.count_nonzero(mask))
        if mask_area == 0:
            # Nothing to inpaint
            return image.copy()

        factor = cls.STRENGTH_FACTORS.get(strength, 0.15)
        radius = max(10, int(np.sqrt(mask_area) * factor))

        # --- Multi-pass iterative inpainting ---
        # Pass 1: Large radius with INPAINT_TELEA for structural reconstruction
        result = cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)

        # Pass 2: Medium radius with INPAINT_NS for color/texture smoothness
        medium_radius = max(3, radius // 2)
        result = cv2.inpaint(result, mask, medium_radius, cv2.INPAINT_NS)

        # Pass 3: Small radius with INPAINT_TELEA for fine detail refinement
        small_radius = max(3, radius // 4)
        result = cv2.inpaint(result, mask, small_radius, cv2.INPAINT_TELEA)

        # --- Reassemble with original alpha if applicable ---
        if has_alpha:
            output = np.dstack((result, alpha_channel))
        else:
            output = result

        return output
