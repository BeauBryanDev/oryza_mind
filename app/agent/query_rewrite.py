from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts import REWRITE_LITERAL_PROMPT, REWRITE_PHOTO_PROMPT
from app.core.config import get_settings

logger = logging.getLogger(__name__)
"""
Spanish chat -> English search query, for retrieval only.

e5-large-v2 and the corpus are English: raw Spanish questions measured hit@5
0.04 without a photo, 0.42 with one; rewritten, 0.71 and 0.875. English is
never sent here, because rewriting it measured worse than leaving it alone.
"""

COMMON_NAMES = {
    "Bacterial_Leaf_Blight": "bacterial leaf blight",
    "Brown_Spot": "brown spot",
    "Leaf_Blast": "rice blast",
    "Narrow_Brown": "narrow brown leaf spot",
    "Rice_Tungro": "rice tungro",
    "Sheath_Blight": "sheath blight",
}

# Consent replies ("si, busquelo") carry no query worth a Gemini call.
MIN_REWRITE_WORDS = 3
MAX_QUERY_CHARS = 400

SPANISH_MARKS = re.compile(r"[¿¡ñáéíóú]", re.I)
# Function words only, so unaccented farmer typing still counts; anything that
# is also common English ("me", "a", "no") is left out.
SPANISH_WORDS = {
    "el", "la", "los", "las", "del", "de", "que", "y", "en", "un", "una", "unos",
    "por", "para", "con", "se", "es", "son", "mi", "mis", "le", "les", "lo", "su",
    "sus", "al", "como", "pero", "mas", "hay", "esta", "estan", "este", "esto",
    "muy", "cual", "cuando", "donde", "porque", "tiene", "tengo", "puedo", "debo",
    "hago", "sirve", "echo", "echarle", "ya", "sin", "sobre", "hojas", "hoja",
    "arroz", "mata", "matas", "lote", "cuanto",
}
ENGLISH_WORDS = {
    "the", "and", "of", "to", "is", "are", "in", "what", "how", "my", "it", "for",
    "with", "on", "do", "does", "can", "should", "when", "which", "this", "that",
    "from", "at", "be", "leaf", "leaves", "rice", "plant", "field", "spots",
}


def is_spanish(text: str) -> bool:
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    es = sum(w in SPANISH_WORDS for w in words) + (2 if SPANISH_MARKS.search(text) else 0)
    en = sum(w in ENGLISH_WORDS for w in words)
    return es >= 2 and es > en


@lru_cache(maxsize=1)
def get_rewrite_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        thinking_budget=settings.gemini_thinking_budget,
        timeout=settings.query_rewrite_timeout,
        max_retries=1,  # attempts, not retries: one try, then the raw message
    )


def _rewrite(message: str, disease: str | None) -> str:
    
    system = (REWRITE_PHOTO_PROMPT.format(disease=COMMON_NAMES[disease])
              if disease in COMMON_NAMES else REWRITE_LITERAL_PROMPT)
    
    started = time.perf_counter()
    try:
        response = get_rewrite_llm().invoke(
            [SystemMessage(content=system), HumanMessage(content=message)])
        
        lines = [l.strip().strip("\"'`") for l in (response.text or "").splitlines()]
        
        query = next((l for l in lines if l), "")[:MAX_QUERY_CHARS]
        
    except Exception as exc:
        logger.warning("query rewrite failed after %.1fs, using raw message: %s",
                       time.perf_counter() - started, exc)
        return message
    logger.info("query rewrite %.1fs (%s)", time.perf_counter() - started,
                "photo" if disease in COMMON_NAMES else "literal")
    
    logger.debug("rewritten query: %s", query)
    return query or message


def retrieval_queries(message: str, 
                      targets: list[str | None]
                      ) -> list[str]:
    """One query per retrieval target, rewritten only for Spanish messages."""
    if (not get_settings().query_rewrite_enabled
            or len(message.split()) < MIN_REWRITE_WORDS
            or not is_spanish(message)):
        return [message] * len(targets)
    
    if len(targets) == 1:
        return [_rewrite(message, targets[0])]
    # Co-infection: one rewrite per class, in parallel so the turn pays one call.
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        
        return list(pool.map(lambda t: _rewrite(message, t), targets))
