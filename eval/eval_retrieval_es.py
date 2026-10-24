#%%
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
sys.path.insert(0, str(ROOT))

from app.core.config import CLASS_NAMES
from app.rag.retriever import RetrievalIntent, retrieve
from app.rag.vectorstore import close_client, embed_queries

GOLDEN_PATH = EVAL_DIR / "golden_questions_es.jsonl"
EN_RESULTS_PATH = ROOT / "retrieval_eval_results.json"
OUT_PATH = EVAL_DIR / "retrieval_eval_es_results.json"
K_MAX = 10
KS = (1, 3, 5)

#%%
with GOLDEN_PATH.open(encoding="utf-8") as f:
    golden = [json.loads(line) for line in f]

en_rank = {}
if EN_RESULTS_PATH.exists():
    en = json.loads(EN_RESULTS_PATH.read_text(encoding="utf-8"))
    en_rank = {r["id"]: r["rank"] for r in en["no_filter"]}

vectors = embed_queries([row["question"] for row in golden])
pairs = list(zip(golden, vectors))
# Lab-protocol targets must never come back under TREATMENT intent: they are
# leakage probes, scored apart from recall.
probes = [(r, v) for r, v in pairs if r["expect_blocked"]]
scored = [(r, v) for r, v in pairs if not r["expect_blocked"]]
filtered = [(r, v) for r, v in scored if r["chunk_disease_label"] in CLASS_NAMES]
print(len(pairs), len(scored), len(filtered), len(probes))

#%%
def rank_of(expected, chunk_ids):
    for i, cid in enumerate(chunk_ids, start=1):
        if cid in expected:
            return i
    return None


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
        ids = [c.chunk_id for c in res.chunks]
        results.append(
            {
                "id": row["id"],
                "rank": rank_of(set(row["expected_chunk_ids"]), ids),
                "en_id": row["en_id"],
                "en_rank": en_rank.get(row["en_id"]),
                "top1": ids[0] if ids else None,
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


no_filter = run_mode(scored, use_filter=False)
disease_filter = run_mode(filtered, use_filter=True)
leaks = run_mode(probes, use_filter=False)

# Same questions in both languages, so any rank gap is the language alone.
paired = [r for r in no_filter if r["en_id"]]
summary = {
    "no_filter": summarize(no_filter),
    "disease_filter": summarize(disease_filter),
    "paired_es": summarize(paired),
    "paired_en": summarize([{"rank": r["en_rank"]} for r in paired]),
    "leaked": sum(1 for r in leaks if r["rank"] is not None),
}
print(json.dumps(summary, indent=2))

#%%
print("id    es   en   top1")
for r in no_filter:
    print(f"{r['id']}  {str(r['rank']):4} {str(r['en_rank']):4} {r['top1']}")
for r in leaks:
    print(r["id"], "LEAKED at rank" if r["rank"] else "blocked", r["rank"] or "")

#%%
with OUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(
        {
            "summary": summary,
            "no_filter": no_filter,
            "disease_filter": disease_filter,
            "probes": leaks,
        },
        f,
        indent=2,
        ensure_ascii=False,
    )
close_client()
