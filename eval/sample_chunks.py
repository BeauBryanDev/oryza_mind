#%%
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent

CHUNKS_PATH = EVAL_DIR.parent / "RAG" / "chunks.json"
OUT_PATH = EVAL_DIR / "golden_candidates.jsonl"
SEED = 42
N_SAMPLES = 30
MIN_WORDS = 40

#%%
with CHUNKS_PATH.open(encoding="utf-8") as f:
    chunks = json.load(f)

print(len(chunks))
print(Counter(c["chunk_type"] for c in chunks))
print(Counter(c["disease_name"] for c in chunks))

#%%
eligible = [
    c for c in chunks
    if c["chunk_type"] == "narrative"
    and not c["is_inoculation_protocol"]
    and c["word_count"] >= MIN_WORDS
]
print(len(eligible))

#%%
rng = random.Random(SEED)
groups = defaultdict(list)
for c in eligible:
    groups[c["disease_name"] or "general"].append(c)
for items in groups.values():
    rng.shuffle(items)

sample = []
while len(sample) < N_SAMPLES and any(groups.values()):
    for key in sorted(groups):
        if groups[key] and len(sample) < N_SAMPLES:
            sample.append(groups[key].pop())

print(Counter(c["disease_name"] or "general" for c in sample))

#%%
fields = ("chunk_id", "source_document", "section", "page_start", "disease_name", "text")
with OUT_PATH.open("w", encoding="utf-8") as f:
    for c in sample:
        f.write(json.dumps({k: c[k] for k in fields}, ensure_ascii=False) + "\n")
