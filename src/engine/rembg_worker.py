import cv2
import numpy as np
import rembg
import os
from PySide6.QtCore import QThread, Signal

class RembgWorker(QThread):
    finished = Signal(np.ndarray)
    error = Signal(str)

    def __init__(self, image: np.ndarray, model_name: str = "isnet-general-use",
                 post_process: bool = True):
        super().__init__()
        self.image = image
        self.model_name = model_name
        self.post_process = post_process
        # Path to the config directory for rembg models (outside project to keep repo small)
        self.res_dir = os.path.join(os.path.expanduser("~"), ".config", "IconifyGo")

    def _fill_holes(self, alpha: np.ndarray) -> np.ndarray:
        """Fill small holes inside the foreground region of the alpha mask.
        
        Holes smaller than 1% of the total image area are filled to prevent
        internal transparent regions that should be part of the foreground.
        """
        total_area = alpha.shape[0] * alpha.shape[1]
        threshold = total_area * 0.01  # 1% of total image area

        # Binarize the alpha mask
        _, binary = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)

        # Invert: holes become white regions
        inverted = cv2.bitwise_not(binary)

        # Find contours of the holes
        contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Create a mask of small holes to fill
        fill_mask = np.zeros_like(alpha)
        for contour in contours:
            area = cv2.contourArea(contour)
            if 0 < area < threshold:
                cv2.drawContours(fill_mask, [contour], -1, 255, -1)

        # Fill the small holes in the original alpha
        result = alpha.copy()
        result[fill_mask > 0] = 255
        return result

    def _post_process_alpha(self, alpha: np.ndarray) -> np.ndarray:
        """Apply post-processing pipeline to refine the alpha mask.
        
        Steps:
        1. Fill small holes inside the foreground
        2. Morphological close to smooth edges and close small gaps
        3. Slight Gaussian blur for edge anti-aliasing
        4. Re-threshold to keep mask clean
        """
        # Step 1: Fill holes
        alpha = self._fill_holes(alpha)

        # Step 2: Morphological close (fills small gaps, smooths edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)

        # Step 3: Slight Gaussian blur for edge smoothing
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)

        # Step 4: Re-threshold to clean up
        _, alpha = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)

        return alpha

    def run(self):
        try:
            # Ensure we have a valid image
            if self.image is None:
                raise ValueError("No image provided to RembgWorker")

            # Tell rembg where to look for models
            os.environ["U2NET_HOME"] = self.res_dir

            # Create a session with the selected model
            session = rembg.new_session(model_name=self.model_name)

            # Convert to RGB/RGBA for rembg (which expects RGB-based input)
            channels = self.image.shape[2] if len(self.image.shape) > 2 else 1
            
            if channels == 3:
                # BGR -> RGB
                img_to_proc = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
            elif channels == 4:
                # BGRA -> RGBA
                img_to_proc = cv2.cvtColor(self.image, cv2.COLOR_BGRA2RGBA)
            else:
                # Grayscale or other
                img_to_proc = self.image

            # Remove background
            # rembg.remove returns RGBA numpy array if input is numpy array
            result_rgba = rembg.remove(
                img_to_proc,
                session=session,
                post_process_mask=True,
            )

            # Ensure result is writable (rembg may return read-only arrays)
            result_rgba = np.array(result_rgba, copy=True)

            # Apply alpha mask post-processing for higher accuracy
            if self.post_process:
                alpha = result_rgba[:, :, 3]
                alpha = self._post_process_alpha(alpha)
                result_rgba[:, :, 3] = alpha

            # Convert back to BGRA for ImageProcessor (OpenCV consistency)
            result_bgra = cv2.cvtColor(result_rgba, cv2.COLOR_RGBA2BGRA)

            self.finished.emit(result_bgra)
        except Exception as e:
            self.error.emit(str(e))
