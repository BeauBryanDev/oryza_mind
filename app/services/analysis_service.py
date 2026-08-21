
from __future__ import annotations

import logging
import re
from collections import defaultdict

import numpy as np

from app.agent.agent import run_agent
from app.agent.state import AgentState
from app.core.exceptions import TooManyImagesError
from app.schemas.analysis import AnalysisResult, DiseaseFinding, SegmentationResult
from app.rag.prompts import RECOMMENDATION_FORMAT
from app.schemas.common import SCIENTIFIC_NAMES, PipelineStage, severity_from_area
from app.services.vision_service import ImageAnalysis, analyze_image
from app.utils.segmentation import union_mask

logger = logging.getLogger(__name__)

MAX_IMAGES = 3

MARKDOWN_EMPHASIS = re.compile(r"\*{1,2}([^*]+)\*{1,2}")


def _aggregate(analyses: list[ImageAnalysis]) -> list[DiseaseFinding]:
    """
    Merge per-image detections into one finding per disease.

    Area is measured against total pixels across every submitted image, so the
    ratios of several findings are comparable and sum sensibly.
    """
    total_px = sum(a.total_px for a in analyses) or 1
    
    acc: dict[str, dict] = defaultdict(
        
        lambda: {"best": 0.0, "n": 0, "px": 0, "images": set()}
    )

    for a in analyses:
        
        h, w = a.image_bgr.shape[:2] #  the image size
        by_class: dict[str, list[np.ndarray]] = defaultdict(list)
        
        for det, mask in zip(a.result.detections, a.masks):
            
            entry = acc[det.class_name]
            entry["best"] = max(entry["best"], det.confidence)
            entry["n"] += 1
            entry["images"].add(a.result.image_index)
            by_class[det.class_name].append(mask)
        # Union per class per image: overlapping lesions of the same disease
        # must not be counted twice.
        for name, masks in by_class.items():
            
            acc[name]["px"] += int(np.count_nonzero(union_mask(masks, (h, w))))

    findings = [
        DiseaseFinding(
            name=name,
            scientific_name=SCIENTIFIC_NAMES.get(name),
            confidence=d["best"],
            lesion_count=d["n"],
            affected_ratio=min(d["px"] / total_px, 1.0),
            severity=severity_from_area(d["px"] / total_px),
            image_indices=sorted(d["images"]),
        )
        for name, d in acc.items()
    ]
    return sorted(findings, key=lambda f: -f.affected_ratio)


def analyze(
    images: list[tuple[bytes, str | None]],
    with_recommendations: bool = True,
) -> AnalysisResult:
    
    if not images:
        
        return AnalysisResult()
    
    if len(images) > MAX_IMAGES:
        
        raise TooManyImagesError(f"{len(images)} images sent; the limit is {MAX_IMAGES}.")

    analyses = [
        
        analyze_image(data, image_index=i, filename=name)
        for i, (data, name) in enumerate(images)
    ]

    findings = _aggregate(analyses)
    total_px = sum(a.total_px for a in analyses) or 1
    lesion_px = sum(a.lesion_px for a in analyses)
    overall = min(lesion_px / total_px, 1.0)

    segmentations = [
        SegmentationResult(
            image_index=a.result.image_index,
            original_url="",  # the client already holds its own preview
            overlay_url=a.result.overlay_data_uri or "",
            lesion_count=len(a.result.detections),
            affected_ratio=a.result.affected_ratio,
            diseases=sorted({d.class_name for d in a.result.detections}),
        )
        for a in analyses
    ]

    result = AnalysisResult(
        diseases=findings,
        primary_disease=findings[0] if findings else None,
        overall_affected_ratio=overall,
        overall_severity=severity_from_area(overall),
        segmentations=segmentations,
        metadata={"images": len(images), "total_lesions": sum(f.lesion_count for f in findings)},
    )

    if with_recommendations and findings:
        
        result.recommendations = _recommend(result)
        
    return result


def _to_lines(reply: str) -> list[str] | None:
    """
    One recommendation per line, markdown stripped.

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


def _recommend(result: AnalysisResult) -> list[str] | None:
    """
    Ask the agent for management guidance. Never fatal: a diagnosis without
    recommendations is still useful, a 500 is not."""
    primary = result.primary_disease
    
    if primary is None:
        return None

    others = [f.name for f in result.diseases if f.name != primary.name]
    question = (
        f"The photo shows {primary.name}"
        + (f", and also {', '.join(others)}" if others else "")
        + f". Severity {result.overall_severity.value}, "
        f"{result.overall_affected_ratio:.1%} of the image shows lesions. "
        "Give practical management steps."
    )
    state = AgentState(
        session_id="analysis",
        stage=PipelineStage.GENERATING_DIAGNOSIS,
        disease_name=primary.name,
        diseases=[f.name for f in result.diseases],
        confidence=primary.confidence,
        severity=result.overall_severity,
        affected_ratio=result.overall_affected_ratio,
        lesion_count=sum(f.lesion_count for f in result.diseases),
    )
    try:
        reply, _ = run_agent(question, state, format_rule=RECOMMENDATION_FORMAT)
        
    except Exception:
        logger.exception("recommendation generation failed; returning vision only")
        return None
    
    return _to_lines(reply)
