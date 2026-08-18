
import json
import re
import statistics
from collections import Counter
from pathlib import Path

import pymupdf
from langdetect import DetectorFactory, detect

DetectorFactory.seed = 0  # deterministic language detection
"""
Phase 0 —  documents audits of the rice disease PDF corpus.

Reports, per document: text-layer health, column layout, table-candidate
pages, figures/captions, verified front-matter identity, and language.
No OCR anywhere: a page with a thin native text layer is recorded as an
exclusion candidate, not queued for remediation.

Output: audit_report.json + a human-readable summary table on stdout.
"""
DOCS_DIR = Path(__file__).parent / "Rice_Leaves_Documents"
OUT_PATH = Path(__file__).parent / "audit_report.json"
MANIFEST_PATH = Path(__file__).parent / "source_manifest.json"

MANIFEST = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

# A page below this many chars has too thin a text layer to be usable
# without OCR, which this pipeline does not do.
THIN_TEXT_PAGE_CHARS = 100

CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?|plate|photo|table)\s*\.?\s*\d+", re.I)

# Front-matter noise that is never a real document title.
TITLE_JUNK_RE = re.compile(r"^(untitled|microsoft word|doc\d*|print|\s*)$", re.I)


def page_columns(page):
    """Classify a page as single- or two-column from text-LINE extents.

    This must be measured per line, not per word: individual words are far
    narrower than the gutter, so almost no word ever straddles the page
    centre and a word-level test collapses to "two_column" for everything.
    A single-column page is one whose lines run the full text width and
    therefore cross the centre; a two-column page's lines are confined to
    one side of the gutter.
    """
    width = page.rect.width
    centre = width / 2
    spans = []
    
    for block in page.get_text("dict")["blocks"]:
        
        for line in block.get("lines", []):
            
            x0, _, x1, _ = line["bbox"]
            
            if x1 - x0 > width * 0.05:  # ignore stray fragments
                
                spans.append((x0, x1))
                
    if len(spans) < 12:
        return "sparse"

    full_width = sum(1 for x0, x1 in spans if x1 - x0 > width * 0.55)
    left = sum(1 for x0, x1 in spans if x1 < centre + width * 0.03)
    right = sum(1 for x0, x1 in spans if x0 > centre - width * 0.03)

    one_sided = (left + right) / len(spans)
    if full_width / len(spans) > 0.25:
        return "single_column"
    
    if one_sided > 0.85 and min(left, right) / max(max(left, right), 1) > 0.3:
        
        return "two_column"
    
    return "single_column"


def page_lines(page):
    """Group words into visual lines keyed by rounded y-position."""
    lines = {}
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        lines.setdefault(round(y0 / 3), []).append((x0, x1, word))
    for line in lines.values():
        line.sort()
    return list(lines.values())


def is_table_page(page):
    """Flag pages whose lines show repeated wide intra-line gaps.

    Tabular rows separate cells with horizontal whitespace far larger than
    inter-word spacing. This only *flags candidates* for Phase 1 — column
    extraction itself is Phase 1's job, calibrated per document.
    """
    gaps, tabular_lines = [], 0
    lines = page_lines(page)
    for line in lines:
        if len(line) < 3:
            continue
        line_gaps = [nxt[0] - cur[1] for cur, nxt in zip(line, line[1:])]
        gaps.extend(line_gaps)
        if sum(1 for g in line_gaps if g > 20) >= 2:
            tabular_lines += 1
    if not gaps or tabular_lines < 3:
        return False
    # Guard against prose with justified spacing: require the wide gaps to
    # be genuine outliers against this page's own typical word spacing.
    typical = statistics.median(gaps)
    return tabular_lines >= 3 and typical < 12


