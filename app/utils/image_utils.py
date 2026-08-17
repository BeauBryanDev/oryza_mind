
from __future__ import annotations

import cv2
import numpy as np

from app.core.exceptions import ImageTooLargeError, InvalidImageError
"""Upload decoding and validation."""

MAX_BYTES = 8 * 1024 * 1024  # matches frontend MAX_FILE_SIZE_MB
MIN_DIMENSION = 32
MAX_DIMENSION = 4096


def decode_image(data: bytes, filename: str | None = None) -> np.ndarray:
    """Bytes to a BGR uint8 array. Raises rather than returning None."""
    if not data:
        
        raise InvalidImageError("The uploaded file is empty.")
    
    if len(data) > MAX_BYTES:
        
        raise ImageTooLargeError(
            
            f"{filename or 'Image'} is {len(data) / 1e6:.1f} MB; the limit is 8 MB."
        )
    #  decode the image from bytes to numpy array
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    
    if image is None:
        
        raise InvalidImageError(
            
            f"{filename or 'The file'} could not be decoded as an image."
        )

    h, w = image.shape[:2]
    
    if min(h, w) < MIN_DIMENSION:
        
        raise InvalidImageError(f"Image is too small ({w}x{h}).")
    
    if max(h, w) > MAX_DIMENSION:
        
        raise InvalidImageError(f"Image is too large ({w}x{h}).")
    
    return image


def to_data_uri(image_bgr: np.ndarray, max_width: int = 1024) -> str:
    """BGR uint8 array to a data URI. Raises rather than returning None."""
    from app.utils.mask import to_data_uri as _to_data_uri

    return _to_data_uri(image_bgr, max_width)
