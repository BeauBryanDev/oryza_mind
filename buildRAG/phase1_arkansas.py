
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent
DOC = ROOT / "Rice_Leaves_Documents" / "managment-of-rice-diseases.pdf"
RECORDS = ROOT / "treatment_records_arkansas.json"

# Fields whose value must appear verbatim in the source page.
VERIFIED_FIELDS = ("fungicide", "active_ingredient", "rate_per_acre",
                   "cultivar_reaction", "percent_positive_stops",
                   "percent_infected_tillers")

# Our own cross-reference text, not source text — exempt from verification.
EXEMPT_VALUES = ("See shared guidance for Table 11-4: twice-applied, "
                 "late boot and 50%-75% heading.",)


def normalize(text):
    """Fold OCR/typographic variance so comparison tests content, not glyphs."""
    text = unicodedata.normalize("NFKD", text)
    text = (text.replace("–", "-").replace("—", "-")
                .replace("’", "'").replace("­", ""))
    return re.sub(r"\s+", " ", text).strip().lower()


def page_text(doc, page_no):
    return normalize(doc[page_no - 1].get_text())


def check(value, haystack):
    """Is `value` present, allowing for line-wrap inside the source?"""
    v = normalize(value)
    if v in haystack:
        return True
    # Cells wrap mid-value ("trifloxystrobin +\npropiconazole"); accept when
    # every token appears in order within a short window.
    tokens = v.split()
    pos, start = 0, -1
    for t in tokens:
        pos = haystack.find(t, pos)
        if pos == -1:
            return False
        if start < 0:
            start = pos
        pos += len(t)
    return (pos - start) < len(v) + 120


def main():
    data = json.loads(RECORDS.read_text())
    doc = pymupdf.open(DOC)

    failures, checked = [], 0
    for table in data["tables"]:
        text = page_text(doc, table["page"])
        print(f"\n{table['table_id']} (p{table['page']}) — {table['caption']}")

        if not check(table["caption"].rstrip("."), text):
            failures.append((table["table_id"], "caption", table["caption"]))

        for i, rec in enumerate(table["records"]):
            for field in VERIFIED_FIELDS:
                val = rec.get(field)
                if not val or val in EXEMPT_VALUES:
                    continue
                checked += 1
                if not check(val, text):
                    failures.append((table["table_id"], f"row{i}.{field}", val))

            label = rec.get("source_disease_label", "")
            if label:
                core = label.split("(")[0].strip()
                checked += 1
                if not check(core, text):
                    failures.append((table["table_id"], f"row{i}.disease", core))

        print(f"   {len(table['records'])} records")

    doc.close()

    print(f"\n{'=' * 60}\nVerified {checked} field values against source pages.")
    if failures:
        print(f"FAILED: {len(failures)} value(s) not found in source:")
        for tid, where, val in failures:
            print(f"  ! {tid} {where}: {val[:70]!r}")
        sys.exit(1)

    canonical = {"Bacterial_Leaf_Blight", "Brown_Spot", "Leaf_Blast",
                 "Narrow_Brown", "Rice_Tungro", "Sheath_Blight"}
    used = {r.get("disease_name") for t in data["tables"] for r in t["records"]}
    used |= {t.get("disease_name") for t in data["tables"]}
    print("PASSED — every transcribed value occurs in its source page.")
    print(f"\ncanonical classes used : {sorted(used & canonical)}")
    print(f"non-canonical retained : {sorted(x for x in used if x and x not in canonical)}")


if __name__ == "__main__":
    
    main()