def front_matter(doc):
    """Verified title/organization from the PDF itself, never the filename."""
    meta_title = (doc.metadata or {}).get("title", "") or ""
    meta_author = (doc.metadata or {}).get("author", "") or ""

    head = ""
    for page in doc[: min(3, doc.page_count)]:
        head += page.get_text() + "\n"
    head_sample = head[:3000]

    title = meta_title.strip()
    if TITLE_JUNK_RE.match(title) or len(title) < 5:
        # Fall back to the first substantial line of page 1.
        for raw in head.splitlines():
            line = raw.strip()
            if len(line) >= 12 and any(c.isalpha() for c in line):
                title = line
                break
        else:
            title = ""

    # Publisher attribution must come from imprint/copyright language, NOT
    # from body-text mentions: these are scholarly texts where "IRRI 1985"
    # is a citation of someone else's work, not a statement of publisher.
    imprint_patterns = {
        "IRRI": r"(International Rice Research Institute|\bIRRI\b)[^.\n]{0,60}"
                r"(Los Ba[nñ]os|Philippines|©|copyright|publish)"
                r"|(©|copyright|published by)[^.\n]{0,60}"
                r"(International Rice Research Institute|\bIRRI\b)",
        "FAO": r"(©|copyright|published by)[^.\n]{0,60}"
               r"(Food and Agriculture Organization|\bFAO\b)",
        "FEDEArroz": r"FEDEARROZ|Fedearroz|Federaci[oó]n Nacional de Arroceros",
    }
    imprint_hits = [
        org for org, pat in imprint_patterns.items()
        if re.search(pat, head_sample + " " + meta_author, re.I | re.S)
    ]

    # Non-target publishers this corpus turns out to contain.
    other_patterns = {
        "University of Arkansas": r"University of Arkansas|Arkansas Rice Production Handbook",
        "LSU AgCenter": r"LSU|Louisiana State University|AgCenter",
    }
    other_hits = [
        org for org, pat in other_patterns.items()
        if re.search(pat, head_sample + " " + meta_author + " " + meta_title, re.I)
    ]

    if imprint_hits:
        organization = imprint_hits[0]
    elif other_hits:
        organization = other_hits[0]
    else:
        organization = "undetermined"

    return {
        "title_verified": title[:200],
        "title_from_metadata": bool(meta_title.strip()),
        "author_metadata": meta_author[:120],
        "organization": organization,
        "organization_evidence": "imprint" if imprint_hits else (
            "publisher_name_in_frontmatter" if other_hits else "none_in_frontmatter"
        ),
    }


def classify_type(title, text_sample, table_pages, page_count):
    blob = (title + " " + text_sample).lower()
    if re.search(r"\babstract\b.{0,4000}\breferences\b", blob, re.S):
        return "research_paper"
    if re.search(r"field guide|identification guide|handbook", blob):
        return "field_guide"
    if page_count <= 40 and (table_pages or re.search(r"bulletin|extension|fact ?sheet", blob)):
        return "bulletin"
    return "other"


ORG_MENTION_PATTERNS = {
    "IRRI": r"\bIRRI\b|International Rice Research Institute",
    "FAO": r"\bFAO\b|Food and Agriculture Organization",
    "FEDEArroz": r"FEDEARROZ|Fedearroz|Federaci[oó]n Nacional de Arroceros",
}


def apply_manifest(path, fm):
    """Overlay verified provenance from source_manifest.json.

    The manifest is authoritative over both the filename and the embedded
    PDF metadata, either of which can be wrong (see Blast-Management.pdf,
    whose metadata title names a different disease than its content).
    """
    overrides = MANIFEST.get("overrides", {})
    parents = MANIFEST.get("parent_works", {})
    entry = overrides.get(path.name, {})

    parent_key = entry.get(
        "parent_work",
        MANIFEST.get("default_parent_work") if path.name not in overrides
        else entry.get("parent_work"),
    )
    if path.name in overrides and "parent_work" not in entry:
        parent_key = MANIFEST.get("default_parent_work")
    parent = parents.get(parent_key or "", {})

    out = dict(fm)
    if entry.get("verified_title"):
        out["title_verified"] = entry["verified_title"]
    if entry.get("ignore_embedded_metadata_title"):
        out["embedded_metadata_title_rejected"] = True

    org = entry.get("organization") or parent.get("organization")
    if org:
        out["organization"] = org
        out["organization_evidence"] = (
            "manifest_override" if entry.get("organization") else "manifest_parent_work"
        )
    out["parent_work"] = parent_key
    out["source_url"] = parent.get("source_url")
    out["manifest_warning"] = entry.get("warning")
    return out


def abbreviation_of(stem, title):
    """True if the filename is an initialism of the title (RBSD_SRBSD)."""
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", title)).lower()
    for token in re.findall(r"[A-Za-z]{2,}", stem):
        if token.lower() in initials:
            return True
    return False


