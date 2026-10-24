#%%
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.agent import get_llm
from app.core.config import CLASS_NAMES
from app.rag.retriever import RetrievalIntent, retrieve
from app.rag.vectorstore import close_client, embed_query

GOLDEN_PATH = EVAL_DIR / "golden_farmer_50.jsonl"
OUT_PATH = EVAL_DIR / "translate_eval_results.json"
K_MAX = 10
KS = (1, 3, 5)
CONTEXT_K = 5

COMMON_NAMES = {
    "Bacterial_Leaf_Blight": "bacterial leaf blight",
    "Brown_Spot": "brown spot",
    "Leaf_Blast": "rice blast",
    "Narrow_Brown": "narrow brown leaf spot",
    "Rice_Tungro": "rice tungro",
    "Sheath_Blight": "sheath blight",
}

# No photo: vision has said nothing, so the query may only carry what the
# farmer wrote. Local names the farmer used may be standardised, never added.
LITERAL_PROMPT = (
    "Translate a rice farmer's message into one English search query for a library "
    "of English rice literature. Translate literally and faithfully. Describe symptoms "
    "exactly as the farmer describes them. If the farmer names a disease, pest or weed, "
    "give its standard English or scientific name (anublo de la vaina = sheath blight, "
    "piricularia = rice blast, sogata = Tagosodes orizicolus, liendre de puerco = "
    "Echinochloa colona). NEVER name a disease, virus, bacterium or pest the farmer did "
    "not name, even if the symptoms suggest one. If the message is already English, "
    "return it unchanged. Do not answer. Output only the query, one line."
)

# Photo: the disease comes from vision, so the rewrite is anchored to it.
PHOTO_PROMPT = (
    "A vision model diagnosed the farmer's rice photo as: {disease}. Rewrite the "
    "farmer's message into one English search query about {disease}. Use that disease "
    "name and no other disease. Keep the farmer's actual question (symptoms, control, "
    "timing, products, fertilizer). Do not answer. Output only the query, one line."
)

# English disease terms and the Spanish or English words that license them. A
# term in the output with none of its aliases in the input is an injection.
DISEASE_ALIASES = {
    r"blast": r"piricularia|pyricularia|quemaz|añublo del cuello|cuello|blast",
    r"sheath blight": r"vaina|rizoctonia|rhizoctonia|sheath",
    r"bacterial (leaf )?blight|xanthomonas": r"bacteri|xanthomonas|tizón bacteriano|blight",
    r"brown spot": r"mancha parda|mancha café|brown spot",
    r"narrow brown|cercospora": r"cercospora|lineal|raya café angosta|narrow",
    r"tungro": r"tungro",
    r"grassy stunt|ragged stunt|dwarf virus": r"grassy|ragged|dwarf",
    r"hoja blanca|rhbv": r"hoja blanca",
    r"smut|ustilaginoidea|tilletia": r"carbón|smut",
    r"sheath rot|sarocladium": r"pudre|sheath rot",
    r"panicle blight|burkholderia": r"panicle blight",
    r"\bwilt\b|kresek": r"wilt|kresek",
}


def injected(source, english):
    src, out = source.lower(), english.lower()
    return [term for term, aliases in DISEASE_ALIASES.items()
            if re.search(term, out) and not re.search(aliases, src)]


#%%
with GOLDEN_PATH.open(encoding="utf-8") as f:
    golden = [json.loads(line) for line in f if line.strip()]
print(len(golden))

llm = get_llm()
embed_query("warmup")


#%%
def rewrite(system, question):
    start = time.perf_counter()
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=question)])
    return response.text().strip().splitlines()[0], time.perf_counter() - start


def search(query, disease):
    t0 = time.perf_counter()
    vec = embed_query(query)
    t1 = time.perf_counter()
    res = retrieve(query, disease_name=disease, intent=RetrievalIntent.TREATMENT,
                   top_k=K_MAX, query_vector=vec)
    return res.chunks, t1 - t0, time.perf_counter() - t1


def rank_of(relevant, chunks):
    return next((i for i, c in enumerate(chunks, start=1) if c.chunk_id in relevant), None)


