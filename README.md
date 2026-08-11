# OryzaMind 🌾 

OryzaMind is an advanced, multimodal AI Agent and RAG system designed to revolutionize rice crop diagnostics. By combining edge computer vision (**YOLOv11**) with the contextual reasoning of **Gemini 3.5**, OryzaMind analyzes images of infected rice leaves, segments visual damage, and provides bilingual (English/Spanish), expert-level agronomic treatments in real-time.

---

##  Key Features

*   **Multimodal AI Agent:** Powered by Gemini 3.5 via Google AI Studio API for strategic agronomic consulting.
*   **Edge Computer Vision:** Custom-trained **YOLOv11small-seg** model that detects and segments lesion geometry on leaves.
*   **Agronomic RAG — built and live:** 2,030 vector chunks in Weaviate Cloud, retrieved from authoritative institutional sources (IRRI, University of Arkansas, LSU AgCenter).
*   **Dynamic Response Structure:** Instant mapping from vision classification directly into targeted cultural, biological, and chemical treatment guidelines.
*   **Bilingual Responses:** the agent answers in English or Spanish. *(The source corpus itself is entirely English — the bilingual layer is at response time.)*

---

## 📚 Knowledge Base — COMPLETE

The RAG knowledge base is **finished and deployed to Weaviate Cloud**.

| | |
|---|---|
| **Status** | ✅ Complete — ingested and validated |
| **Chunks** | **2,030** (370,918 words) |
| **Collection** | `OryzaMindChunk` (Weaviate Cloud, `vectorizer: none`) |
| **Embedding model** | `intfloat/e5-large-v2` — 1024 dimensions |
| **Embedding hardware** | Google Colab, NVIDIA T4 GPU |
| **Source corpus** | 31 English PDFs — 28 IRRI, 1 University of Arkansas, 1 LSU AgCenter, 1 unattributed field guide |

Built by a six-phase ETL pipeline (audit → extraction → cleaning → chunking → embedding → ingestion → validation). The phase scripts live at the repository root; `RAG_BUILD_SPEC.md` documents the design and `CLAUDE.md` records the decisions and known limitations.

**Two notes for anyone querying this collection:**

1. `intfloat/e5-large-v2` is **asymmetric** — search text must be prefixed with `query: ` (chunks were embedded with `passage: `). Omitting the prefix degrades retrieval silently, with no error raised.
2. On treatment-intent queries, filter `is_inoculation_protocol == False`. Part of the corpus is a screening manual describing how to *deliberately infect* rice for resistance trials; that vocabulary is near-identical to treatment guidance, so vector similarity alone does not separate them. The metadata flag does.

---

## 🦠 Supported Rice Diseases

OryzaMind is purpose-built to recognize and prescribe treatments for **6 major rice pathogens**:

1.  **Bacterial Leaf Blight** (*Xanthomonas oryzae pv. oryzae*)
2.  **Brown Spot** (*Bipolaris oryzae*)
3.  **Leaf Blast** (*Magnaporthe oryzae*)
4.  **Narrow Brown Leaf Spot** (*Cercospora janseana*)
5.  **Rice Tungro Disease** (*Tungro Virus Complex*)
6.  **Sheath Blight** (*Rhizoctonia solani*)

---

##  Tech Stack

### Backend & AI Core
*   **Language:** Python 3.11+
*   **API Framework:** FastAPI (Asynchronous execution, robust performance)
*   **Vision Models:** YOLOv11small-seg + OpenCV (Image preprocessing & instance segmentation)
*   **LLM Engine:** Gemini 3.5 API (Google AI Studio)
*   **Vector Database:** Weaviate Cloud (metadata filtering over externally supplied vectors)
*   **Embeddings:** `intfloat/e5-large-v2` (1024-dim, sentence-transformers)

### Frontend
*   **Language:** TypeScript
*   **Framework:** React.js
*   **Styling:** Tailwind CSS

---

##   System Architecture

1.  **Image Capture:** The user uploads a photo of a rice leaf via the React interface.
2.  **Vision Inference:** The FastAPI backend passes the frame through **YOLOv11small-seg**. The model isolates the lesion and yields a class tag (e.g., `Sheath_Blight`).
3.  **Contextual Retrieval (RAG):** The tag is used as a hard metadata filter on `disease_name` in the **Weaviate** `OryzaMindChunk` collection. The query is embedded with `intfloat/e5-large-v2` (prefixed `query: `) and matched against the 2,030 stored chunks.
4.  **Agent Synthesis:** **Gemini 3.5** digests the raw clinical chunks, aligns them with the user's querying language (EN/ES), and outputs a highly authoritative, structured remedy profile.

---

##  Installation & Setup

> **Build status:** the RAG knowledge base is complete and live. The `backend/` and `frontend/` applications described below are the intended architecture and are **not yet implemented** — the setup steps are the target layout, not runnable today.

### Prerequisites
*   Python 3.11+
*   Node.js v18+
*   Weaviate Instance (Cloud or Local Docker)
*   Google AI Studio API Key

### Backend Setup
```bash
# Clone the repository
git clone https://github.com
cd oryzamind/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload
```

### Frontend Setup
```bash
cd ../frontend

# Install packages
npm install

# Start local server
npm run dev
```

---

##  Environment Variables

Create a `.env` file in your backend folder:
```env
GEMINI_API_KEY=your_google_gemini_api_key
WEAVIATE_URL=your_weaviate_cluster_url
WEAVIATE_API_KEY=your_weaviate_api_key
```
---

##   Contributing
Contributions to expand OryzaMind's model metrics or knowledge bases are welcome. Please open an issue or submit a pull request with technical documentation.

##  License
This project is licensed under the MIT License.

