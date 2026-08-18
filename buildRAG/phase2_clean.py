

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf
"""
Phase 2 — cleaning.

Everything here is driven by artifacts actually observed in this corpus, per
spec §6: no preemptive fix dictionaries, and nothing carried over from the
Spanish-language Compliance RAG (this corpus is English and involves no OCR
of our own).

What the evidence showed:

* **Running headers exist in exactly ONE document.** The 2025 IRRI Manual
  repeats its module title on 73 of 116 pages; the IRRI chapters have none,
  contrary to spec §6's expectation that bulletin-style documents would.
  Headers are therefore detected from the PDFs rather than assumed.

* **Word-splitting repair is deliberately NOT generalised.** A corpus-wide
  scan found only ~38 candidate splits in 325,650 words, and the single most
  frequent was "crus"+"galli" — *Echinochloa crus-galli*, a Latin binomial.
  Joining that would corrupt a species name, which is exactly why PPATH-211
  was excluded from the corpus. Only explicitly listed, eyeballed pairs are
  repaired, and any candidate adjacent to a capitalised genus is skipped.

* **No cross-document duplication exists.** All near-duplicate pairs are
  internal to the 2025 Manual (its per-disease protocols share boilerplate).
  Duplicates are FLAGGED for review, never silently dropped — a RAG that
  returns the same guidance twice implies two independent authorities agree.

Output: narrative_clean.json, cleaning_report.json
"""
ROOT = Path(__file__).parent
DOCS = ROOT / "Rice_Leaves_Documents"
IN = ROOT / "narrative_sections.json"
OUT = ROOT / "narrative_clean.json"
REPORT = ROOT / "cleaning_report.json"

HEADER_MIN_PAGES = 6
HEADER_MIN_RATIO = 0.25
HEADER_BAND = 0.08          # fraction of page height treated as header/footer

# Verified split-word repairs. Each was inspected individually. Latin
# binomials are NEVER joined — see module docstring.
WORD_JOINS = [
    ("espe cially", "especially"),
    ("experi ence", "experience"),
    ("d uring", "during"),
    ("h owever", "however"),
    ("d iseases", "diseases"),
    ("spor es", "spores"),
    ("telio spores", "teliospores"),
    ("r outine", "routine"),
]

# Genus names appearing in the corpus; a repair touching one of these is
# skipped outright rather than trusted.
GENUS_GUARD = re.compile(
    r"\b(Echinochloa|Oryza|Magnaporthe|Pyricularia|Rhizoctonia|Bipolaris|"
    r"Cercospora|Xanthomonas|Sphaerulina|Cochliobolus|Sclerotium|Fusarium)\b")


def detect_running_lines(name):
    """Lines repeated in the header/footer band on a large share of pages."""
    doc = pymupdf.open(DOCS / name)
    n = doc.page_count
    if n < HEADER_MIN_PAGES:
        doc.close()
        return []
    counts = Counter()
    for page in doc:
        height = page.rect.height
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text or text.isdigit():
                    continue
                y = line["bbox"][1]
                if y < height * HEADER_BAND or y > height * (1 - HEADER_BAND):
                    counts[text] += 1
    doc.close()
    threshold = max(4, n * HEADER_MIN_RATIO)
    return [t for t, c in counts.items() if c >= threshold and len(t) > 8]


def normalize(text):
    """Whitespace and typographic normalisation. Content-preserving.

    Does NOT resolve hyphen-plus-space: that needs corpus-wide evidence and
    is handled by dehyphenate() below.
    """
    text = unicodedata.normalize("NFKC", text)
    # NFKC decomposes modifier letters into space + combining mark, which
    # SPLITS tokens: 'A˚' (Ångström) -> 'A ̊', 'Rossello´-Mora' -> two words.
    # Re-attach the mark to the character it belongs to.
    text = re.sub(r"\s+([̀-ͯ])", r"\1", text)
    text = text.replace("­", "")                 # soft hyphen
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐‑‒–—]", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def collect_inline_hyphens(docs):
    """Pairs seen hyphenated WITHOUT a line break — i.e. lexically hyphenated.

    "crus-galli" appears inline elsewhere in the corpus, which is the evidence
    that its hyphen belongs to the word and must survive. Without this,
    Echinochloa crus-galli becomes "crusgalli".
    """
    pairs = Counter()
    for r in docs:
        for s in r["sections"]:
            for a, b in re.findall(r"(\w+)-(\w+)", s["text"]):
                pairs[(a.lower(), b.lower())] += 1
    return pairs


def dehyphenate(text, inline_pairs, log):
    """Join words split at a line end, preserving genuine hyphenated terms."""
    def repl(m):
        a, b = m.group(1), m.group(2)
        key = (a.lower(), b.lower())
        if inline_pairs.get(key, 0) > 0 or GENUS_GUARD.search(
                text[max(0, m.start() - 30):m.end() + 30]):
            log["hyphen_preserved"][f"{a}-{b}"] = (
                log["hyphen_preserved"].get(f"{a}-{b}", 0) + 1)
            return f"{a}-{b}"
        log["hyphen_joined"] += 1
        return f"{a}{b}"

    return re.sub(r"(\w+)-\s+(\w+)", repl, text)


