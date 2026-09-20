
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

# The six output classes of the YOLOv8s-seg detector.[ dieases names ]
CLASS_NAMES: tuple[str, ...] = (  # these are the x6 class my yolo-seg model detects
    "Bacterial_Leaf_Blight",
    "Brown_Spot",
    "Leaf_Blast",
    "Narrow_Brown",
    "Rice_Tungro",
    "Sheath_Blight",
)

# Per-class detection thresholds. Lower :: weaker detections are allowed through
# for that class. The three low-recall classes drop to 0.15; the rest stay near
# default. Calibrated starting points from the v4 eval.
DETECT_THRESHOLDS: dict[str, float] = { #  intended becuase model did not got good metrics
    "Bacterial_Leaf_Blight": 0.25,
    "Brown_Spot": 0.15,
    "Leaf_Blast": 0.15,
    "Narrow_Brown": 0.15,
    "Rice_Tungro": 0.30,
    "Sheath_Blight": 0.30,
}  # it was a bleeding dificult dataset training day , hence even though
#  metrics were not good, I made inference test and I liked the results

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    # Load e5 on a background thread at startup so the first request does not
    # pay ~40s and hit nginx's proxy_read_timeout. Off for tests and the ETL.
    warmup_encoder: bool = True

    # Gemini
    gemini_api_key: str

    # Gemini 3 thinks by default and picks its own budget
    gemini_model: str = "gemini-3.1-flash-lite"
    temperature: float = 0.2 # Temperature for the model
    # Gemini 3 thinks by default and picks its own budget, which measured 10s to
    # 201s on identical work. Off here: retrieval is deterministic and the
    # passages are pre-filtered, so the model summarizes rather than reasons.
 
    gemini_thinking_budget: int = 0
    # Save money and time. I do not need Gemini to think. The client default timeout=None
    #  this is not rocket science, but it hangs forever, so a bound is needed.

    gemini_timeout: float = 25.0
    # attempts, not extra tries: langchain maps this straight to
    # HttpRetryOptions(attempts=N), so 1 means a single try with no retry.
    # Google dropping the connection mid-call is real and worth one more go.
    gemini_max_retries: int = 2

    # Weaviate
    weaviate_url: str
    weaviate_api_key: str
    weaviate_collection: str = "OryzaMindChunk"

    # Embeddings
    embedding_model: str = "intfloat/e5-large-v2"
    embedding_dim: int = 1024
    embedding_query_prefix: str = "query: "

    # Retrieval
    retrieval_top_k: int = 5
    retrieval_max_top_k: int = 20

    # Vision  RICE LEAVES DISEASES MODEL 
    yolo_model_path: Path = REPO_ROOT / "ml" / "oryza_mind_vision_yolo_seg_model.onnx"
    # Global floor. 0.15 matches the lowest per-class value; raising it would
    # cancel the recall recovery. Read via confidence_threshold_for().
    yolo_confidence_threshold: float = 0.15
    yolo_iou_threshold: float = 0.45
    yolo_mask_threshold: float = 0.5
    yolo_input_size: int = 640

    # Spike classifier  EfficientNetB0,  TF/Keras -> ONNX via tf2onnx
    spike_model_path: Path = REPO_ROOT / "ml" / "Rice_Spike_Model.onnx"
    spike_input_size: int = 640
    # Single sigmoid output: p is P(unhealthy). Above the threshold => UNHEALTHY.
    spike_threshold: float = 0.5 # this is a binary CNN classifier
    # Below this margin from the threshold the call is reported as uncertain
    # rather than dressed up as a decision.
    spike_uncertain_margin: float = 0.10

    # Tabular tools, sklearn artifacts. Both are LLM-decided tools, not chain steps.
    fertilizer_model_path: Path = REPO_ROOT / "ml" / "decision_tree_fertilizer.joblib"
    crop_model_path: Path = REPO_ROOT / "ml" / "crop_recomendation_model.pkl"
    crop_class_path: Path = REPO_ROOT / "ml" / "crop_class.json"
    plant_health_model_path: Path = REPO_ROOT / "ml" / "plant_health_model.joblib"
    plant_health_class_path: Path = REPO_ROOT / "ml" / "plant_health_classes.json"
    # Below this top probability the soil profile is reported as ambiguous.
    crop_uncertain_threshold: float = 0.5

    # Market data. Two independent price sources, deliberately not merged:
    # FAOSTAT is annual USD/tonne for 43 countries, FEDEARROZ is monthly
    # COP/tonne for Colombia only and runs about two years fresher.
    faostat_prices_path: Path = REPO_ROOT / "RAG" / "rice_producer_prices.json"
    # FEDEARROZ / Fondo Nacional del Arroz, converted from xlsx by
    # scripts/convert_fedearroz.py. All values COP.
    fedearroz_prices_path: Path = REPO_ROOT / "RAG" / "fedearroz_prices.json"
    fedearroz_costs_path: Path = REPO_ROOT / "RAG" / "fedearroz_costs.json"
    fedearroz_area_path: Path = REPO_ROOT / "RAG" / "fedearroz_area.json"
    fedearroz_consumption_path: Path = REPO_ROOT / "RAG" / "fedearroz_consumption.json"

    # HTTP
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # CORS Handling here  to avoid headless browser errors  // it s to be changed on production
    @field_validator("embedding_model")
    @classmethod
    def _embedding_model_must_match_collection(cls, v: str) -> str:
 
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
        """
        Effective detection threshold for one class.

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
