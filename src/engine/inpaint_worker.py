import cv2
import numpy as np
import os
import urllib.request
from PySide6.QtCore import QThread, Signal, QStandardPaths
import onnxruntime as ort


class InpaintWorker(QThread):
    """QThread-based worker for watermark removal via progressive peeling inpainting or AI.

    Takes an image and a watermark mask, then performs progressive peeling (onion-skin)
    inpainting or LaMa AI-based inpainting with boundary feathering.

    Signals:
        finished(np.ndarray): Emitted with the inpainted image on success.
        error(str): Emitted with an error message on failure.
        progress(str): Emitted with progress messages (e.g. download progress).
    """

    finished = Signal(np.ndarray)
    error = Signal(str)
    progress = Signal(str)

    # Cached ONNX Runtime InferenceSession
    _session = None

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

    def run(self):
        try:
            if self.image is None:
                raise ValueError("No image provided to InpaintWorker")
            if self.watermark_mask is None:
                raise ValueError("No watermark mask provided to InpaintWorker")

            result = self._perform_inpaint(
                self.image, self.watermark_mask, self.strength, progress_cb=self.progress.emit
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    @classmethod
    def get_model_path(cls) -> str:
        """Resolves the local destination path for the LaMa ONNX model."""
        model_dir = os.path.expanduser("~/.config/IconifyGo")
        os.makedirs(model_dir, exist_ok=True)
        return os.path.join(model_dir, "lama_fp32.onnx")

    @classmethod
    def download_model(cls, save_path: str, progress_cb=None):
        """Downloads the LaMa ONNX model from Hugging Face with progress reporting."""
        url = "https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx"
        if progress_cb:
            progress_cb("Downloading AI model (0%)...")
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
                total_size = int(response.info().get('Content-Length', 0))
                block_size = 1024 * 1024  # 1MB chunks
                downloaded = 0
                
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if progress_cb:
                            progress_cb(f"Downloading AI model ({percent:.1f}%)...")
        except Exception as e:
            # Delete incomplete file to prevent corruption on next run
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            raise RuntimeError(f"Failed to download AI model: {e}")

    @classmethod
    def _perform_inpaint(cls, image: np.ndarray, watermark_mask: np.ndarray, strength: str, progress_cb=None) -> np.ndarray:
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
            model_path = cls.get_model_path()
            if not os.path.exists(model_path):
                cls.download_model(model_path, progress_cb)
                
            if cls._session is None:
                if progress_cb:
                    progress_cb("Loading AI model into memory...")
                # CoreML is preferred on macOS; falls back to CPU
                providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
                cls._session = ort.InferenceSession(model_path, providers=providers)
                
            if progress_cb:
                progress_cb("AI watermark removal in progress...")
                
            output_bgr = cls._run_lama_ai(bgr, watermark_mask, cls._session)
        else:
            # --- Dynamic Configuration Retrieval ---
            cfg = cls.CONFIGS.get(strength, cls.CONFIGS["medium"])
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
