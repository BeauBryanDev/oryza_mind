
from __future__ import annotations

import logging
import re

from app.agent.spike_agent import run_spike_agent
from app.core.config import get_settings
from app.core.load_spike_model import get_spike_model
from app.schemas.chat import Citation
from app.schemas.spike import SpikeLabel, SpikePrediction, SpikeResult
from app.utils.image_utils import decode_image
from app.utils.preprocessing import to_spike_tensor

logger = logging.getLogger(__name__)
"""
Spike classification. Owns the model call and the batch verdict, nothing else.

Separate from vision_service on purpose: this is a different model, a different
tensor layout, and its classes are not the six canonical disease strings, so it
never feeds the Weaviate `disease_name` filter I made before adding the new CNN model.
"""
# Rice Spikes EfficientNetB0 Model came later, so I did not put it under existing vision helpers 
MAX_IMAGES = 3

MARKDOWN_EMPHASIS = re.compile(r"\*{1,2}([^*]+)\*{1,2}")


def classify_spike(
    data: bytes, 
    image_index: int = 0, 
    filename: str | None = None
) -> SpikePrediction:
    
    settings = get_settings()
    image = decode_image(data, filename)
    # This came form  utils.preprocessing.to_spike_tensor -> Single Responsability Principle
    tensor = to_spike_tensor(image, settings.spike_input_size)
    score = get_spike_model().run(tensor)
    # here is where Inference takes place
    unhealthy = score > settings.spike_threshold
    label = SpikeLabel.UNHEALTHY if unhealthy else SpikeLabel.HEALTHY
    confidence = score if unhealthy else 1.0 - score

    prediction = SpikePrediction(
        image_index=image_index,
        filename=filename,
        label=label,
        confidence=confidence,
        unhealthy_score=score,
        uncertain=abs(score - settings.spike_threshold) < settings.spike_uncertain_margin,
    )
    logger.info(
        "spike image %d: %s (score=%.4f%s)",
        image_index,
        label.value,
        score,
        ", uncertain" if prediction.uncertain else "",
    )
    
    return prediction


def _to_lines(reply: str) -> list[str] | None:
    """
    One recommendation per line, markdown stripped.

    Same net as the analysis service: the panel takes a string[], so a table
    separator row would otherwise arrive as a bullet point.
    """
    out: list[str] = []
    
    for raw in reply.splitlines():
        
        line = raw.strip().lstrip("-*• ").strip()
        
        if not line or line.startswith(("#", "|", "```")):
            continue
        
        line = MARKDOWN_EMPHASIS.sub(r"\1", line)
        
        if len(line) > 2:
            
            out.append(line)
            
    return out or None


def _advise(result: SpikeResult) -> None:
    """Attach the agent's assessment. Never fatal: a verdict without advice is
    still useful, a 500 is not."""
    try:
        answer, chunks, grounded = run_spike_agent(result)
        
    except Exception:
        logger.exception("spike recommendations failed; returning verdict only")
        return

    result.assessment = answer
    result.recommendations = _to_lines(answer)
    result.grounded = grounded
    result.citations = [
        Citation(
            chunk_id=c.chunk_id,
            document_title=c.document_title or c.source_document,
            organization=c.organization,
            page_start=c.page_start,
            source_url=c.source_url,
        )
        for c in chunks
    ]


def classify(
    images: list[tuple[bytes, str | None]],
    with_recommendations: bool = True,
) -> SpikeResult:
    
    predictions = [
        
        classify_spike(data, i, filename) for i, (data, filename) in enumerate(images)
    ]
    
    unhealthy_count = sum(p.label is SpikeLabel.UNHEALTHY for p in predictions)

    result = SpikeResult(
        predictions=predictions,
        overall_label=SpikeLabel.UNHEALTHY if unhealthy_count else SpikeLabel.HEALTHY,
        unhealthy_count=unhealthy_count,
        total_count=len(predictions),
    )

    if with_recommendations and predictions:
        _advise(result)
        
    return result
