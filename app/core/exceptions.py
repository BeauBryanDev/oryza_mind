
from __future__ import annotations

## My  OryzaMindError  Exceptions
class OryzaError(Exception):
    """Base for every error this app raises deliberately."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None):
        self.message = message or self.__doc__ or "Unexpected error"
        super().__init__(self.message)

    def to_payload(self) -> dict[str, str]:
        return {"message": self.message, "code": self.code}


# Input
class InvalidImageError(OryzaError):
    """The uploaded file could not be decoded as an image."""

    status_code = 400
    code = "invalid_image"


class ImageTooLargeError(OryzaError):
    """The uploaded image exceeds the size limit."""

    status_code = 413
    code = "image_too_large"


class TooManyImagesError(OryzaError):
    """More images were uploaded than the pipeline accepts."""

    status_code = 400
    code = "too_many_images"


# Vision
class ModelNotLoadedError(OryzaError):
    """The YOLO ONNX model is not available."""

    status_code = 503
    code = "model_not_loaded"


class InferenceError(OryzaError):
    """The vision model failed during inference."""

    status_code = 500
    code = "inference_failed"


class NoDetectionError(OryzaError):
    """No disease was detected with sufficient confidence."""

    # Not an error condition for the pipeline -- a healthy leaf is a valid
    # result. Raised only where a caller genuinely requires a detection.
    status_code = 422
    code = "no_detection"


# Retrieval
class UnknownDiseaseClassError(OryzaError):
    """A disease name outside the 6 canonical YOLO classes was supplied."""

    status_code = 400
    code = "unknown_disease_class"


class RetrievalError(OryzaError):
    """The knowledge base could not be queried."""

    status_code = 503
    code = "retrieval_failed"


class EmbeddingError(OryzaError):
    """The query could not be embedded."""

    status_code = 503
    code = "embedding_failed"


# Agent
class AgentError(OryzaError):
    """The reasoning agent failed to produce a response."""

    status_code = 502
    code = "agent_failed"


class UnsafeContentError(OryzaError):
    """Generated content failed a safety check and was withheld.

    Raised rather than returned: an inoculation protocol reaching the answer
    layer is a bug worth surfacing loudly, not degrading past quietly.
    """

    status_code = 500
    code = "unsafe_content"