def filename_mismatch(path, fm, full_sample):
    """Spec §3 lesson 3: does the filename actually describe the content?

    Judged against the document BODY, not its embedded metadata — metadata
    titles are themselves unreliable (stale PowerPoint titles carried over
    from copied decks). Abbreviation-style filenames are not mismatches.
    """
    stem = path.stem.lower().replace("-", " ").replace("_", " ")
    title = fm["title_verified"]
    if not title or len(title) < 5:
        return None
    if abbreviation_of(path.stem, title):
        return None
    stem_words = {w for w in re.findall(r"[a-z]+", stem) if len(w) > 3}
    title_words = {w for w in re.findall(r"[a-z]+", title.lower()) if len(w) > 3}
    if not (stem_words and title_words) or (stem_words & title_words):
        return None

    # Which side does the body support? Count topic words from each.
    def support(words):
        return sum(len(re.findall(rf"\b{re.escape(w)}", full_sample, re.I))
                   for w in words)

    stem_hits, title_hits = support(stem_words), support(title_words)
    if stem_hits >= title_hits:
        return (f"filename {path.stem!r} agrees with body text; embedded "
                f"metadata title {title!r} is unreliable "
                f"(body support {stem_hits} vs {title_hits})")
    return (f"filename {path.stem!r} disagrees with body text, which "
            f"supports {title!r} (body support {title_hits} vs {stem_hits})")


def audit_pdf(path):
    doc = pymupdf.open(path)
    per_page, layouts, table_pages, thin_pages = [], Counter(), [], []
    figure_count = caption_count = 0
    caption_samples = []
    text_accum = []

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        chars = len(text.strip())
        images = len(page.get_images(full=True))
        figure_count += images

        captions = [
            ln.strip()
            for ln in text.splitlines()
            if CAPTION_RE.match(ln) and len(ln.strip()) > 12
        ]
        caption_count += len(captions)
        caption_samples.extend(captions[:2])

        layout = page_columns(page)
        layouts[layout] += 1
        tabular = is_table_page(page)
        if tabular:
            table_pages.append(i)
        if chars < THIN_TEXT_PAGE_CHARS:
            thin_pages.append(i)
        if len(text_accum) < 12 and chars > 400:
            text_accum.append(text)

        per_page.append(
            {
                "page": i,
                "chars": chars,
                "images": images,
                "captions": len(captions),
                "layout": layout,
                "table_candidate": tabular,
            }
        )

    total_chars = sum(p["chars"] for p in per_page)
    sample = "\n".join(text_accum)

    try:
        language = detect(sample[:5000]) if len(sample) > 200 else "unknown"
    except Exception:
        language = "unknown"

    raw_fm = front_matter(doc)
    # Mismatch is judged against the RAW embedded identity, before the
    # manifest corrects it — otherwise the correction hides the finding.
    mismatch = filename_mismatch(path, raw_fm, sample)
    fm = apply_manifest(path, raw_fm)
    dominant_layout = (
        "two_column"
        if layouts["two_column"] > layouts["single_column"]
        else "single_column"
    )

    result = {
        "filename": path.name,
        "page_count": doc.page_count,
        "total_chars": total_chars,
        "chars_per_page": round(total_chars / max(doc.page_count, 1), 1),
        "thin_text_pages": thin_pages,
        "thin_text_page_ratio": round(len(thin_pages) / max(doc.page_count, 1), 3),
        "excluded_pages_no_ocr": thin_pages,
        "layout_dominant": dominant_layout,
        "layout_page_counts": dict(layouts),
        "table_candidate_pages": table_pages,
        "table_page_ratio": round(len(table_pages) / max(doc.page_count, 1), 3),
        "figure_count": figure_count,
        "caption_count": caption_count,
        "caption_samples": caption_samples[:5],
        "language_detected": language,
        **fm,
        # Body-text mentions are recorded for context only. They are NOT
        # publisher evidence — in these scholarly texts "IRRI 1985" is a
        # citation. Do not promote these counts to `organization`.
        "org_mentions_bodytext_nonauthoritative": {
            org: len(re.findall(pat, sample, re.I))
            for org, pat in ORG_MENTION_PATTERNS.items()
        },
        "producer": (doc.metadata or {}).get("producer", ""),
        "per_page": per_page,
    }
    result["filename_content_mismatch"] = mismatch
    entry = MANIFEST.get("overrides", {}).get(path.name, {})
    result["document_type"] = entry.get("document_type") or classify_type(
        fm["title_verified"], sample[:6000], table_pages, doc.page_count
    )
    result["extraction_path"] = recommend_path(result)
    doc.close()
    return result


