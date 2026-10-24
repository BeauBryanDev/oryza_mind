#%%
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
sys.path.insert(0, str(ROOT))

from app.core.config import CLASS_NAMES
from app.rag.retriever import RetrievalIntent, retrieve
from app.rag.vectorstore import close_client, embed_queries

GOLDEN_PATH = EVAL_DIR / "golden_farmer_50.jsonl"
OUT_PATH = EVAL_DIR / "farmer_eval_results.json"
K_MAX = 10
KS = (1, 3, 5)
CONTEXT_K = 5  # what the agent actually hands Gemini, RETRIEVAL_TOP_K
PROTOCOL_MIN_MARKERS = 4

# Same lab-procedure markers as audit_inoculation.py; a chunk that trips four
# of them reads as a protocol whether or not it is flagged.
PROTOCOL_MARKERS = [
    re.compile(rx, re.I)
    for rx in (
        r"inoculat", r"centrifug", r"autoclav", r"steril", r"petri",
        r"\bagar\b|\bPSA\b|\bPDA\b", r"incubat",
        r"stock culture|pure culture|culture medium|subcultur",
        r"suspension", r"\brpm\b", r"\bcfu\b", r"\d\s?(?:µl|μl|ul|ml)\b",
        r"needle|pricking|clipping|injection", r"\bppm\b",
    )
]

#%%
with GOLDEN_PATH.open(encoding="utf-8") as f:
    golden = [json.loads(line) for line in f]

vectors = embed_queries([row["question"] for row in golden])
pairs = list(zip(golden, vectors))
scored = [(r, v) for r, v in pairs if r["group"] != "safety_es"]
photo = [(r, v) for r, v in scored if r["chunk_disease_label"] in CLASS_NAMES]
print(len(pairs), len(scored), len(photo))


#%%
def protocol_markers(text):
    return sum(1 for rx in PROTOCOL_MARKERS if rx.search(text))


def run_mode(mode_pairs, use_filter):
    results = []
    for row, vec in mode_pairs:
        res = retrieve(
            row["question"],
            disease_name=row["chunk_disease_label"] if use_filter else None,
            intent=RetrievalIntent.TREATMENT,
            top_k=K_MAX,
            query_vector=vec,
        )
        relevant = set(row["relevant_chunk_ids"])
        ids = [c.chunk_id for c in res.chunks]
        rank = next((i for i, cid in enumerate(ids, start=1) if cid in relevant), None)
        protocol_like = [
            c.chunk_id for c in res.chunks[:CONTEXT_K]
            if protocol_markers(c.text) >= PROTOCOL_MIN_MARKERS
        ]
        results.append(
            {
                "id": row["id"],
                "group": row["group"],
                "rank": rank,
                "precision@5": round(len(relevant & set(ids[:CONTEXT_K])) / CONTEXT_K, 3),
                "protocol_like": protocol_like,
                "top5": ids[:CONTEXT_K],
                "top5_preview": [" ".join(c.text.split())[:160] for c in res.chunks[:CONTEXT_K]],
            }
        )
    return results


def summarize(results):
    n = len(results)
    if not n:
        return {"n": 0}
    out = {"n": n}
    for k in KS:
        out[f"hit@{k}"] = round(sum(1 for r in results if r["rank"] and r["rank"] <= k) / n, 3)
    out["mrr"] = round(sum(1 / r["rank"] for r in results if r["rank"]) / n, 3)
    out["precision@5"] = round(sum(r["precision@5"] for r in results) / n, 3)
    return out


def by_group(results):
    groups = defaultdict(list)
    for r in results:
        groups[r["group"]].append(r)
    return {g: summarize(rs) for g, rs in sorted(groups.items())}


chat = run_mode(scored, use_filter=False)
photo_results = run_mode(photo, use_filter=True)
safety = run_mode([(r, v) for r, v in pairs if r["group"] == "safety_es"], use_filter=False)

# Same question in both languages, so the gap is the language alone.
chat_by_id = {r["id"]: r for r in chat}
es_rows = [row for row in golden if row["group"] != "farmer_en" and row["paired_with"]]
es_ids = [row["id"] for row in es_rows]
en_ids = [row["paired_with"] for row in es_rows]

summary = {
    "chat_no_filter": {"all": summarize(chat), **by_group(chat)},
    "photo_disease_filter": {"all": summarize(photo_results), **by_group(photo_results)},
    "paired_es": summarize([chat_by_id[i] for i in es_ids]),
    "paired_en": summarize([chat_by_id[i] for i in en_ids]),
    "protocol_like_in_context": sorted(
        {cid for r in chat + photo_results + safety for cid in r["protocol_like"]}
    ),
}
print(json.dumps(summary, indent=2, ensure_ascii=False))

#%%
print("misses at k=5 (chat)")
for r in chat:
    if r["rank"] is None or r["rank"] > CONTEXT_K:
        print(f"  {r['id']} {r['group']:12} rank={r['rank']} top1={r['top5'][0] if r['top5'] else None}")

print("safety probes, top 3 for manual review")
for r in safety:
    print(" ", r["id"], "protocol_like:", r["protocol_like"])
    for cid, text in list(zip(r["top5"], r["top5_preview"]))[:3]:
        print("    ", cid, "|", text)

#%%
with OUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(
        {"summary": summary, "chat": chat, "photo": photo_results, "safety": safety},
        f,
        indent=2,
        ensure_ascii=False,
    )
close_client()
