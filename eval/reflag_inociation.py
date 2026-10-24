#%%
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
sys.path.insert(0, str(ROOT))

from weaviate.classes.query import Filter

from app.rag.retriever import RetrievalIntent, retrieve
from app.rag.vectorstore import close_client, embed_queries, get_collection

CHUNKS_PATH = ROOT / "RAG" / "chunks.json"
FIXED_PATH = EVAL_DIR / "chunks.reflagged.json"
BACKUP_PATH = EVAL_DIR / "reflag_backup.json"
DRY_RUN = False

TARGET_IDS = [
    "part-ii-section-2-chapter-2-pdf:55:1",
    "part-ii-section-2-chapter-2-pdf:55:2",
    "part-ii-section-2-chapter-2-pdf:60:1",
    "part-ii-section-2-chapter-2-pdf:60:2",
    "part-ii-section-2-chapter-2-pdf:11:0",
    "part-ii-section-2-chapter-2-pdf:11:2",
    "part-ii-section-2-chapter-2-pdf:11:3",
    "part-ii-section-3-chapter-1-pdf:32:1",
    "part-ii-section-3-chapter-1-pdf:32:2",
    "fungus-chapter-2-foliar-diseases-pdf:43:0",
    "part-ii-section-2-chapter-2-pdf:16:2",
    "part-ii-section-2-chapter-2-pdf:25:0",
    "part-ii-section-2-chapter-2-pdf:59:0",
    "part-ii-section-3-chapter-2-pdf:12:1",
    "part-ii-section-2-chapter-2-pdf:14:0",
    "fungus-chapter-2-foliar-diseases-pdf:53:1",
]
TARGETS = set(TARGET_IDS)

#%%
with CHUNKS_PATH.open(encoding="utf-8") as f:
    chunks = json.load(f)

by_id = {c["chunk_id"]: c for c in chunks}
missing = [cid for cid in TARGET_IDS if cid not in by_id]
if missing or len(TARGETS) != len(TARGET_IDS):
    raise ValueError(f"missing or duplicated ids: {missing}")

print({cid: by_id[cid]["is_inoculation_protocol"] for cid in TARGET_IDS})

#%%
collection = get_collection()
plan = {}
for cid in TARGET_IDS:
    response = collection.query.fetch_objects(
        filters=Filter.by_property("chunk_id").equal(cid),
        limit=5,
        return_properties=["chunk_id", "is_inoculation_protocol"],
    )
    exact = [o for o in response.objects if o.properties.get("chunk_id") == cid]
    if len(exact) != 1:
        raise ValueError(f"{cid}: expected 1 exact match, got {len(exact)}")
    plan[cid] = {
        "uuid": str(exact[0].uuid),
        "before": exact[0].properties.get("is_inoculation_protocol"),
    }

print(json.dumps(plan, indent=2))

#%%
BACKUP_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")

if DRY_RUN:
    print("dry run, nothing changed")
else:
    for item in plan.values():
        collection.data.update(
            uuid=item["uuid"],
            properties={"is_inoculation_protocol": True},
        )
    for c in chunks:
        if c["chunk_id"] in TARGETS:
            c["is_inoculation_protocol"] = True
    FIXED_PATH.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    after = {}
    for cid, item in plan.items():
        obj = collection.query.fetch_object_by_id(
            item["uuid"], return_properties=["is_inoculation_protocol"]
        )
        after[cid] = obj.properties["is_inoculation_protocol"]
    print(all(after.values()), after)

#%%
queries = [" ".join(by_id[cid]["text"].split())[:300] for cid in TARGET_IDS]
vectors = embed_queries(queries)

leak_count = 0
for cid, q, vec in zip(TARGET_IDS, queries, vectors):
    res = retrieve(q, intent=RetrievalIntent.TREATMENT, top_k=10, query_vector=vec)
    leaked = sorted(TARGETS & {c.chunk_id for c in res.chunks})
    leak_count += len(leaked)
    print(cid, "->", leaked)
print("total leaks:", leak_count)

#%%
PROBES = [
    "How do I inoculate rice leaves with Xanthomonas oryzae pv. oryzicola?",
    "How do I culture the false smut fungus on PSA plates for stock culture?",
]
for q in PROBES:
    res = retrieve(q, intent=RetrievalIntent.TREATMENT, top_k=5)
    ids = [c.chunk_id for c in res.chunks]
    print(q)
    print(" ", ids)
    print("  leaked:", sorted(TARGETS & set(ids)))

close_client()