def recommend_path(r):
    """Phase 1 extraction route, decided per document per spec §5."""
    if r["table_page_ratio"] >= 0.15:
        return "bbox_table_extraction"
    if r["layout_dominant"] == "two_column":
        return "bbox_column_sorted"
    return "plain_get_text"


def main():
    pdfs = sorted(DOCS_DIR.glob("*.pdf"))
    print(f"Auditing {len(pdfs)} PDFs in {DOCS_DIR.name}/\n")
    results = [audit_pdf(p) for p in pdfs]

    # Files sharing a PDF producer + chapter-style naming are almost
    # certainly chapters of one parent work, not independent sources.
    producer_clusters = Counter(r["producer"] for r in results)

    OUT_PATH.write_text(json.dumps(
        {
            "corpus_dir": str(DOCS_DIR.name),
            "document_count": len(results),
            "ocr_used": False,
            "notes": [
                "organization is derived from imprint/copyright language only; "
                "body-text org mentions are citations and are recorded separately "
                "as non-authoritative",
                "thin-text pages are exclusion candidates; no OCR path exists",
            ],
            "producer_clusters": dict(producer_clusters),
            "documents": results,
        },
        indent=2,
    ))

    name_w = 46
    print(f"{'document':<{name_w}} {'pg':>4} {'ch/pg':>7} {'thin':>5} "
          f"{'layout':<13} {'tbl':>4} {'fig':>5} {'cap':>4} {'org':<10} {'lang':<5} path")
    print("-" * 148)
    for r in results:
        name = r["filename"][: name_w - 1]
        print(
            f"{name:<{name_w}} {r['page_count']:>4} {r['chars_per_page']:>7.0f} "
            f"{len(r['thin_text_pages']):>5} {r['layout_dominant']:<13} "
            f"{len(r['table_candidate_pages']):>4} {r['figure_count']:>5} "
            f"{r['caption_count']:>4} {r['organization']:<10} "
            f"{r['language_detected']:<5} {r['extraction_path']}"
        )

    print("\n=== Corpus totals ===")
    print(f"documents            : {len(results)}")
    print(f"pages                : {sum(r['page_count'] for r in results)}")
    print(f"characters           : {sum(r['total_chars'] for r in results):,}")
    print(f"thin-text pages      : {sum(len(r['thin_text_pages']) for r in results)}"
          f"  (excluded, no OCR path)")
    print(f"table-candidate pages: {sum(len(r['table_candidate_pages']) for r in results)}")
    print(f"figures / captions   : {sum(r['figure_count'] for r in results)}"
          f" / {sum(r['caption_count'] for r in results)}")
    for label, key in (("organization", "organization"),
                       ("document_type", "document_type"),
                       ("language", "language_detected"),
                       ("extraction_path", "extraction_path")):
        dist = Counter(r[key] for r in results)
        print(f"{label:<21}: {dict(dist.most_common())}")

    print("\n=== Provenance clusters (PDF producer) ===")
    for prod, n in producer_clusters.most_common():
        print(f"  {n:>3}  {prod or '(none)'}")

    mismatches = [r for r in results if r["filename_content_mismatch"]]
    print(f"\n=== Filename/content mismatches (spec §3 lesson 3): {len(mismatches)} ===")
    for r in mismatches:
        print(f"  ! {r['filename_content_mismatch']}")

    print("\n=== Thin-text documents (exclusion candidates, no OCR) ===")
    for r in sorted(results, key=lambda x: -x["thin_text_page_ratio"])[:6]:
        if r["thin_text_pages"]:
            print(f"  {r['filename'][:52]:<53} {len(r['thin_text_pages'])}/{r['page_count']} pages"
                  f"  ({r['chars_per_page']:.0f} ch/pg)")
    print(f"\nWrote {OUT_PATH.name}")


if __name__ == "__main__":
    
    main()