def apply_joins(text, log):
    """Repair every listed occurrence, skipping any adjacent to a genus name.

    Rebuilt left-to-right rather than mutating in place: replacing inside the
    string shifts later match offsets, so an in-place loop over finditer
    would corrupt positions or silently repair only the first hit.
    """
    for broken, fixed in WORD_JOINS:
        pattern = re.compile(re.escape(broken))
        out, pos = [], 0
        for m in pattern.finditer(text):
            window = text[max(0, m.start() - 40):m.end() + 40]
            out.append(text[pos:m.start()])
            if GENUS_GUARD.search(window):
                log["skipped_near_genus"].append(broken)
                out.append(m.group(0))
            else:
                out.append(fixed)
                log["applied"][broken] = log["applied"].get(broken, 0) + 1
            pos = m.end()
        out.append(text[pos:])
        text = "".join(out)
    return text


def shingles(text, k=8):
    words = re.findall(r"[a-z]+", text.lower())
    return {hash(tuple(words[i:i + k])) for i in range(max(0, len(words) - k + 1))}


def main():
    docs = json.loads(IN.read_text())
    log = {"applied": {}, "skipped_near_genus": [],
           "hyphen_preserved": {}, "hyphen_joined": 0}
    inline_pairs = collect_inline_hyphens(docs)
    headers_by_doc, removed_header_words = {}, 0

    for r in docs:
        headers = detect_running_lines(r["filename"])
        if headers:
            headers_by_doc[r["filename"]] = headers

        for s in r["sections"]:
            text = s["text"]
            # Measure the header strip in ISOLATION. Measuring across the
            # whole cleaning block silently folds in the hyphen collapses
            # below, which inflated this figure by 308 words before.
            before = len(text.split())
            for h in headers:
                text = text.replace(normalize(h), " ").replace(h, " ")
            removed_header_words += before - len(text.split())

            text = normalize(text)
            text = dehyphenate(text, inline_pairs, log)
            text = apply_joins(text, log)
            s["text"] = text
            s["word_count"] = len(text.split())

        for c in r["figure_captions"]:
            c["text"] = normalize(c["text"])

    # Flag near-duplicates for review; never drop silently.
    entries = [(r["filename"], i, s) for r in docs
               for i, s in enumerate(r["sections"]) if s["word_count"] >= 60]
    shing = [(f, i, s, shingles(s["text"])) for f, i, s in entries]
    dupes = []
    for a in range(len(shing)):
        for b in range(a + 1, len(shing)):
            f1, i1, s1, g1 = shing[a]
            f2, i2, s2, g2 = shing[b]
            if not g1 or not g2:
                continue
            overlap = len(g1 & g2) / min(len(g1), len(g2))
            if overlap >= 0.30:
                dupes.append({
                    "overlap": round(overlap, 3),
                    "cross_document": f1 != f2,
                    "a": {"document": f1, "heading": s1["heading"], "words": s1["word_count"]},
                    "b": {"document": f2, "heading": s2["heading"], "words": s2["word_count"]},
                })
    dupes.sort(key=lambda d: -d["overlap"])

    OUT.write_text(json.dumps(docs, indent=2))
    REPORT.write_text(json.dumps({
        "running_headers_removed": headers_by_doc,
        "header_words_removed": removed_header_words,
        "word_joins_applied": log["applied"],
        "word_joins_skipped_near_genus": Counter(log["skipped_near_genus"]),
        "line_break_hyphens_joined": log["hyphen_joined"],
        "lexical_hyphens_preserved": log["hyphen_preserved"],
        "near_duplicates_flagged": dupes,
        "_duplicate_policy": "FLAGGED ONLY, not removed. All are internal to a single "
                             "document (repeated protocol boilerplate). No cross-document "
                             "duplication exists in this corpus.",
    }, indent=2, default=str))

    total = sum(s["word_count"] for r in docs for s in r["sections"])
    print(f"documents cleaned        : {len(docs)}")
    print(f"running headers stripped : {sum(len(v) for v in headers_by_doc.values())} "
          f"distinct lines in {len(headers_by_doc)} document(s)")
    for name, hs in headers_by_doc.items():
        print(f"     {name[:44]}")
        for h in hs:
            print(f"        {h[:66]!r}")
    print(f"header words removed     : {removed_header_words:,}")
    print(f"word joins applied       : {log['applied'] or 'none'}")
    print(f"joins skipped near genus : {dict(Counter(log['skipped_near_genus'])) or 'none'}")
    print(f"near-duplicates flagged  : {len(dupes)} "
          f"({sum(1 for d in dupes if d['cross_document'])} cross-document)")
    print(f"words after cleaning     : {total:,}")
    print(f"\nWrote {OUT.name}, {REPORT.name}")


if __name__ == "__main__":
    main()
