#%%
import json
import re
from collections import defaultdict
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent

CHUNKS_PATH = EVAL_DIR.parent / "RAG" / "chunks.json"
OUT_PATH = EVAL_DIR / "inoculation_audit.md"
SCREENING_DOCUMENT_TYPE = "screening_manual"
MIN_MARKERS = 4
PREVIEW_CHARS = 450

MARKERS = {
    "inoculat": r"inoculat",
    "centrifuge": r"centrifug",
    "autoclave": r"autoclav",
    "sterile": r"steril",
    "petri": r"petri",
    "agar": r"\bagar\b|\bPSA\b|\bPDA\b",
    "incubate": r"incubat",
    "culture": r"stock culture|pure culture|culture medium|subcultur",
    "suspension": r"suspension",
    "rpm": r"\brpm\b",
    "cfu": r"\bcfu\b",
    "volume": r"\d\s?(?:µl|μl|ul|ml)\b",
    "needle": r"needle|pricking|clipping|injection",
    "ppm": r"\bppm\b",
}

#%%
with CHUNKS_PATH.open(encoding="utf-8") as f:
    chunks = json.load(f)

flagged = sum(1 for c in chunks if c["is_inoculation_protocol"])
screening = sum(1 for c in chunks if c["document_type"] == SCREENING_DOCUMENT_TYPE)
print(len(chunks), flagged, screening)

#%%
compiled = {name: re.compile(rx, re.I) for name, rx in MARKERS.items()}
step_rx = re.compile(r"\b\d{1,2}\.\s+[A-Z][a-z]+")


def markers_in(text):
    found = [name for name, rx in compiled.items() if rx.search(text)]
    if len(step_rx.findall(text)) >= 3:
        found.append("numbered_steps")
    return found


def group_of(chunk_id):
    return chunk_id.rsplit(":", 1)[0]


pool = [
    c for c in chunks
    if c["chunk_type"] == "narrative"
    and not c["is_inoculation_protocol"]
    and c["document_type"] != SCREENING_DOCUMENT_TYPE
]
by_id = {c["chunk_id"]: c for c in pool}
found = {cid: markers_in(c["text"]) for cid, c in by_id.items()}
strong = {cid for cid, m in found.items() if len(m) >= MIN_MARKERS}

groups = defaultdict(list)
for c in pool:
    groups[group_of(c["chunk_id"])].append(c["chunk_id"])

selected = set(strong)
group_score = defaultdict(int)
for cid in strong:
    selected.update(groups[group_of(cid)])
    group_score[group_of(cid)] = max(group_score[group_of(cid)], len(found[cid]))

ordered = sorted(
    selected,
    key=lambda cid: (-group_score[group_of(cid)], group_of(cid), by_id[cid]["chunk_index"]),
)
print(len(pool), len(strong), len(selected))

#%%
lines = [
    "# Inoculation audit",
    "",
    f"pool: {len(pool)} | strong hits: {len(strong)} | listed: {len(selected)}",
    "",
]
for cid in ordered:
    c = by_id[cid]
    role = "hit" if cid in strong else "neighbor"
    preview = " ".join(c["text"].split())[:PREVIEW_CHARS]
    lines += [
        f"### {cid} [{role}] markers={len(found[cid])}",
        f"- document: {c['source_document']} | section: {c['section']} | page: {c['page_start']}",
        f"- disease: {c['disease_name']} | type: {c['document_type']}",
        f"- matched: {', '.join(found[cid]) or 'none'}",
        f"> {preview}",
        "",
    ]
OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
print(OUT_PATH.resolve())
