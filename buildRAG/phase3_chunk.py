

import json
import re
from collections import Counter
from pathlib import Path
"""
Phase 3 — chunking, per spec §7.1, emitting the §8 metadata schema.

Sections are already the semantic unit (Phase 1 recovered the IRRI numbered
structure), so this stage bounds their length and attaches metadata. Median
section is 249 words, so most pass through as a single chunk; only long
sections are sub-split, on sentence boundaries with overlap.

The two judgement calls that matter:

`disease_name` — the CV->RAG chain filters on it, so a wrong value is worse
than none. A canonical class is assigned only when it dominates the chunk
(>=60% of disease mentions, >=2 mentions), with parent-section context
inherited first so a sub-split "Disease management" fragment still knows
which disease it belongs to. Ambiguous chunks get null and rely on semantic
similarity instead.

`is_inoculation_protocol` — the 2025 IRRI Manual explains how to deliberately
INFECT rice. Such chunks are flagged and can never be typed as
treatment_record; serving one as advice would be actively harmful.

Output: chunks.json
"""
ROOT = Path(__file__).parent
NARRATIVE = ROOT / "narrative_clean.json"
ARKANSAS = ROOT / "treatment_records_arkansas.json"
MANIFEST = json.loads((ROOT / "source_manifest.json").read_text())
OUT = ROOT / "chunks.json"

TARGET_WORDS = 280      # ~365 tokens for e5-large-v2's 512 window
OVERLAP_WORDS = 60
MIN_WORDS = 40

# The IRRI chapters refer to diseases by short codes far more often than by
# name ("BSp can be managed by chemical control..."), so the codes must be
# recognised or whole management sections go unattributed. Codes are guarded
# against their common false friends: "BB Table 4" is a table reference, and
# "RT-PCR" is a laboratory method, not rice tungro.
CANONICAL = {
    "Bacterial_Leaf_Blight": r"bacterial (leaf )?blight|\bBLB\b|Xanthomonas oryzae pv\.? oryzae|"
                             r"\bXoo\b|\bBB\b(?!\s+(Table|Figure|Fig))",
    "Brown_Spot": r"brown spot|Bipolaris oryzae|Cochliobolus miyabeanus|"
                  r"Helminthosporium oryzae|\bBSp\b",
    "Leaf_Blast": r"\bleaf blast\b|\bblast\b|Magnaporthe|Pyricularia|"
                  r"\bRBl\b(?!\s+(Table|Figure|Fig))",
    "Narrow_Brown": r"narrow brown( leaf)? spot|\bNBLs?\b|Cercospora janseana|Sphaerulina oryzina",
    "Rice_Tungro": r"tungro|\bRTBV\b|\bRTSV\b|\bRTV\b|\bRTD\b",
    "Sheath_Blight": r"sheath blight|Rhizoctonia solani|\bShB\b",
}
# Diseases the corpus covers that are NOT vision classes — kept under their
# own names, never force-fitted onto a canonical string.
NON_CANONICAL = {
    "Kernel Smut": r"kernel smut",
    "False Smut": r"false smut",
    "Stem Rot": r"stem rot|Sclerotium oryzae",
    "White Leaf Streak": r"white leaf streak",
    "Bacterial Leaf Streak": r"bacterial leaf streak|\bBLS\b",
    "Grain Discoloration": r"grain discolo",
    "Rice Black-Streaked Dwarf": r"black-?streaked dwarf|\bRBSDV?\b|\bSRBSDV?\b",
}

# A treatment_record needs the SECTION to be about management, or the text to
# carry a concrete actionable recommendation. Matching the bare word "control"
# anywhere in the body typed ordinary prose ("biological control of the
# pathogen is poorly understood") as treatment guidance.
MANAGEMENT_HEADING_RE = re.compile(
    r"\bmanagement\b|\bcontrol\b|cultural practice|fungicid|chemical|"
    r"resistant variet|varietal resistance|seed treatment|\btreatment\b", re.I)
ACTIONABLE_RE = re.compile(
    # chemical
    r"\bfungicid\w*\b|\bapply\b|\bapplication rate\b|\bspray\b|\bseed treatment\b|"
    r"\bfl oz\b|\bkg/ha\b|\bg/ha\b|\bl/ha\b|\brecommended\b|"
    # varietal
    r"\bresistant cultivars?\b|\bresistant variet\w+\b|\bsusceptible cultivars?\b|"
    # cultural practices — the corpus gives much of its advice this way
    r"\bavoid\b|\bmaintain\b|\bplant early\b|\brotat\w+\b|\bsanitation\b|"
    r"\bdestroy\b|\bremove\b|\bdrain\b|\bflood depth\b|\bfertility program\b", re.I)
# The Arkansas handbook marks management with an inline bullet header rather
# than a heading the font-size detector can see.
MANAGEMENT_MARKER_RE = re.compile(
    r"\bManagement\b\s*[••\-]|\bControl measures?\b|\bDisease management\b", re.I)