results = []
for row in golden:
    relevant = set(row["relevant_chunk_ids"])
    disease = row["chunk_disease_label"] if row["chunk_disease_label"] in CLASS_NAMES else None
    entry = {"id": row["id"], "group": row["group"], "question": row["question"]}

    chunks, t_embed, t_ret = search(row["question"], None)
    entry.update(raw_chat_rank=rank_of(relevant, chunks), raw_t=t_embed + t_ret)

    literal, t_lit = rewrite(LITERAL_PROMPT, row["question"])
    chunks, t_embed, t_ret = search(literal, None)
    entry.update(literal=literal, literal_chat_rank=rank_of(relevant, chunks),
                 t_literal=t_lit, literal_t=t_lit + t_embed + t_ret,
                 literal_injected=injected(row["question"], literal),
                 literal_top3=[c.chunk_id for c in chunks[:3]])

    if disease:
        chunks, _, _ = search(row["question"], disease)
        entry["raw_photo_rank"] = rank_of(relevant, chunks)
        photo, t_photo = rewrite(PHOTO_PROMPT.format(disease=COMMON_NAMES[disease]), row["question"])
        chunks, t_embed, t_ret = search(photo, disease)
        entry.update(photo=photo, photo_rank=rank_of(relevant, chunks), t_photo=t_photo,
                     photo_t=t_photo + t_embed + t_ret)
    results.append(entry)
    flag = f" INJECTED {entry['literal_injected']}" if entry["literal_injected"] else ""
    print(f"{row['id']} chat {entry['raw_chat_rank']}->{entry['literal_chat_rank']} "
          f"photo {entry.get('raw_photo_rank', '-')}->{entry.get('photo_rank', '-')} | {literal}{flag}")


#%%
def summarize(ranks):
    n = len(ranks)
    out = {"n": n}
    for k in KS:
        out[f"hit@{k}"] = round(sum(1 for r in ranks if r and r <= k) / n, 3) if n else None
    out["mrr"] = round(sum(1 / r for r in ranks if r) / n, 3) if n else None
    return out


def latency(values):
    values = sorted(values)
    return {"p50": round(statistics.median(values), 3),
            "p95": round(values[min(len(values) - 1, int(0.95 * len(values)))], 3),
            "max": round(values[-1], 3)}


scored = [r for r in results if r["group"] != "safety_es"]
photo = [r for r in scored if "photo_rank" in r]
groups = sorted({r["group"] for r in scored})

summary = {
    "chat": {
        "all": {"raw": summarize([r["raw_chat_rank"] for r in scored]),
                "literal": summarize([r["literal_chat_rank"] for r in scored])},
        **{g: {"raw": summarize([r["raw_chat_rank"] for r in scored if r["group"] == g]),
               "literal": summarize([r["literal_chat_rank"] for r in scored if r["group"] == g])}
           for g in groups},
    },
    "photo": {
        "all": {"raw": summarize([r["raw_photo_rank"] for r in photo]),
                "rewritten": summarize([r["photo_rank"] for r in photo])},
        **{g: {"raw": summarize([r["raw_photo_rank"] for r in photo if r["group"] == g]),
               "rewritten": summarize([r["photo_rank"] for r in photo if r["group"] == g])}
           for g in sorted({r["group"] for r in photo})},
    },
    "literal_injections": {r["id"]: r["literal_injected"] for r in results if r["literal_injected"]},
    "latency_s": {
        "literal_call": latency([r["t_literal"] for r in results]),
        "photo_call": latency([r["t_photo"] for r in photo]),
        "raw_retrieval": latency([r["raw_t"] for r in results]),
        "literal_retrieval_total": latency([r["literal_t"] for r in results]),
        "photo_retrieval_total": latency([r["photo_t"] for r in photo]),
    },
}
print(json.dumps(summary, indent=2, ensure_ascii=False))

print("safety probes, literal, top 3")
for r in results:
    if r["group"] == "safety_es":
        print(" ", r["id"], "|", r["literal"], "|", r["literal_top3"])

#%%
with OUT_PATH.open("w", encoding="utf-8") as f:
    json.dump({"prompts": {"literal": LITERAL_PROMPT, "photo": PHOTO_PROMPT},
               "summary": summary, "results": results}, f, indent=2, ensure_ascii=False)
close_client()
