
# OryzaMind 🌾


![Status](https://img.shields.io/badge/status-production-brightgreen)
![CI/CD](https://img.shields.io/badge/CI%2FCD-automated-brightgreen)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

This project is available at [https://oryza.tensorgeek.com/](oryza.tensorgeek.com/)

![Status](https://img.shields.io/badge/status-production-brightgreen)
![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20ONNX%20%7C%20React-blue)

**OryzaMind** is a multimodal agronomic decision-support agent for rice cultivation. It couples two independent
convolutional vision models to a retrieval-augmented generation (RAG) layer built over institutional agronomic
literature, and orchestrates ten function-calling tools through a large language model.

The system's governing design principle is **grounding**: a computer-vision classification is never presented as
text alone. The predicted class becomes a *hard metadata filter* into a curated vector collection, and the language
model is permitted to speak only from the passages that filter returns. Every quantitative recommendation a farmer
might act upon — a fungicide rate, a spray volume — is traceable to a hand-verified source record.

This is an academic project. It sells nothing, and it is not a substitute for a local agricultural extension service.

---

## 1. System Overview

OryzaMind is composed of four cooperating subsystems:

| Subsystem | Role |
|---|---|
| **Vision** | Two ONNX models — a leaf-disease segmenter and a panicle condition classifier — that convert a photograph into a structured finding |
| **Retrieval** | A 2,030-chunk Weaviate Cloud collection of agronomic literature, queried under class and safety filters |
| **Agent** | A Gemini-backed orchestrator that synthesises retrieved passages and elects when to consult external tools |
| **Interface** | A FastAPI service exposing four endpoints, and a React 19 client |

### 1.1 The two vision models are independent

This distinction is architecturally load-bearing and is frequently misread.

| | Leaf detector | Panicle classifier |
|---|---|---|
| Architecture | YOLOv8s-seg (instance segmentation) | EfficientNetB0 (binary classification) |
| Output | 0..N lesion instances, each with a class and mask | One sigmoid: P(unhealthy) |
| Tensor layout | NCHW, letterboxed | **NHWC**, plain bilinear stretch |
| Endpoint | `POST /analyze` | `POST /spike` |
| Retrieval strategy | Hard `disease_name` class filter | Vocabulary fan-out, no class filter |

They share the corpus and the language model, and nothing else. A panicle photograph submitted to the leaf detector
— or the converse — yields a confident answer to a question that was never asked. The frontend therefore presents
two visually distinct, separately-stated upload zones.

The panicle model **names no disease.** It reports a *condition*, and no layer downstream may render that condition
as a diagnosis.

---

## 2. Supported Rice Pathogens

The segmentation model discriminates **six** pathogens of economic significance:

| Class token | Common name | Causal agent |
|---|---|---|
| `Bacterial_Leaf_Blight` | Bacterial leaf blight | *Xanthomonas oryzae* pv. *oryzae* |
| `Brown_Spot` | Brown spot | *Bipolaris oryzae* |
| `Leaf_Blast` | Leaf blast | *Magnaporthe oryzae* |
| `Narrow_Brown` | Narrow brown leaf spot | *Cercospora janseana* |
| `Rice_Tungro` | Rice tungro disease | Tungro virus complex |
| `Sheath_Blight` | Sheath blight | *Rhizoctonia solani* |

**These six strings are an invariant of the system.** They are simultaneously the detector's output classes and the
`disease_name` values stored in the vector database. Any renaming, re-casing or normalisation severs the
vision→retrieval chain silently — retrieval simply returns nothing, and the grounding rule then forbids the agent
from advising at all. Diseases outside this set remain in the corpus under their own source names and are
deliberately never coerced to the nearest class.

A leaf may carry several pathogens simultaneously, so the API returns a **list** of findings. There is no probability
distribution: segmentation confidences do not sum to unity and are never normalised into a fabricated one.

---

## 3. The Knowledge Base

The RAG corpus is built, embedded, and live in Weaviate Cloud.

| Property | Value |
|---|---|
| Collection | `OryzaMindChunk` (`vectorizer: none` — vectors supplied externally) |
| Chunks | **2,030** (370,918 words) |
| Embedding model | `intfloat/e5-large-v2`, **1024-dim** |
| Embedding hardware | Google Colab, NVIDIA T4 |
| Source corpus | 31 English PDFs — 28 IRRI, 1 University of Arkansas, 1 LSU AgCenter, 1 unattributed field guide |

Construction follows a seven-phase ETL pipeline (audit → region detection → extraction → cleaning → chunking →
embedding → ingestion → validation). Phases 0–3 execute locally from `buildRAG/`; phases 4–6 were executed on Colab
and are recorded in  documents the design of the pipeline.
records the decisions, the evidence behind them, and the known limitations.

### 3.1 Two non-negotiable rules for any client of this collection

**Rule 1 — the embedding model is asymmetric.** E5 requires instruction prefixes: chunks were embedded with
`passage: `, and query text **must** be prefixed `query: `. Omitting the prefix degrades retrieval measurably and
raises no error anywhere in the stack. It is a silent failure.

**Rule 2 — treatment-intent queries must filter `is_inoculation_protocol == False`.** Part of the corpus is a
resistance-screening manual describing how to *deliberately infect* rice for trial purposes. Its vocabulary is
near-identical to treatment guidance, and vector similarity alone does not separate the two: an unfiltered query for
"treatment for Bacterial_Leaf_Blight" returned an *Xoc* spray-inoculation procedure at rank 2. The metadata flag
does separate them. Do not delegate this to the language model's judgement — it is the one failure mode in this
system capable of producing actively harmful output.

### 3.2 Corpus coverage, and where it is thin

| Class | Chunks | of which `treatment_record` |
|---|---|---|
| Bacterial_Leaf_Blight | 292 | 10 |
| Leaf_Blast | 220 | 39 |
| Rice_Tungro | 175 | 19 |
| Sheath_Blight | 143 | 28 |
| Brown_Spot | 93 | 5 |
| **Narrow_Brown** | **13** | **1** |

`Narrow_Brown` is the acknowledged weak point. Most of its text is taxonomic rather than managerial, so an
unfiltered query risks retrieving morphology in place of management. Queries against this class must always carry
the class filter. A further 921 chunks hold `disease_name: null` by design, so that general agronomic content
surfaces on semantic similarity rather than requiring a class match.

---

## 4. The Agent and Its Ten Tools

The agent is a Gemini model (`gemini-3.1-flash-lite`) driving a capped tool loop (`MAX_TOOL_ROUNDS = 3`). It binds
**ten tools drawn from six modules** — the mapping is not one-to-one, as `fedearroz_tools.py` defines four.

| # | Tool | Module | Function |
|---|---|---|---|
| 1 | `search_agrochemical_products` | `products_tool.py` | Searches a 30-product catalogue (Invesa, Precisagro) by query and category |
| 2 | `get_crop_weather` | `weather_tool.py` | Live meteorological conditions via Open-Meteo geocoding + forecast |
| 3 | `recommend_rice_fertilizer` | `rice_fertilizer.py` | Fertilizer *type* from soil moisture, electrical conductivity and growth phase |
| 4 | `recommend_crop` | `recommend_crop.py` | Rice suitability score for a soil profile, plus rotation alternatives |
| 5 | `check_plant_health_status` | `check_plant_health_status.py` | Stress status — healthy / moderate / high — from sensor readings |
| 6 | `get_rice_price` | `rice_price_tool.py` | FAOSTAT producer prices, USD/tonne, annual, 43 countries |
| 7 | `get_colombia_rice_price` | `fedearroz_tools.py` | FEDEARROZ paddy prices, COP/tonne, monthly |
| 8 | `get_rice_production_costs` | `fedearroz_tools.py` | Production cost by *rubro*, COP/hectare, irrigated |
| 9 | `get_rice_planted_area` | `fedearroz_tools.py` | Planted area by zone, with a zone→department mapping |
| 10 | `get_rice_consumption` | `fedearroz_tools.py` | Per-capita consumption, kg/person/year, urban and rural |

### 4.1 Two files in `tools/` are deliberately *not* tools

`vision_tool.py` is intentionally empty and `rag_tool.py` is unused. Vision and corpus retrieval are **forced chain
steps, not elective tool calls.** The photograph is classified before the language model is invoked, and literature
retrieval always runs. A model empowered to *choose* to run vision could equally choose *not* to, and the grounding
rule would collapse at precisely the moment it matters. This is a structural guarantee, not a prompt instruction.

### 4.2 Governing constraints on tool behaviour

These are enforced in code, not merely requested in the prompt.

- **Consent gating.** Tools are bound only when the conversation history already contains an assistant turn.
  A user's first message therefore *cannot* trigger a lookup. After recommending a chemical, the agent offers a
  product search and stops; the tool runs only on assent.
- **No prices in agronomic advice.** The product catalogue stores prices; the response schema omits them entirely.
  *We inform, we do not sell.* Market prices are a separate tool family and never justify a treatment decision.
- **No rate may originate from model memory.** Not approximate, not typical, not a range. Active-ingredient
  *classes* may be named; the numeric rate defers to the product label or the extension service. The fertilizer,
  plant-health and cost tools all inherit this rule.
- **Chemical and cultural, always both.** IRRI material leans cultural; Arkansas and LSU carry fungicide programmes.
  The agent is instructed to present both and never to withhold chemical options.
- **The two price sources are never merged.** FAOSTAT and FEDEARROZ differ in unit, cadence and authority. A test
  asserts they remain distinct.

### 4.3 The tabular models

Three scikit-learn artefacts back tools 3, 4 and 5. Their limitations are stated in their own output rather than
concealed:

| Artefact | Estimator | Notes |
|---|---|---|
| `decision_tree_fertilizer.joblib` | Decision tree, depth 4 | Only three features carry signal; every leaf is pure, so confidence is always 1.0 and is therefore never reported |
| `crop_recomendation_model.pkl` | Random forest, 50 trees | The source notebook's test accuracy of 1.0 is leakage; the tool quotes the 0.995 cross-validated score |
| `plant_health_model.joblib` | Random forest, 100 trees | Class indices are **alphabetical, not ordinal** — 1 is High Stress and 2 is Moderate. They must never be compared or sorted |

Out-of-range inputs are refused rather than predicted, because tree ensembles extrapolate silently.

---

## 5. Request Pipelines

### 5.1 Leaf pathway — `POST /analyze`

```
Photograph
    │
    ▼
YOLOv8s-seg (ONNX Runtime, CPU)  ──►  letterbox ► inference ► NMS/IoU ► mask crop
    │
    ▼
Findings: [{class, confidence, mask, severity}, ...]
    │
    ▼
Per-disease retrieval  ──►  Weaviate: disease_name == class
                            AND is_inoculation_protocol == False
    │                       query embedded with "query: " prefix
    ▼
Merged context (dedup by chunk_id)
    │
    ▼
Gemini synthesis  ──►  grounded recommendations + citations
    │
    ▼
FastAPI JSON  ──►  React client
```

**Co-infection is handled by fanning out, not by choosing.** Filtering on a single primary disease returned nothing
for the others, and the grounding rule then silently suppressed advice for them — producing a response that looked
complete while covering one pathogen. Retrieval now issues one pass per detected class and merges by `chunk_id`.

**Severity** is lesion pixels over total image pixels, banded `<3% LOW / 3–10% MODERATE / 10–18% HIGH / >18%
CRITICAL`. The scale is calibrated for field photography, in which the plant occupies a fraction of the frame.

### 5.2 Panicle pathway — `POST /spike`

The classifier yields no class token, so there is nothing to filter on. Retrieval instead **fans out across the
panicle vocabulary** — neck blast, grain discolouration, false and kernel smut, sheath rot, bacterial panicle
blight, fungicide timing, and nitrogen/water/cultivar management — merging by `chunk_id` and capping context at
seven chunks. A single blended query does not work: "unhealthy panicle" returns neck blast every time, because it
dominates the corpus, and the minor causes vanish entirely.

`disease_name` remains `None` throughout, deliberately: the corpus labels panicle diseases under their own source
names, which are correctly *not* among the six canonical classes. The inoculation filter nonetheless stays active,
because the screening manual's panicle inoculation procedures rank well on exactly this vocabulary.

Predictions within a margin of the decision threshold are flagged `uncertain` rather than presented as verdicts. The
batch verdict is worst-case: one unhealthy panicle condemns the sample.

**The grounded fallback.** When retrieval returns nothing, and only then, the model may answer from its own
knowledge — the single place in the system where that is permitted. The answer is fenced: it must open by declaring
that it is not drawn from the OryzaMind corpus, it may cite no source, and **no dosage, rate, concentration or
volume per area may come from memory.** The response carries a `grounded: bool` that the interface surfaces.

---

## 6. API Surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/analyze` | Leaf disease segmentation, severity, and grounded management plan |
| `POST` | `/spike` | Panicle condition verdict and management plan |
| `POST` | `/chat` | Stateless follow-up dialogue; accepts `history` and `analysis` in the body |
| `GET` | `/health` | Liveness, plus per-component readiness |

`/analyze` and `/spike` share a multipart contract (`image_0..image_N`, maximum 3) and a common form reader.

`/health` always returns 200 and reports degradation in its payload. It exposes `model_loaded`, `weaviate_ready`,
`spike_model_loaded`, `fertilizer_model_loaded`, `crop_model_loaded` and `plant_health_model_loaded`. Only the leaf
model and Weaviate gate the aggregate `status` — the remaining models are additive capabilities, and the primary
pipeline serves correctly without them.

`/chat` is **stateless by design**: it accepts the conversation history and the prior analysis in each request and
stores nothing. Persistence is currently client-side, in `localStorage`.

---

## 7. Technology Stack

**Backend** — Python 3.13 · FastAPI · Pydantic v2 · ONNX Runtime (CPU) · Weaviate Python client v4 ·
sentence-transformers · scikit-learn · LangChain 1.x with `langchain-google-genai` · Pillow · OpenCV (headless)

**Frontend** — React 19 · TypeScript 5.9 · Vite 7 · Tailwind CSS 4 · Zustand (with `persist`) · Axios ·
react-markdown

### 7.1 Dependency pins that encode hard-won constraints

Several pins exist for reasons that are non-obvious and expensive to rediscover:

- **`weaviate-client>=4.22`** — a safety floor. Earlier releases serialise a boolean filter into protobuf's
  `value_int` (because `isinstance(False, int)` is `True`), which protobuf 7 rejects. That breaks the
  `is_inoculation_protocol` filter outright.
- **`langchain-google-genai>=4.4`** — Gemini 3 returns a `thought_signature` with each function call that must be
  echoed on the following turn. Earlier clients drop it, and the turn that feeds a tool result back fails with
  `400 Function call is missing a thought_signature`.
- **`opencv-python-headless==4.10.0.84`** — 4.9 is built against NumPy 1.x and cannot import on Python 3.13.
- **`pillow>=10.4`** — required for panicle preprocessing, and not interchangeable with OpenCV (see §7.2).

### 7.2 Two silent preprocessing invariants

Neither raises an error when violated; both were established by measurement across the full test set.

1. **The panicle model receives raw `[0,255]` pixels.** ImageNet normalisation is *baked into the ONNX graph*.
   Applying it again in Python collapses every image to ≈0.90 and the model ceases to discriminate at all.
2. **Resizing uses PIL bilinear, not OpenCV.** PIL antialiases on downscale; `cv2.INTER_LINEAR` does not. On a
   2940-px field photograph the difference *inverts the predicted class* (0.904 → 0.157). With PIL, the backend
   reproduces the reference implementation to a maximum delta of 0.00000 across all test images.

Model loaders assert the expected input and output shapes and fail loudly, so that a future retrain cannot silently
reinterpret a sigmoid head.

---

## 8. Installation

### Prerequisites

- Python 3.13
- Node.js 18+
- A Weaviate Cloud cluster containing the `OryzaMindChunk` collection
- A Google AI Studio API key

### Backend

Two virtual environments exist and **must not be mixed**: `.venv/` for the ETL pipeline, `oryza/` for the
application. The ETL environment deliberately excludes Torch and sentence-transformers.

```bash
git clone https://github.com/BeauBryanDev/oryza-mind
cd oryza_mind

python3 -m venv oryza
# CPU wheel FIRST — otherwise the resolver pulls ~2 GB of CUDA to embed one short query
oryza/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
oryza/bin/pip install -r requirements.txt

oryza/bin/uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment

Create `.env` at the repository root:

```env
GEMINI_API_KEY=your_google_ai_studio_key
WEAVIATE_URL=your_weaviate_cluster_url
WEAVIATE_API_KEY=your_weaviate_api_key
EMBEDDING_MODEL=e5-large-v2
WEATHER_API_KEY=your_weather_api_key
```

Credentials belong in environment variables exclusively. They are never committed, and never inlined in a notebook
cell.

---

## 9. Testing

```bash
oryza/bin/python -m pytest            # full suite, ~9 s
oryza/bin/python -m pytest -m "not slow"   # what CI runs
```

**109 tests; 108 pass and 1 is a deliberate `xfail`.** The suite is **offline by construction**: `conftest.py`
installs dummy credentials before `app.core.config` is imported, so no test reaches Gemini or Weaviate. The three
network entry points are `lru_cache`d module-level functions, which makes monkeypatching them straightforward. *Do
not add real credentials to make a test pass — fake the seam instead.*

Coverage spans IoU and NMS arithmetic, letterbox round-tripping, severity banding, both panicle preprocessing
invariants, both retrieval safety rules, the no-rate guarantees, out-of-range refusal, and agent tool binding.

Tests requiring a real model artefact are marked `slow` and skip when `ml/` is absent. They are local gates: CI runs
`-m "not slow"` and therefore deselects them.

The single `xfail` is a **tripwire rather than a comment**: overall severity currently divides by total pixels
across all submitted images, so adding a healthy photograph dilutes the result. The test flips to passing on the day
that defect is repaired.

---

## 10. Known Limitations

Stated plainly, in keeping with the project's MVP posture.

**Classification accuracy.** On ten labelled photographs the detector achieved 6/10 primary-class accuracy, with no
`Narrow_Brown` examples present — a smoke signal, not a metric. Leaf blast was misread as brown spot in both
instances. Critically, **threshold tuning cannot repair this**: the raw pre-threshold activation for the true class
on the failures is 0.001–0.02, not a near-miss beneath a cutoff. This requires training data, not a parameter. The
consequence is architectural: a confidently wrong class becomes the retrieval filter, and every safety rule holds
while the pipeline answers the wrong question. No downstream layer can detect this.

**Incomplete inoculation metadata.** The `is_inoculation_protocol` flag was applied only to the 2025 screening
manual. Roughly 138 chunks in the IRRI chapter PDFs contain procedural inoculation language and remain unflagged.
The remedy is metadata-only and requires no re-embedding.

**Severity dilution.** Overall severity is computed across all submitted images jointly; the recommended fix is a
per-image maximum.

**No server-side persistence.** State lives in browser `localStorage`. MongoDB Atlas persistence is the next
milestone.

**Panicle evaluation.** Unlike the leaf model, no labelled accuracy figures exist yet — only qualitative
verification against unlabelled field photographs.

---

## 11. Repository Layout

```
app/          FastAPI backend
  agent/      orchestrator, panicle agent, prompts, state
  core/       configuration, logging, model loaders
  rag/        vector store client, retriever, prompt templates
  routers/    endpoint definitions and the shared multipart reader
  schemas/    Pydantic contracts (camelCase at the API boundary)
  services/   vision, analysis, chat and panicle orchestration
  tools/      the ten bound tools (and two files deliberately left inert)
  utils/      vision preprocessing and postprocessing
buildRAG/     phases 0–3 of the ETL pipeline
RAG/          pipeline outputs and static tool datasets
ml/           exported ONNX and scikit-learn artefacts
frontend/     React 19 + Vite + Tailwind client
scripts/      corpus scrapers, dataset converters, model retraining
tests/        the offline suite
```
---

## 12. Contributing

Contributions extending the corpus, the evaluation set, or model metrics are welcome — the `Narrow_Brown` coverage
gap and the absence of a labelled panicle evaluation set are the most valuable open targets. Note that adding corpus
material requires re-embedding and re-ingesting all chunks.

Please accompany a pull request with the technical rationale, and with the measurement supporting it where a claim
is empirical.

## License

MIT.
