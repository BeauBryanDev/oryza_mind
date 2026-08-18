
from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.retriever import RetrievedChunk
from app.schemas.common import PipelineStage, SeverityLevel
"""Agent state carried through one analysis or chat turn."""

@dataclass
class AgentState:
    session_id: str
    stage: PipelineStage = PipelineStage.IDLE

    # Set once vision has run. None on a cold chat with no photo.
    # disease_name is the dominant class; diseases holds every class detected.
    # A leaf can carry several at once, so retrieval reads diseases, not this.
    disease_name: str | None = None
    diseases: list[str] = field(default_factory=list)
    confidence: float | None = None
    severity: SeverityLevel | None = None
    affected_ratio: float | None = None
    lesion_count: int = 0

    retrieved: list[RetrievedChunk] = field(default_factory=list)
    answer: str | None = None
    error: str | None = None

    @property
    def has_diagnosis(self) -> bool:
        
        return self.disease_name is not None

    @property
    def target_diseases(self) -> list[str]:
        """Every class to retrieve for. Falls back to the dominant one."""
        if self.diseases:
            return self.diseases
        
        return [self.disease_name] if self.disease_name else []

    @property
    def is_coinfection(self) -> bool:
        
        return len(self.target_diseases) > 1

    @property
    def is_low_confidence(self) -> bool:
        """Below this the identification is reported as uncertain, not asserted."""
        return self.confidence is not None and self.confidence < 0.50
    # TODO: I might have to  mess with  this confidence in order to boost detections at low  .... 
    def fail(self, message: str) -> "AgentState":
        
        self.stage = PipelineStage.ERROR
        self.error = message
        
        return self