INOCULATION_RE = re.compile(
    r"inoculat|spore suspension|inoculum|clipping method|scissor.?dip|"
    r"spray.{0,20}suspension|conidial suspension", re.I)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def dominant_disease(text, min_share=0.6, min_hits=2):
    """Return (name, is_canonical) when one disease clearly dominates."""
    counts = {c: len(re.findall(p, text, re.I)) for c, p in CANONICAL.items()}
    counts = {k: v for k, v in counts.items() if v}
    nc = {c: len(re.findall(p, text, re.I)) for c, p in NON_CANONICAL.items()}
    nc = {k: v for k, v in nc.items() if v}

    total = sum(counts.values()) + sum(nc.values())
    if not total:
        return None, False

    if counts:
        top, n = max(counts.items(), key=lambda kv: kv[1])
        if n >= min_hits and n / total >= min_share:
            return top, True
    if nc:
        top, n = max(nc.items(), key=lambda kv: kv[1])
        if n >= min_hits and n / total >= min_share:
            return top, False
    return None, False


def split_section(text):
    """Sentence-boundary splitting with overlap; never mid-sentence."""
    words = text.split()
    if len(words) <= TARGET_WORDS:
        return [text]

    # A single sentence longer than the target (run-on prose does occur here)
    # is hard-split at word boundaries, else it would blow past the window.
    sentences = []
    for s in SENTENCE_RE.split(text):
        sw = s.split()
        while len(sw) > TARGET_WORDS:
            sentences.append(" ".join(sw[:TARGET_WORDS]))
            sw = sw[TARGET_WORDS:]
        if sw:
            sentences.append(" ".join(sw))

    chunks, current = [], []
    for sentence in sentences:
        # Close the chunk BEFORE overflowing it. Appending first and checking
        # after let a long sentence land inside an already-full chunk,
        # producing 523-word chunks against a 280-word target.
        if current and len((" ".join(current) + " " + sentence).split()) > TARGET_WORDS:
            chunks.append(" ".join(current))
            # Take only trailing sentences that FIT the overlap budget. Taking
            # until the budget is exceeded could carry back a target-length
            # sentence, so overlap + next sentence overshot to 434 words.
            back, count = [], 0
            for s in reversed(current):
                n = len(s.split())
                if count + n > OVERLAP_WORDS:
                    break
                back.insert(0, s)
                count += n
            current = back
        current.append(sentence)
    tail = " ".join(current).strip()
    if tail:
        # Never emit a runt; fold it into the previous chunk instead.
        if chunks and len(tail.split()) < MIN_WORDS:
            chunks[-1] = chunks[-1] + " " + tail
        else:
            chunks.append(tail)
    return chunks


def doc_meta(record):
    entry = MANIFEST.get("overrides", {}).get(record["filename"], {})
    parent_key = entry.get("parent_work", MANIFEST.get("default_parent_work"))
    if record["filename"] in MANIFEST.get("overrides", {}) and "parent_work" not in entry:
        parent_key = MANIFEST.get("default_parent_work")
    parent = MANIFEST["parent_works"].get(parent_key or "", {})
    return {
        "source_document": record["filename"],
        "document_title": record["document_title"],
        "organization": record["organization"] or "unknown",
        "source_url": entry.get("source_url") or parent.get("source_url"),
        "document_type": record["document_type"],
        "ocr_derived": "Paper Capture" in (entry.get("warning") or ""),
    }


def build_narrative_chunks():
    docs = json.loads(NARRATIVE.read_text())
    chunks = []
    for r in docs:
        meta = doc_meta(r)
        slug = re.sub(r"[^a-z0-9]+", "-", r["filename"].lower())[:40].strip("-")
        screening = meta["document_type"] == "screening_manual"

        for si, section in enumerate(r["sections"]):
            heading = section["heading"]
            # Parent-section context first: a sub-split "Disease management"
            # fragment must inherit its section's disease.
            parent_disease, parent_canon = dominant_disease(
                (heading or "") + " " + section["text"], min_share=0.5, min_hits=1)

            parts = split_section(section["text"])
            for ci, part in enumerate(parts):
                if len(part.split()) < MIN_WORDS and len(parts) == 1:
                    continue
                disease, canon = dominant_disease(part)
                if disease is None and parent_disease:
                    disease, canon = parent_disease, parent_canon

                inoculation = bool(screening and INOCULATION_RE.search(part))
                # Management section OR concrete actionable advice — the
                # heading alone is not enough ("9. Future perspectives"
                # mentions control without recommending anything).
                heading_mgmt = bool(heading and MANAGEMENT_HEADING_RE.search(heading))
                marker = bool(MANAGEMENT_MARKER_RE.search(part))
                n_actionable = len(ACTIONABLE_RE.findall(part))
                # Signposted as management (heading or inline marker) needs
                # only one concrete recommendation; unsignposted prose needs
                # several, so ordinary discussion isn't typed as advice.
                is_mgmt = ((heading_mgmt or marker) and n_actionable >= 1) or n_actionable >= 3
                ctype = ("treatment_record"
                         if is_mgmt and not inoculation else "narrative")

                chunks.append({
                    "chunk_id": f"{slug}:{si}:{ci}",
                    "text": part,
                    **meta,
                    "chunk_type": ctype,
                    "disease_name": disease,
                    "disease_name_is_canonical": canon,
                    "source_disease_label": None,
                    "section": heading,
                    "page_start": section["page_start"],
                    "page_end": section["page_end"],
                    "word_count": len(part.split()),
                    "chunk_index": ci,
                    "chunk_total": len(parts),
                    "is_inoculation_protocol": inoculation,
                    "symptom": None,
                    "recommended_treatment": None,
                    "active_ingredient": None,
                    "dosage": None,
                    "crop_stage": None,
                })

        for fi, cap in enumerate(r["figure_captions"]):
            disease, canon = dominant_disease(cap["text"], min_share=0.5, min_hits=1)
            chunks.append({
                "chunk_id": f"{slug}:fig:{fi}",
                "text": cap["text"],
                **meta,
                "chunk_type": "figure_caption",
                "disease_name": disease,
                "disease_name_is_canonical": canon,
                "source_disease_label": None,
                "section": None,
                "page_start": cap["page"], "page_end": cap["page"],
                "word_count": len(cap["text"].split()),
                "chunk_index": 0, "chunk_total": 1,
                "is_inoculation_protocol": False,
                "symptom": None, "recommended_treatment": None,
                "active_ingredient": None, "dosage": None, "crop_stage": None,
            })
    return chunks


