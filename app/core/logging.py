
from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from app.core.config import get_settings

# Regexes to scrub PII from logs. The first pattern is the most aggressive.
_REDACT_PATTERNS = (
    re.compile(r"(AIza[0-9A-Za-z_\-]{20,})"), # Google API keys
    re.compile(r"(?i)(api[_-]?key[\"'\s:=]+)([^\s\"',}]+)"),
    re.compile(r"(?i)(authorization[\"'\s:=]+bearer\s+)(\S+)"),
)


class RedactionFilter(logging.Filter):
    
    def filter(self, record: logging.LogRecord) -> bool:
        
        if isinstance(record.msg, str):
            
            record.msg = self._scrub(record.msg)
            
        if record.args:
            
            if isinstance(record.args, dict):
                
                record.args = {k: self._scrub_any(v) for k, v in record.args.items()}
                
            else:
                record.args = tuple(self._scrub_any(a) for a in record.args)
                
        return True


    @staticmethod
    def _scrub(text: str) -> str:
        
        for pattern in _REDACT_PATTERNS:
            
            if pattern.groups == 1:
                
                text = pattern.sub("[REDACTED]", text)
                
            else:
                
                text = pattern.sub(r"\1[REDACTED]", text)
                
        return text

    @classmethod
    def _scrub_any(cls, value: Any) -> Any:
        
        return cls._scrub(value) if isinstance(value, str) else value


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log collectors in deployed environments."""

    def format(self, record: logging.LogRecord) -> str:
        
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            
            payload["exception"] = self.formatException(record.exc_info)
            
        for key, value in getattr(record, "extra_fields", {}).items():
            
            payload[key] = value
            
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    
    settings = get_settings()
    
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactionFilter())
    
    if settings.environment == "development":
        
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s")
        )
    else:
        handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # These are chatty at INFO and drown out our own lines.
    for noisy in ("httpx", "httpcore", "urllib3", "sentence_transformers"):
        
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "logging ready | env=%s level=%s", 
        settings.environment, 
        settings.log_level
    )


def get_logger(name: str) -> logging.Logger:
    
    return logging.getLogger(name)
