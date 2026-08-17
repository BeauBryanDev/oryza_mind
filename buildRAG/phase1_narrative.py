
import json
import re
import statistics
from collections import Counter
from pathlib import Path

import pymupdf
"""
Phase 1 — narrative extraction into sections.

Per-document routing comes from Phase 0 (audit_report.json): two-column
pages are read column-by-column, everything else in block order. Table
regions found in Phase 1 (table_regions.json) are cut from the stream.

HEADING DETECTION (spec §3 lesson 2)
 
Two independent signals produce heading candidates:
  1. a numbered pattern — "3.1. Symptoms", "1.5.2.3. Detection using..."
  2. font size larger than the document's own body size

Bold is deliberately NOT used: these PDFs carry bold spans mid-sentence, so
it produces false headings. Whichever signal fires, every candidate passes
through the SAME quality gate (`is_plausible_heading`) — that is the lesson
the Art-Atelier build paid for, where an all-caps rule let figure
references and scanner debris become chapter boundaries and fragmented
continuous prose.

Output: narrative_sections.json
"""
ROOT = Path(__file__).parent
DOCS = ROOT / "Rice_Leaves_Documents"
OUT = ROOT / "narrative_sections.json"

AUDIT = {d["filename"]: d for d in
         json.loads((ROOT / "audit_report.json").read_text())["documents"]}
REGIONS = json.loads((ROOT / "table_regions.json").read_text())["documents"]
MANIFEST = json.loads((ROOT / "source_manifest.json").read_text())

NUMBERED_RE = re.compile(r"^\d+(\.\d+){0,3}\.?\s+[A-Z(]")
FIGURE_RE = re.compile(r"^\s*([A-Z][A-Za-z]{0,5}\s+)?(Fig(ure)?|Photo|Plate)\s*\.?\s*\d+", re.I)
PAGE_NUM_RE = re.compile(r"^\s*\d{1,4}\s*$")
# Reference-list lines: "Ou S. H. 1985. Rice diseases..." / "Mol. Plant Pathol. 7:303-324."
REFERENCE_RE = re.compile(r"^[A-Z][a-z]+,?\s+[A-Z]\.\s*[A-Z]?\.?\s*\d{4}[.,]|\d+:\d+[-‒–]\d+")
# A wrapped citation continuing with its year — "1992. Nucleotide sequence of..."
# matches the numbered-heading shape and would split a reference list into
# dozens of bogus sections.
YEAR_START_RE = re.compile(r"^(1[89]|20)\d{2}\s*[.,]")

# Section headings that introduce a bibliography rather than content.
BIBLIOGRAPHY_RE = re.compile(
    r"^\s*(references|bibliography|literature cited|further reading|acknowledge)", re.I)

MAX_HEADING_WORDS = 14
MIN_HEADING_CHARS = 3


def is_plausible_heading(text, size, body_size):
    """THE shared quality gate. Every candidate passes here, no exceptions.

    Rejects the debris that silently degraded chunking in the prior build:
    mid-sentence fragments, figure/table references, page numbers, citation
    lines, and anything too long to be a title.
    """
    t = text.strip()
    if len(t) < MIN_HEADING_CHARS or len(t.split()) > MAX_HEADING_WORDS:
        return False
    if not any(c.isalpha() for c in t):
        return False
    if PAGE_NUM_RE.match(t) or FIGURE_RE.match(t) or REFERENCE_RE.match(t):
        return False
    if YEAR_START_RE.match(t):
        return False
    if re.match(r"^(Table|Source|Note|continued)\b", t, re.I):
        return False
    # Character variety: guards against runs of dots/dashes or "AAAA".
    if len(set(t.lower().replace(" ", ""))) < 3:
        return False
    # A sentence fragment: starts lowercase and isn't numbered.
    if t[0].islower() and not NUMBERED_RE.match(t):
        return False
    # Ends mid-clause — real headings don't end in a comma or conjunction.
    if re.search(r"[,;]$|\b(and|or|of|the|in|with|for|to)$", t, re.I):
        return False
    # Prose ending in a period is only a heading if it is numbered.
    if t.endswith(".") and not NUMBERED_RE.match(t):
        return False
    # "1. Stunting - reduction in plant height" is a numbered LIST ITEM, not a
    # section heading: the dash introduces a definition. Treating these as
    # headings shreds a list into one-line sections.
    if NUMBERED_RE.match(t) and re.search(r"\s[–—-]\s", t):
        return False
    return True


