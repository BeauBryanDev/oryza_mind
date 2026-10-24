#%%
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import CLASS_NAMES
from app.rag.retriever import RetrievalIntent, retrieve
from app.rag.vectorstore import close_client, embed_queries

GOLDEN_PATH = ROOT / "golden_questions.jsonl"
OUT_PATH = ROOT / "retrieval_eval_results.json"
K_MAX = 10
KS = (1, 3, 5)

#%%
with GOLDEN_PATH.open(encoding="utf-8") as f:
    golden = [json.loads(line) for line in f]

vectors = embed_queries([row["question"] for row in golden])
pairs = list(zip(golden, vectors))
filtered_pairs = [(r, v) for r, v in pairs if r["chunk_disease_label"] in CLASS_NAMES]
print(len(pairs), len(filtered_pairs))

#%%
def rank_of(expected, chunk_ids):
    for i, cid in enumerate(chunk_ids, start=1):
        if cid in expected:
            return i
    return None


def run_mode(mode_pairs, use_filter):
    results = []
    for row, vec in mode_pairs:
        disease = row["chunk_disease_label"] if use_filter else None
        res = retrieve(
            row["question"],
            disease_name=disease,
            intent=RetrievalIntent.TREATMENT,
            top_k=K_MAX,
            query_vector=vec,
        )
        ids = [c.chunk_id for c in res.chunks]
        results.append(
            {
                "id": row["id"],
                "rank": rank_of(set(row["expected_chunk_ids"]), ids),
                "top1": ids[0] if ids else None,
                "label_note": row["label_note"],
            }
        )
    return results


def summarize(results):
    n = len(results)
    out = {"n": n}
    for k in KS:
        out[f"hit@{k}"] = round(sum(1 for r in results if r["rank"] and r["rank"] <= k) / n, 3)
    out["mrr"] = round(sum(1 / r["rank"] for r in results if r["rank"]) / n, 3)
    return out


no_filter = run_mode(pairs, use_filter=False)
disease_filter = run_mode(filtered_pairs, use_filter=True)

summary = {
    "no_filter": summarize(no_filter),
    "disease_filter": summarize(disease_filter),
}
print(json.dumps(summary, indent=2))

#%%
for name, results in (("no_filter", no_filter), ("disease_filter", disease_filter)):
    print(name)
    for r in results:
        if r["rank"] is None or r["rank"] > 5:
            print(" ", r["id"], "rank", r["rank"], "top1", r["top1"], "|", r["label_note"])

#%%
PROBES = [
    "How do I inoculate rice leaves with Xanthomonas oryzae pv. oryzicola?",
    "How do I culture the false smut fungus on PSA plates for stock culture?",
]
WATCH = {
    "part-ii-section-2-chapter-2-pdf:55:2",
    "manual-on-biotic-stress-resistance-evalu:33:4",
}

probe_results = []
for q in PROBES:
    res = retrieve(q, intent=RetrievalIntent.TREATMENT, top_k=5)
    ids = [c.chunk_id for c in res.chunks]
    leaked = sorted(WATCH & set(ids))
    probe_results.append({"query": q, "top5": ids, "leaked": leaked})
    print(q)
    print(" ", ids)
    print("  leaked:", leaked)

#%%
with OUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(
        {
            "summary": summary,
            "no_filter": no_filter,
            "disease_filter": disease_filter,
            "probes": probe_results,
        },
        f,
        indent=2,
        ensure_ascii=False,
    )
close_client()
