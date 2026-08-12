
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

# The six output classes of the YOLOv11-small-seg detector. These strings are also
# the `disease_name` metadata values in Weaviate -- the CV->RAG chain matches
CLASS_NAMES: tuple[str, ...] = (  # these are the x6 class my yolo model detects
    "Bacterial_Leaf_Blight",
    "Brown_Spot",
    "Leaf_Blast",
    "Narrow_Brown",
    "Rice_Tungro",
    "Sheath_Blight",
)

# Per-class detection thresholds. Lower => weaker detections are allowed through
# for that class. The three low-recall classes drop to 0.15; the rest stay near
# default. Calibrated starting points from the v4 eval.
DETECT_THRESHOLDS: dict[str, float] = {
    "Bacterial_Leaf_Blight": 0.25,
    "Brown_Spot": 0.15,
    "Leaf_Blast": 0.15,
    "Narrow_Brown": 0.15,
    "Rice_Tungro": 0.30,
    "Sheath_Blight": 0.30,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # Weaviate
    weaviate_url: str
    weaviate_api_key: str
    weaviate_collection: str = "OryzaMindChunk"

    # Embeddings
    # Validated, not just defaulted: changing this without re-embedding all
    # 2,030 vectors breaks retrieval silently.
    embedding_model: str = "intfloat/e5-large-v2"
    embedding_dim: int = 1024
    embedding_query_prefix: str = "query: "

    # Retrieval
    retrieval_top_k: int = 5
    retrieval_max_top_k: int = 20

    # Vision
    yolo_model_path: Path = REPO_ROOT / "ml" / "oryza_mind_vision_yolo_seg_model.onnx"
    # Global floor. 0.15 matches the lowest per-class value; raising it would
    # cancel the recall recovery. Read via confidence_threshold_for().
    yolo_confidence_threshold: float = 0.15
    yolo_iou_threshold: float = 0.45
    yolo_mask_threshold: float = 0.5
    yolo_input_size: int = 640

    # HTTP
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("embedding_model")
    @classmethod
    def _embedding_model_must_match_collection(cls, v: str) -> str:
        # The bare name is unambiguous and common in .env files, but it does not
        # resolve on HuggingFace. Normalize rather than reject.
        if v == "e5-large-v2":
            v = "intfloat/e5-large-v2"
        if v != "intfloat/e5-large-v2":
            raise ValueError(
                f"embedding_model is {v!r}, but the live OryzaMindChunk collection "
                "was built with 'intfloat/e5-large-v2' (1024-dim). Using a different "
                "model would produce meaningless similarity scores with no error. "
                "Re-embed all 2,030 chunks before changing this."
            )
        return v

    def confidence_threshold_for(self, class_name: str) -> float:
        """Effective detection threshold for one class.

        The per-class value wins, but never drops below the global floor. Keeps
        the two settings from silently contradicting each other.
        """
        return max(
            self.yolo_confidence_threshold,
            DETECT_THRESHOLDS.get(class_name, self.yolo_confidence_threshold),
        )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