def is_slide_deck(name, body_size):
    """Slide decks defeat the font-size signal — everything is large text.

    Detected from the PDF producer plus an implausibly large body size. For
    these, each page is one section (a slide is already a coherent unit).
    """
    producer = (AUDIT[name].get("producer") or "").lower()
    return "powerpoint" in producer or body_size >= 18.0


def merge_empty_sections(sections):
    """Fold heading-only sections into the next section that has content.

    A heading with no body is either a multi-line heading or a stray
    fragment; either way it must not become its own chunk. Its text is
    carried forward rather than dropped, so no content is lost.
    """
    out, pending = [], []
    for s in sections:
        if s["word_count"] < 5:
            if s["heading"]:
                pending.append(s["heading"])
            continue
        if pending:
            s = dict(s)
            s["heading"] = " / ".join(pending + ([s["heading"]] if s["heading"] else []))
            pending = []
        out.append(s)
    if pending and out:
        out[-1] = dict(out[-1])
        out[-1]["heading"] = (out[-1]["heading"] or "") + " / " + " / ".join(pending)
    return out


def page_lines(page, bands):
    """Lines with table bands and page numbers removed, in reading order."""
    width = page.rect.width
    raw = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            if any(b["drop_y_start"] <= y0 and y1 <= b["drop_y_end"] for b in bands):
                continue
            if PAGE_NUM_RE.match(text):
                continue
            size = max(s["size"] for s in line["spans"])
            raw.append({"x0": x0, "y0": y0, "x1": x1, "text": text, "size": round(size, 1)})
    return raw, width


def order_lines(lines, width, two_column):
    """Column-aware ordering; naive y-sort interleaves two-column pages."""
    if not two_column:
        return sorted(lines, key=lambda l: (round(l["y0"], 1), l["x0"]))
    centre = width / 2
    left = [l for l in lines if (l["x0"] + l["x1"]) / 2 <= centre]
    right = [l for l in lines if (l["x0"] + l["x1"]) / 2 > centre]
    key = lambda l: (round(l["y0"], 1), l["x0"])
    return sorted(left, key=key) + sorted(right, key=key)


def body_font_size(name):
    """Modal font size across the document = its body text size."""
    doc = pymupdf.open(DOCS / name)
    sizes = Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if len(text.split()) >= 6:
                    sizes[round(max(s["size"] for s in line["spans"]), 1)] += 1
    doc.close()
    return sizes.most_common(1)[0][0] if sizes else 11.0


