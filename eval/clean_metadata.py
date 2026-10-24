#%%
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
sys.path.insert(0, str(ROOT))

from weaviate.classes.query import Filter

from app.rag.vectorstore import close_client, get_collection

CHUNKS_PATH = ROOT / "RAG" / "chunks.json"
CHUNKS_BACKUP_PATH = ROOT / "RAG" / "chunks.pre_clean.json"
BACKUP_PATH = EVAL_DIR / "clean_metadata_backup.json"
DRY_RUN = True

# Procedures for infecting plants or promoting disease. The three that were
# treatment_record become narrative, or invariant 1 breaks.
PROTOCOL_IDS = [
    "fungus-chapter-2-foliar-diseases-pdf:91:2",
    "fungus-chapter-2-foliar-diseases-pdf:91:1",
    "fungus-chapter-2-foliar-diseases-pdf:88:4",
    "part-ii-section-2-chapter-2-pdf:11:1",
    "part-ii-section-2-chapter-2-pdf:12:1",
]

# Reference lists that slipped past the Phase 1 bibliography cut. Two mixed
# chunks with ~110 words of prose ahead of the references stay in.
BIBLIOGRAPHY_IDS = [
    *[f"part-ii-section-5-ch-4-pdf:9:{i}" for i in (1, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20)],
    "part-ii-section-1-chapter-3-pdf:43:0",
    "part-ii-section-2-chapter-1-pdf:9:1",
    *[f"part-ii-section-2-chapter-2-pdf:49:{i}" for i in range(7)],
    "part-i-sec2-shifty-enemies-final-pdf:16:3",
    "part-i-sec2-shifty-enemies-final-pdf:16:4",
    *[f"rbsd-srbsd-final-pdf:10:{i}" for i in range(1, 15)],
    # Second pass: reference lists with fewer "Year." entries per chunk.
    *[f"part-ii-section-5-ch-4-pdf:9:{i}" for i in (2, 9, 14, 21)],
    "part-ii-section-2-chapter-2-pdf:49:7",
    "part-i-sec2-shifty-enemies-final-pdf:16:5",
    "part-iii-section-4-pdf:13:0",
]


def planned_change(chunk):
    if chunk["chunk_id"] in PROTOCOL_IDS:
        change = {"is_inoculation_protocol": True}
        if chunk["chunk_type"] == "treatment_record":
            change["chunk_type"] = "narrative"
        return change
    return {"chunk_type": "bibliography"}


#%%
with CHUNKS_PATH.open(encoding="utf-8") as f:
    chunks = json.load(f)
by_id = {c["chunk_id"]: c for c in chunks}

targets = PROTOCOL_IDS + BIBLIOGRAPHY_IDS
missing = [cid for cid in targets if cid not in by_id]
if missing or len(set(targets)) != len(targets):
    raise ValueError(f"missing or duplicated ids: {missing}")
print(len(PROTOCOL_IDS), len(BIBLIOGRAPHY_IDS))

#%%
collection = get_collection()
plan = {}
for cid in targets:
    response = collection.query.fetch_objects(
        # chunk_id is word-tokenized, so ":9:5" also matches ":5:9"; fetch wide
        # and keep the exact string match below.
        filters=Filter.by_property("chunk_id").equal(cid),
        limit=200,
        return_properties=["chunk_id", "chunk_type", "is_inoculation_protocol"],
    )
    exact = [o for o in response.objects if o.properties.get("chunk_id") == cid]
    if len(exact) != 1:
        raise ValueError(f"{cid}: expected 1 exact match, got {len(exact)}")
    props = exact[0].properties
    before = {"chunk_type": props["chunk_type"],
              "is_inoculation_protocol": props["is_inoculation_protocol"]}
    after = planned_change(by_id[cid])
    # Already applied on an earlier run: nothing to write, nothing to back up.
    if all(before[k] == v for k, v in after.items()):
        continue
    plan[cid] = {"uuid": str(exact[0].uuid), "before": before, "after": after}

for cid, item in plan.items():
    print(cid, item["before"], "->", item["after"])
print(len(plan), "to change")

#%%
# Merge, never overwrite: the earliest "before" is the one a revert needs.
backup = json.loads(BACKUP_PATH.read_text(encoding="utf-8")) if BACKUP_PATH.exists() else {}
for cid, item in plan.items():
    backup.setdefault(cid, item)
BACKUP_PATH.write_text(json.dumps(backup, indent=2), encoding="utf-8")

if DRY_RUN:
    print("dry run, nothing changed")
else:
    for item in plan.values():
        collection.data.update(uuid=item["uuid"], properties=item["after"])

    if not CHUNKS_BACKUP_PATH.exists():
        CHUNKS_BACKUP_PATH.write_text(CHUNKS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    for cid, item in plan.items():
        by_id[cid].update(item["after"])
    CHUNKS_PATH.write_text(json.dumps(chunks, indent=2), encoding="utf-8")

    wrong = {}
    for cid, item in plan.items():
        obj = collection.query.fetch_object_by_id(
            item["uuid"], return_properties=["chunk_type", "is_inoculation_protocol"]
        )
        live = {k: obj.properties[k] for k in item["after"]}
        if live != item["after"]:
            wrong[cid] = live
    both = sum(1 for c in chunks if c["is_inoculation_protocol"] and c["chunk_type"] == "treatment_record")
    print("verified" if not wrong else f"MISMATCH {wrong}", "| invariant 1 violations:", both)

close_client()
