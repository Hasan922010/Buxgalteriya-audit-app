import io
from typing import List
import cv2
import numpy as np
import pymupdf  # PyMuPDF
from PIL import Image

def deskew_image(gray: np.ndarray) -> np.ndarray:
    """Deskew an image using cv2.minAreaRect."""
    # Invert and threshold to find text contours
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle

    # If angle is negligible, do nothing
    if abs(angle) < 0.2 or abs(angle) > 45:
        return gray

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def enhance_cv2_image(img: np.ndarray) -> np.ndarray:
    """
    Applies the full degraded scan enhancement pipeline:
    1. Grayscale conversion
    2. Deskewing via minAreaRect
    3. Denoising via fastNlMeansDenoising
    4. CLAHE adaptive contrast (clipLimit=2.2)
    5. Unsharp Masking filter for faded numbers
    """
    # 1. Grayscale conversion
    if len(img.shape) == 3 and img.shape[2] == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif len(img.shape) == 3 and img.shape[2] == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    else:
        gray = img.copy()

    # 2. Deskewing
    deskewed = deskew_image(gray)

    # 3. Denoising
    denoised = cv2.fastNlMeansDenoising(deskewed, None, h=10, templateWindowSize=7, searchWindowSize=21)

    # 4. CLAHE Adaptive Contrast (clipLimit=2.2)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    contrast_enhanced = clahe.apply(denoised)

    # 5. Unsharp Masking filter for faded numbers
    blurred = cv2.GaussianBlur(contrast_enhanced, (0, 0), sigmaX=3.0)
    unsharp = cv2.addWeighted(contrast_enhanced, 1.5, blurred, -0.5, 0)

    return unsharp

def pdf_to_enhanced_images(pdf_bytes: bytes, dpi: int = 300) -> List[np.ndarray]:
    """
    Renders each page of a PDF document at target DPI and applies
    the enhancement pipeline. Returns a list of enhanced image arrays.
    """
    enhanced_images = []
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    # Calculate zoom matrix for requested DPI (72 default PDF DPI)
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)

    for page_idx in range(len(doc)):
        page = doc.load_page(page_idx)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
        # Convert RGB to BGR for OpenCV
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        enhanced = enhance_cv2_image(img_bgr)
        enhanced_images.append(enhanced)

    doc.close()
    return enhanced_images

def cv2_to_png_bytes(img: np.ndarray) -> bytes:
    """Encode an OpenCV numpy array into PNG bytes."""
    success, buffer = cv2.imencode(".png", img)
    if not success:
        raise ValueError("Failed to encode image to PNG format.")
    return buffer.tobytes()

def image_bytes_to_enhanced(image_bytes: bytes) -> bytes:
    """Convenience helper to take arbitrary image bytes, enhance, and return PNG bytes."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Invalid image file format.")
    enhanced = enhance_cv2_image(img)
    return cv2_to_png_bytes(enhanced)