def extract(name):
    audit = AUDIT[name]
    two_column = audit["layout_dominant"] == "two_column"
    bands_by_page = REGIONS.get(name, {})
    body_size = body_font_size(name)

    slides = is_slide_deck(name, body_size)
    doc = pymupdf.open(DOCS / name)
    sections = [{"heading": None, "text": [], "page_start": 1, "page_end": 1}]
    captions = []

    for pno, page in enumerate(doc, start=1):
        lines, width = page_lines(page, bands_by_page.get(str(pno), []))
        ordered = order_lines(lines, width, two_column)

        if slides:
            # One slide = one section; its first line is the slide title.
            if not ordered:
                continue
            title = ordered[0]["text"]
            head = title if is_plausible_heading(title, 0, 0) else None
            body = ordered[1:] if head else ordered
            sections.append({"heading": head,
                             "text": [l["text"] for l in body],
                             "page_start": pno, "page_end": pno})
            continue

        for line in ordered:
            text, size = line["text"], line["size"]

            if FIGURE_RE.match(text) and size <= body_size:
                captions.append({"page": pno, "text": text})
                continue

            numbered = bool(NUMBERED_RE.match(text))
            larger = size >= body_size + 0.9
            if (numbered or larger) and is_plausible_heading(text, size, body_size):
                sections.append({"heading": text, "text": [],
                                 "page_start": pno, "page_end": pno})
            else:
                sections[-1]["text"].append(text)
                sections[-1]["page_end"] = pno
    doc.close()

    out = []
    for s in sections:
        body = re.sub(r"\s+", " ", " ".join(s["text"])).strip()
        # Rejoin ONLY soft-hyphen line breaks (U+00AD), which are unambiguous.
        # A normal hyphen before a line break may be lexical — joining those
        # blindly destroyed "Echinochloa crus-galli" into "crusgalli". Regular
        # hyphens are resolved in Phase 2, which has corpus-wide evidence for
        # deciding each case.
        body = re.sub(r"(\w)­\s*(\w)", r"\1\2", body)
        if len(body.split()) < 5 and not s["heading"]:
            continue
        out.append({"heading": s["heading"], "text": body,
                    "word_count": len(body.split()),
                    "page_start": s["page_start"], "page_end": s["page_end"]})
    out = merge_empty_sections(out)

    # Bibliographies are ~a fifth of this corpus's narrative words and carry
    # no diagnostic or treatment content. They are separated rather than
    # deleted, so the word-count reconciliation still balances and the
    # decision stays visible.
    bibliography = [s for s in out if s["heading"] and BIBLIOGRAPHY_RE.match(s["heading"])]
    out = [s for s in out if not (s["heading"] and BIBLIOGRAPHY_RE.match(s["heading"]))]

    entry = MANIFEST.get("overrides", {}).get(name, {})
    parent = MANIFEST["parent_works"].get(
        entry.get("parent_work", MANIFEST["default_parent_work"]) or "", {})
    return {
        "filename": name,
        "document_title": entry.get("verified_title") or audit["title_verified"],
        "organization": entry.get("organization") or parent.get("organization"),
        "document_type": entry.get("document_type") or audit["document_type"],
        "two_column": two_column,
        "body_font_size": body_size,
        "sections": out,
        "bibliography_excluded": bibliography,
        "figure_captions": captions,
    }


def main():
    results = [extract(p.name) for p in sorted(DOCS.glob("*.pdf"))]
    OUT.write_text(json.dumps(results, indent=2))

    print(f"{'document':<47}{'sects':>6}{'words':>9}{'headed':>8}{'caps':>6}")
    print("-" * 76)
    tot_w = tot_s = tot_h = tot_c = 0
    for r in results:
        w = sum(s["word_count"] for s in r["sections"])
        h = sum(1 for s in r["sections"] if s["heading"])
        print(f"{r['filename'][:46]:<47}{len(r['sections']):>6}{w:>9,}{h:>8}"
              f"{len(r['figure_captions']):>6}")
        tot_w += w; tot_s += len(r["sections"]); tot_h += h
        tot_c += len(r["figure_captions"])
    print("-" * 76)
    print(f"{'TOTAL':<47}{tot_s:>6}{tot_w:>9,}{tot_h:>8}{tot_c:>6}")
    wc = [s["word_count"] for r in results for s in r["sections"]]
    print(f"\nsection words: median {statistics.median(wc):.0f}  "
          f"mean {statistics.mean(wc):.0f}  max {max(wc)}")
    print(f"sections with no heading: {tot_s - tot_h}")

    bib_s = sum(len(r["bibliography_excluded"]) for r in results)
    bib_w = sum(s["word_count"] for r in results for s in r["bibliography_excluded"])
    print(f"\nbibliography excluded: {bib_s} sections, {bib_w:,} words "
          f"({100 * bib_w / (bib_w + tot_w):.1f}% of extracted narrative)")
    print(f"retained for chunking: {tot_w:,} words")
    print(f"\nWrote {OUT.name}")


if __name__ == "__main__":
    main()
