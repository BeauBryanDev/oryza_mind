
from __future__ import annotations

from app.agent.state import AgentState


def vision_context(state: AgentState) -> str:
    """Describe the current photo analysis, or say there isn't one."""
    if not state.has_diagnosis:
        
        return (
            "No leaf photo has been analyzed in this conversation. If the user "
            "asks about their crop, ask them to upload a photo, or answer "
            "generally from retrieved sources without naming a specific disease "
            "as theirs.  BE FRIENDLY THE FARMER IS ASKING FOR HELP"
        )

    lines = [
        "Current photo analysis:",
        f"- Disease: {state.disease_name}",
        f"- Confidence: {state.confidence:.1%}" if state.confidence else "",
        f"- Severity: {state.severity.value}" if state.severity else "",
        f"- Lesions detected: {state.lesion_count}",
    ]
    if state.is_coinfection:
        
        others = [d for d in state.target_diseases if d != state.disease_name]
        
        lines.insert(2, f"- Also detected on the same sample: {', '.join(others)}")
        lines.append(
            "- This is a co-infection. Cover every disease listed, each with its "
            "own management steps, and say plainly if a measure treats one but "
            "not the others. Do not merge them into a single plan."
        )
    if state.is_low_confidence:
        
        lines.append(
            "- Confidence is low. Present the identification as provisional and "
            "say what would confirm it."
        )

    return "\n".join(l for l in lines if l)
