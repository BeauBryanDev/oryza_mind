
from __future__ import annotations

from fastapi import Request

from app.core.exceptions import InvalidImageError, TooManyImagesError
from app.utils.image_utils import MAX_BYTES
"""Shared multipart image collection for the vision endpoints."""
# The field names are fixed, so the frontend can be trusted.
FIELD_PREFIX = "image_"


async def collect_images(request: Request, max_images: int) -> list[tuple[bytes, str | None]]:
    """
    Read image_0..image_N from the form, in index order.

    Reads the form rather than declaring fixed parameters so the field count is
    governed by max_images alone, and an extra image is rejected with our own
    error instead of being silently ignored by FastAPI.
    """
    form = await request.form()
    
    fields = sorted(k for k in form.keys() if k.startswith(FIELD_PREFIX))
    
    if len(fields) > max_images:
        
        raise TooManyImagesError(f"{len(fields)} images sent; the limit is {max_images}.")
        #TODO: I am not sure if this is the right error to raise, I think it is a bad request
        # MANY IMAGES TAKES BLEEDING TIME, I WILL SEE HOW IT GOES
    images: list[tuple[bytes, str | None]] = []
    
    for key in fields:
        
        upload = form[key]
        
        if isinstance(upload, str):
            
            raise InvalidImageError(f"Field {key} is text, not a file.")
        
        data = await upload.read()
        
        # decode_image re-checks this, but rejecting here avoids holding several
        # oversized buffers while the first one fails.
        if len(data) > MAX_BYTES:
            
            raise InvalidImageError(
                
                f"{upload.filename or key} is {len(data) / 1e6:.1f} MB; the limit is 8 MB."
            )
            
        images.append((data, upload.filename))
        
    return images
