import cv2
import numpy as np
import os
import time
import threading
import urllib.request
from urllib.error import HTTPError
from src.utils.i18n import tr
from PySide6.QtCore import QThread, Signal
import onnxruntime as ort


class InpaintWorker(QThread):
    """QThread-based worker for watermark removal via progressive peeling inpainting or AI.

    Takes an image and a watermark mask, then performs progressive peeling (onion-skin)
    inpainting or LaMa AI-based inpainting with boundary feathering.

    Signals:
        finished(np.ndarray): Emitted with the inpainted image on success.
        error(str): Emitted with an error message on failure.
        progress(str): Emitted with text progress messages (e.g. "Loading AI model...").
        download_progress(int, int): Emitted with (downloaded_bytes, total_bytes) during model download.
        cancelled(): Emitted when the user cancels a model download.
    """

    finished = Signal(np.ndarray)
    error = Signal(str)
    progress = Signal(str)
    download_progress = Signal(int, int)
    cancelled = Signal()

    # Cached ONNX Runtime InferenceSession
    _session = None

    # Download mirrors for the LaMa ONNX model (HuggingFace + China mirror fallback)
    MIRRORS = [
        "https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx",
        "https://hf-mirror.com/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx",
    ]

    # Dynamic configurations for progressive peeling based on strength
    CONFIGS = {
        "light": {
            "dilate_kernel_size": 3,
            "dilate_iterations": 1,
            "step_size": 2,
            "inpaint_radius": 2,
            "feather_kernel": 3,
        },
        "medium": {
            "dilate_kernel_size": 3,
            "dilate_iterations": 2,
            "step_size": 3,
            "inpaint_radius": 3,
            "feather_kernel": 3,
        },
        "strong": {
            "dilate_kernel_size": 5,
            "dilate_iterations": 2,
            "step_size": 4,
            "inpaint_radius": 4,
            "feather_kernel": 5,
        },
    }

    def __init__(self, image: np.ndarray, watermark_mask: np.ndarray, strength: str = "medium"):
        super().__init__()
        self.image = image
        self.watermark_mask = watermark_mask
        self.strength = strength if (strength in self.CONFIGS or strength == "ai") else "medium"
        self._cancel_event = threading.Event()

    def cancel_download(self):
        """Called from the UI thread to cancel an in-progress model download."""
        self._cancel_event.set()

    def run(self):
        try:
            if self.image is None:
                raise ValueError("No image provided to InpaintWorker")
            if self.watermark_mask is None:
                raise ValueError("No watermark mask provided to InpaintWorker")
            if self.isInterruptionRequested():
                return

            result = self._perform_inpaint(
                self.image, self.watermark_mask, self.strength, progress_cb=self.progress.emit
            )
            if not self.isInterruptionRequested() and not self._cancel_event.is_set():
                self.finished.emit(result)
        except Exception as e:
            if not self.isInterruptionRequested() and not self._cancel_event.is_set():
                self.error.emit(str(e))

    @classmethod
    def get_model_path(cls) -> str:
        """Resolves the local destination path for the LaMa ONNX model."""
        model_dir = os.path.expanduser("~/.config/IconifyGo")
        os.makedirs(model_dir, exist_ok=True)
        return os.path.join(model_dir, "lama_fp32.onnx")

    @classmethod
    def is_model_available(cls) -> bool:
        """Check if the LaMa model is already downloaded and non-trivial in size."""
        path = cls.get_model_path()
        return os.path.exists(path) and os.path.getsize(path) > 1_000_000

    def _download_model(self, save_path: str) -> bool:
        """Downloads the LaMa ONNX model with resume, retry, mirror fallback, and cancel support.

        Returns True on success, False if cancelled by the user.
        Raises RuntimeError if all mirrors and retries are exhausted.
        """
        tmp_path = save_path + ".part"
        block_size = 256 * 1024  # 256KB chunks for fine-grained cancel responsiveness

        for mirror_idx, url in enumerate(self.MIRRORS):
            max_retries = 3
            for attempt in range(max_retries):
                if self._cancel_event.is_set():
                    self.cancelled.emit()
                    return False

                try:
                    resume_pos = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    if resume_pos > 0:
                        headers['Range'] = f'bytes={resume_pos}-'

                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        status = resp.status
                        if status == 200:
                            # Server ignored Range header or fresh download
                            resume_pos = 0
                            mode = 'wb'
                        elif status == 206:
                            # Partial content - resume from where we left off
                            mode = 'ab'
                        else:
                            raise RuntimeError(f"Unexpected HTTP status: {status}")

                        content_length = int(resp.info().get('Content-Length', 0))
                        total = resume_pos + content_length

                        with open(tmp_path, mode) as f:
                            downloaded = resume_pos
                            while True:
                                if self._cancel_event.is_set():
                                    self.cancelled.emit()
                                    return False
                                chunk = resp.read(block_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    self.download_progress.emit(downloaded, total)

                    # Verify download completion
                    actual_size = os.path.getsize(tmp_path)
                    if total > 0 and actual_size >= total:
                        os.rename(tmp_path, save_path)
                        return True
                    elif total == 0 and actual_size > 0:
                        os.rename(tmp_path, save_path)
                        return True

                except HTTPError as e:
                    if self._cancel_event.is_set():
                        self.cancelled.emit()
                        return False
                    if e.code == 416 and os.path.exists(tmp_path):
                        # .part file is larger than remote - delete and retry from scratch
                        os.remove(tmp_path)
                        continue
                    # Other HTTP errors fall through to retry logic
                    if attempt < max_retries - 1:
                        wait_secs = 2 ** attempt
                        for _ in range(wait_secs * 10):
                            if self._cancel_event.is_set():
                                self.cancelled.emit()
                                return False
                            time.sleep(0.1)
                        continue
                    if mirror_idx < len(self.MIRRORS) - 1:
                        break
                    raise RuntimeError(f"Failed to download AI model from all mirrors: {e}")
                except Exception as e:
                    if self._cancel_event.is_set():
                        self.cancelled.emit()
                        return False
                    if attempt < max_retries - 1:
                        # Exponential backoff: 1s, 2s (interruptible sleep)
                        wait_secs = 2 ** attempt
                        for _ in range(wait_secs * 10):
                            if self._cancel_event.is_set():
                                self.cancelled.emit()
                                return False
                            time.sleep(0.1)
                        continue
                    # Last retry on this mirror failed — try next mirror
                    if mirror_idx < len(self.MIRRORS) - 1:
                        break
                    raise RuntimeError(f"Failed to download AI model from all mirrors: {e}")

        raise RuntimeError("Failed to download AI model: all mirrors exhausted")

    def _perform_inpaint(self, image: np.ndarray, watermark_mask: np.ndarray, strength: str, progress_cb=None) -> np.ndarray:
        """Core inpainting logic using progressive peeling or AI, and boundary feathering.

        Args:
            image: Input image (BGR or BGRA, np.uint8).
            watermark_mask: Binary mask where non-zero pixels mark watermark regions.
            strength: One of 'light', 'medium', 'strong', 'ai'.
            progress_cb: Optional callback for progress reporting.

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

        if strength == "ai":
            model_path = InpaintWorker.get_model_path()
            if not os.path.exists(model_path) or os.path.getsize(model_path) < 1_000_000:
                if progress_cb:
                    progress_cb(tr("Downloading AI model..."))
                success = self._download_model(model_path)
                if not success:
                    # Cancelled by user - return original image unchanged
                    return image.copy()

            if InpaintWorker._session is None:
                if progress_cb:
                    progress_cb(tr("Loading AI model into memory..."))
                # CoreML is preferred on macOS; falls back to CPU
                providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
                InpaintWorker._session = ort.InferenceSession(model_path, providers=providers)

            if progress_cb:
                progress_cb(tr("AI watermark removal in progress..."))

            output_bgr = InpaintWorker._run_lama_ai(bgr, watermark_mask, InpaintWorker._session)
        else:
            # --- Dynamic Configuration Retrieval ---
            cfg = InpaintWorker.CONFIGS.get(strength, InpaintWorker.CONFIGS["medium"])
            dilate_kernel_size = cfg["dilate_kernel_size"]
            dilate_iterations = cfg["dilate_iterations"]
            step_size = cfg["step_size"]
            inpaint_radius = cfg["inpaint_radius"]
            feather_kernel = cfg["feather_kernel"]

            # --- Mask pre-processing ---
            # Dilate the watermark mask to ensure full watermark coverage
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_kernel_size, dilate_kernel_size))
            mask = cv2.dilate(watermark_mask, dilate_kernel, iterations=dilate_iterations)

            if np.count_nonzero(mask) == 0:
                return image.copy()

            # Keep a copy of the initial dilated mask for feathering blend later
            initial_mask = mask.copy()

            # --- Progressive peeling (onion-skin) loop ---
            current_mask = mask.copy()
            result = bgr.copy()
            
            # Use a 3x3 structuring element for erosion steps
            erosion_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            
            max_iters = 200
            iters = 0
            while np.any(current_mask > 0) and iters < max_iters:
                # Inpaint current state using current_mask with a small radius.
                # This reconstructs the boundary layer using clean outer pixels.
                result = cv2.inpaint(result, current_mask, inpaint_radius, cv2.INPAINT_TELEA)
                
                # Erode current mask to move the boundary inward
                current_mask = cv2.erode(current_mask, erosion_kernel, iterations=step_size)
                iters += 1

            # --- Seamless Feathering Blend ---
            # Smooth the transition boundary to completely eliminate sharp edges / seams
            mask_float = initial_mask.astype(np.float32) / 255.0
            feathered_mask = cv2.GaussianBlur(mask_float, (feather_kernel, feather_kernel), 0)
            feathered_mask = np.expand_dims(feathered_mask, axis=2)
            
            output_bgr = (bgr.astype(np.float32) * (1.0 - feathered_mask) + result.astype(np.float32) * feathered_mask).astype(np.uint8)

        # --- Reassemble with original alpha if applicable ---
        if has_alpha:
            output = np.dstack((output_bgr, alpha_channel))
        else:
            output = output_bgr

        return output

    @classmethod
    def _run_lama_ai(cls, image: np.ndarray, mask: np.ndarray, session: ort.InferenceSession) -> np.ndarray:
        """Executes patch-based LaMa AI inpainting model inference."""
        h, w = image.shape[:2]
        
        # 1. Dilate mask slightly to cover edge transitions
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        dilated_mask = cv2.dilate(mask, dilate_kernel, iterations=2)
        
        # 2. Get bounding box of the mask to perform localized crop
        y_indices, x_indices = np.where(dilated_mask > 0)
        if len(y_indices) == 0:
            return image.copy()
            
        ymin, ymax = y_indices.min(), y_indices.max()
        xmin, xmax = x_indices.min(), x_indices.max()
        
        # Add 32px padding on all sides, clamped to image borders
        padding = 32
        ymin = max(0, ymin - padding)
        ymax = min(h, ymax + padding)
        xmin = max(0, xmin - padding)
        xmax = min(w, xmax + padding)
        
        # 3. Crop patch
        crop_img = image[ymin:ymax, xmin:xmax]
        crop_mask = dilated_mask[ymin:ymax, xmin:xmax]
        
        crop_h, crop_w = crop_img.shape[:2]
        
        # 4. Resize crop patch to 512x512
        crop_img_512 = cv2.resize(crop_img, (512, 512), interpolation=cv2.INTER_AREA)
        crop_mask_512 = cv2.resize(crop_mask, (512, 512), interpolation=cv2.INTER_NEAREST)
        _, crop_mask_512 = cv2.threshold(crop_mask_512, 127, 255, cv2.THRESH_BINARY)
        
        # 5. Preprocess for LaMa
        crop_img_512_rgb = cv2.cvtColor(crop_img_512, cv2.COLOR_BGR2RGB)
        img_tensor = crop_img_512_rgb.astype(np.float32) / 255.0
        mask_tensor = crop_mask_512.astype(np.float32) / 255.0
        
        img_tensor = np.transpose(img_tensor, (2, 0, 1))  # (3, 512, 512)
        img_tensor = np.expand_dims(img_tensor, axis=0)   # (1, 3, 512, 512)
        
        mask_tensor = np.expand_dims(mask_tensor, axis=0) # (512, 512)
        mask_tensor = np.expand_dims(mask_tensor, axis=0) # (1, 1, 512, 512)
        
        # 6. Run inference
        outputs = session.run(None, {'image': img_tensor, 'mask': mask_tensor})
        output_tensor = outputs[0][0]  # (3, 512, 512)
        
        # 7. Postprocess
        output_img = np.transpose(output_tensor, (1, 2, 0)) # (512, 512, 3)
        output_img = np.clip(output_img, 0, 255).astype(np.uint8)
        output_bgr = cv2.cvtColor(output_img, cv2.COLOR_RGB2BGR)
        
        # Resize back to cropped patch size
        result_crop = cv2.resize(output_bgr, (crop_w, crop_h), interpolation=cv2.INTER_CUBIC)
        
        # 8. Paste patch back into full image
        inpainted_full = image.copy()
        inpainted_full[ymin:ymax, xmin:xmax] = result_crop
        
        # 9. Blend with original image using a feathered mask for seamless boundary stitching
        mask_float = dilated_mask.astype(np.float32) / 255.0
        feathered_mask = cv2.GaussianBlur(mask_float, (5, 5), 0)
        feathered_mask = np.expand_dims(feathered_mask, axis=2)
        
        final_output = (image.astype(np.float32) * (1.0 - feathered_mask) + inpainted_full.astype(np.float32) * feathered_mask).astype(np.uint8)
        return final_output
