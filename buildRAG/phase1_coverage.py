
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent
DOCS = ROOT / "Rice_Leaves_Documents"
REGIONS = json.loads((ROOT / "table_regions.json").read_text())["documents"]
OUT = ROOT / "class_coverage.json"

# Deliberately specific: pathogen binomials plus the common disease names.
CLASSES = {
    "Bacterial_Leaf_Blight": r"bacterial (leaf )?blight|\bBLB\b|\bBB\b(?! Table)|Xanthomonas oryzae pv\.? oryzae\b|\bXoo\b",
    "Brown_Spot": r"brown spot|Bipolaris oryzae|Cochliobolus miyabeanus|Helminthosporium oryzae",
    "Leaf_Blast": r"\bleaf blast\b|\bblast\b|Magnaporthe|Pyricularia",
    "Narrow_Brown": r"narrow brown( leaf)? spot|\bNBLS\b|Cercospora janseana|Sphaerulina oryzina",
    "Rice_Tungro": r"tungro|\bRTBV\b|\bRTSV\b",
    "Sheath_Blight": r"sheath blight|Rhizoctonia solani|\bShB\b",
}

TREATMENT_RE = re.compile(
    r"fungicid|chemical control|管理|manage(ment)?\b|control measure|cultural practice|"
    r"resistant variet|seed treatment|spray|dosage|application rate|integrated",
    re.I,
)

# Guards against counting a screening manual's infection protocols as
# treatment content (see source_manifest.json retrieval_hazard).
INOCULATION_RE = re.compile(
    r"inoculat|spore suspension|inoculum|clipping method|greenhouse test|screening", re.I
)


def page_texts(name):
    """Page text with table regions removed, mirroring Phase 2/3 input."""
    doc = pymupdf.open(DOCS / name)
    bands_by_page = REGIONS.get(name, {})
    out = []
    for i, page in enumerate(doc, start=1):
        bands = bands_by_page.get(str(i), [])
        kept = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                y0, y1 = line["bbox"][1], line["bbox"][3]
                if any(b["drop_y_start"] <= y0 and y1 <= b["drop_y_end"] for b in bands):
                    continue
                kept.append(text)
        out.append(" ".join(kept))
    doc.close()
    return out


def main():
    stats = {c: {"mentions": 0, "pages": 0, "primary_pages": 0,
                 "treatment_pages": 0, "inoculation_only_pages": 0,
                 "documents": Counter()} for c in CLASSES}
    per_doc = defaultdict(Counter)

    for path in sorted(DOCS.glob("*.pdf")):
        for text in page_texts(path.name):
            if not text:
                continue
            counts = {c: len(re.findall(p, text, re.I)) for c, p in CLASSES.items()}
            total = sum(counts.values())
            if not total:
                continue
            treat = bool(TREATMENT_RE.search(text))
            inoc = bool(INOCULATION_RE.search(text))

            for c, n in counts.items():
                if not n:
                    continue
                stats[c]["mentions"] += n
                stats[c]["pages"] += 1
                stats[c]["documents"][path.name] += n
                per_doc[path.name][c] += n
                # "Primary" = this class owns most of the page's disease talk.
                if n / total >= 0.6:
                    stats[c]["primary_pages"] += 1
                    if treat and not (inoc and not treat):
                        stats[c]["treatment_pages"] += 1
                    if inoc and not treat:
                        stats[c]["inoculation_only_pages"] += 1

    print(f"{'class':<24}{'mentions':>9}{'pages':>7}{'primary':>9}{'treatment':>11}{'docs':>6}")
    print("-" * 66)
    for c in CLASSES:
        s = stats[c]
        print(f"{c:<24}{s['mentions']:>9}{s['pages']:>7}{s['primary_pages']:>9}"
              f"{s['treatment_pages']:>11}{len(s['documents']):>6}")

    print("\ntop documents per class (by mentions):")
    for c in CLASSES:
        top = stats[c]["documents"].most_common(3)
        print(f"  {c}")
        for name, n in top:
            print(f"      {n:>5}  {name[:58]}")
        if not top:
            print("      (none)")

    OUT.write_text(json.dumps(
        {c: {**v, "documents": dict(v["documents"])} for c, v in stats.items()}, indent=2))
    print(f"\nWrote {OUT.name}")


if __name__ == "__main__":
    main()
