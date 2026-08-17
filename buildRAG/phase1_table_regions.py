

import json
import re
from collections import Counter
from pathlib import Path

import pymupdf
"""
Phase 1 — table region detection for EXCLUSION from the narrative stream.

Decision (Beau, Phase 1): the corpus's tables are research data — conidia
sizes, near-isogenic lines, resistance-gene donors, race reactions — not
treatment guidance. They are not worth structured extraction, and extraction
proved unreliable besides. But they cannot simply be left alone: unextracted
table cells linearize into the narrative stream as noise
("F. rubra (1) 21.9 x 8.3 Phleum pratense 25.4"), which would pollute the
embedding of the real prose around them.

So each table region is located and cut, and its caption is kept as a single
informative marker line — "RBl Table 10. Rice blast fungicides in Japan and
some of their features." — which is clean, readable, and genuinely useful in
retrieval.

The one exception is the Arkansas handbook's Tables 11-2/11-3/11-4, handled
separately as verified treatment_records (see phase1_arkansas.py).

Output: table_regions.json — per document, per page, the y-bands to drop
and the caption marker to keep in their place.
"""
ROOT = Path(__file__).parent
DOCS = ROOT / "Rice_Leaves_Documents"
OUT = ROOT / "table_regions.json"

# Handled by the dedicated verified-treatment-record path instead.
ARKANSAS = "managment-of-rice-diseases.pdf"

CAPTION_RE = re.compile(
    r"^\s*(?P<prefix>[A-Z][A-Za-z]{0,5}\s+)?Table\s+(?P<num>\d+(?:-\d+)?)\s*[.．]\s+(?P<caption>\S.{6,})"
)
# "...see Table 4 for details" — a cross-reference, not a caption.
REFERENCE_START_RE = re.compile(r"^(for|in|and|or|of|to|shows?|lists?)\b", re.I)


def lines_with_pos(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"])
            if text.strip():
                x0, y0, x1, y1 = line["bbox"]
                out.append((y0, x0, x1, y1, text.strip()))
    return sorted(out)


def find_captions(page):
    """Locate captions, absorbing their wrapped continuation lines.

    Captions routinely wrap ("...inoculation of cereals and / grasses.
    Source: Narita et al 1956."). If only the first line becomes the marker,
    the remainder sits above the drop band and leaks into the narrative as a
    dangling fragment — so continuation lines are folded into the marker and
    the drop band starts beneath the last of them.
    """
    lines = lines_with_pos(page)
    width = page.rect.width
    caps = []
    for idx, (y0, x0, x1, y1, text) in enumerate(lines):
        m = CAPTION_RE.match(text)
        if not m or REFERENCE_START_RE.match(m.group("caption")):
            continue

        # A wrapped caption line is ALONE at its y and left-aligned with the
        # caption. Table cells are equally narrow but share their y with
        # sibling cells — width alone cannot tell the two apart.
        parts, bottom = [text], y1
        for j in range(idx + 1, min(idx + 4, len(lines))):
            ny0, nx0, nx1, ny1, ntext = lines[j]
            if parts[-1].rstrip().endswith((".", ":")) or CAPTION_RE.match(ntext):
                break
            siblings = sum(1 for l in lines if abs(l[0] - ny0) <= 2.0)
            if siblings > 1 or abs(nx0 - x0) > width * 0.02:
                break
            parts.append(ntext)
            bottom = ny1

        prefix = (m.group("prefix") or "").strip()
        caps.append({
            "table_id": f"{prefix} Table {m.group('num')}".strip(),
            "caption_line": " ".join(parts),
            "y_caption_top": round(y0, 1),
            "y_caption_bottom": round(bottom, 1),
        })
    return caps


def region_end(page, y_start):
    """First line below the caption that reads as running prose.

    Table cells are short and don't span the text width; body paragraphs do.
    Two consecutive prose lines end the region — one alone may be a wrapped
    caption or an in-table note.
    """
    width = page.rect.width
    prose_run = 0
    for y0, x0, x1, y1, text in lines_with_pos(page):
        if y0 <= y_start + 1:
            continue
        is_prose = (x1 - x0) > width * 0.55 and len(text.split()) > 12
        if is_prose:
            prose_run += 1
            if prose_run == 1:
                candidate = y0
            if prose_run >= 2:
                return candidate
        else:
            prose_run = 0
    return page.rect.height


def looks_tabular(page, y0, y1):
    """Confirm the band really is a table before excluding it.

    Guards against cutting narrative on a false caption match: a table band
    holds several short lines, unlike a paragraph block.
    """
    band = [l for l in lines_with_pos(page) if y0 < l[0] < y1]
    if len(band) < 3:
        return False
    width = page.rect.width
    short = sum(1 for _, x0, x1, _, t in band
                if (x1 - x0) < width * 0.55 or len(t.split()) <= 12)
    return short / len(band) >= 0.6


def scan_document(path):
    doc = pymupdf.open(path)
    pages = {}
    for i, page in enumerate(doc, start=1):
        regions = []
        for cap in find_captions(page):
            y_end = region_end(page, cap["y_caption_bottom"])
            if y_end - cap["y_caption_bottom"] < 8:
                continue
            if not looks_tabular(page, cap["y_caption_bottom"], y_end):
                continue
            regions.append({
                "table_id": cap["table_id"],
                # Kept in the narrative stream in place of the cut region.
                "caption_marker": cap["caption_line"],
                "drop_y_start": cap["y_caption_bottom"],
                "drop_y_end": round(y_end, 1),
            })
        if regions:
            pages[str(i)] = regions
    doc.close()
    return pages


def main():
    result, total = {}, 0
    for path in sorted(DOCS.glob("*.pdf")):
        if path.name == ARKANSAS:
            continue
        pages = scan_document(path)
        if pages:
            n = sum(len(v) for v in pages.values())
            total += n
            result[path.name] = pages
            print(f"{path.name[:46]:<47} {n:>3} table regions on {len(pages):>3} pages")

    OUT.write_text(json.dumps({
        "_purpose": "Table regions to CUT from the narrative text stream in Phase 2/3. "
                    "Drop every line whose bbox falls entirely within "
                    "[drop_y_start, drop_y_end] on that page.",
        "_caption_marker_usage": "DO NOT re-insert `caption_marker` into the text. The "
                                 "caption sits ABOVE drop_y_start and therefore survives "
                                 "the cut on its own — re-inserting it would duplicate it. "
                                 "The field is recorded here so each region is identifiable "
                                 "in review and so chunkers can attach the table's subject "
                                 "as metadata.",
        "_exception": f"{ARKANSAS} is excluded from this file; its treatment tables are "
                      "extracted and verified separately (treatment_records_arkansas.json).",
        "documents": result,
    }, indent=2))

    print(f"\n{total} table regions across {len(result)} documents -> {OUT.name}")
    top = Counter({d: sum(len(v) for v in p.values()) for d, p in result.items()})
    print("\nmost table-dense documents:")
    for name, n in top.most_common(5):
        print(f"  {n:>3}  {name}")


if __name__ == "__main__":
    main()
