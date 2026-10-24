
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


# Query rewrite for Spanish chat. Retrieval only: the answer still sees the
# farmer's own words.

# No photo: vision has said nothing, so the query carries only what the farmer
# wrote. Local names the farmer used may be standardised, never added.
REWRITE_LITERAL_PROMPT = (
    "Translate a rice farmer's message into one English search query for a library "
    "of English rice literature. Translate literally and faithfully. Describe symptoms "
    "exactly as the farmer describes them. If the farmer names a disease, pest or weed, "
    "give its standard English or scientific name (anublo de la vaina = sheath blight, "
    "piricularia = rice blast, sogata = Tagosodes orizicolus, liendre de puerco = "
    "Echinochloa colona). NEVER name a disease, virus, bacterium or pest the farmer did "
    "not name, even if the symptoms suggest one. Do not answer. Output only the query, "
    "one line."
)

# Photo: the disease comes from vision, so the rewrite is anchored to it.
REWRITE_PHOTO_PROMPT = (
    "A vision model diagnosed the farmer's rice photo as: {disease}. Rewrite the "
    "farmer's message into one English search query about {disease}. Use that disease "
    "name and no other disease. Keep the farmer's actual question (symptoms, control, "
    "timing, products, fertilizer). Do not answer. Output only the query, one line."
)