def build_treatment_chunks():
    """Render the 19 verified Arkansas records as readable prose.

    Embedding raw JSON would match poorly against a natural-language query,
    so each record becomes a sentence that still carries every field.
    """
    data = json.loads(ARKANSAS.read_text())
    src = data["_source"]
    out = []
    for table in data["tables"]:
        for i, rec in enumerate(table["records"]):
            disease = rec.get("disease_name") or table.get("disease_name")
            canon = disease in CANONICAL

            if "fungicide" in rec:
                text = (f"{table['caption']} For {rec.get('source_disease_label', disease)}: "
                        f"apply {rec['fungicide']} (active ingredient "
                        f"{rec['active_ingredient']}) at {rec['rate_per_acre']} per acre. "
                        f"{rec.get('comments', '')}").strip()
                treatment, ai, dose = rec["fungicide"], rec["active_ingredient"], rec["rate_per_acre"]
                stage = None
            else:
                text = (f"{table['caption']} For a cultivar rated "
                        f"{rec['cultivar_reaction']}, the treatment threshold is "
                        f"{rec.get('percent_positive_stops') or 'n/a'}% positive stops and "
                        f"{rec.get('percent_infected_tillers') or 'n/a'}% infected tillers. "
                        f"{rec.get('comments', '')}").strip()
                treatment, ai, dose = None, None, None
                stage = rec.get("comments")

            out.append({
                "chunk_id": f"arkansas:{table['table_id'].replace(' ', '-')}:{i}",
                "text": text,
                "source_document": src["document"],
                "document_title": src["document_title"],
                "organization": src["organization"],
                "source_url": None,
                "document_type": "bulletin",
                "ocr_derived": True,
                "chunk_type": "treatment_record",
                "disease_name": disease,
                "disease_name_is_canonical": canon,
                "source_disease_label": rec.get("source_disease_label"),
                "section": table["table_id"],
                "page_start": table["page"], "page_end": table["page"],
                "word_count": len(text.split()),
                "chunk_index": i, "chunk_total": len(table["records"]),
                "is_inoculation_protocol": False,
                "symptom": None,
                "recommended_treatment": treatment,
                "active_ingredient": ai,
                "dosage": dose,
                "crop_stage": stage,
            })
            
    return out


def main():
    chunks = build_narrative_chunks() + build_treatment_chunks()
    OUT.write_text(json.dumps(chunks, indent=2))

    wc = [c["word_count"] for c in chunks]
    types = Counter(c["chunk_type"] for c in chunks)
    canon = Counter(c["disease_name"] for c in chunks if c["disease_name_is_canonical"])
    noncanon = Counter(c["disease_name"] for c in chunks
                       if c["disease_name"] and not c["disease_name_is_canonical"])

    print(f"chunks            : {len(chunks):,}")
    print(f"words             : {sum(wc):,}")
    print(f"size  min/med/max : {min(wc)} / {sorted(wc)[len(wc)//2]} / {max(wc)}")
    print(f"chunk_type        : {dict(types)}")
    print(f"inoculation flags : {sum(1 for c in chunks if c['is_inoculation_protocol'])}")
    print(f"unassigned disease: {sum(1 for c in chunks if not c['disease_name'])}")
    print("\ncanonical class coverage:")
    for k in CANONICAL:
        t = sum(1 for c in chunks if c["disease_name"] == k and c["chunk_type"] == "treatment_record")
        print(f"   {k:<24}{canon.get(k, 0):>5} chunks  ({t} treatment_record)")
    print(f"\nnon-canonical diseases retained: {dict(noncanon)}")
    print(f"\nWrote {OUT.name}")


if __name__ == "__main__":
    
    main()
