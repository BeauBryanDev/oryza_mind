#%%
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import CLASS_NAMES, get_settings
from app.core.load_vision_model import get_model
from app.schemas.common import severity_from_area
from app.services.vision_service import analyze_image
from app.utils.image_utils import decode_image
from app.utils.preprocessing import to_tensor

IMAGE_DIR = ROOT / "eval" / "eval_vision"
OUT_PATH = ROOT / "eval" / "vision_eval_results.json"
HEALTHY = "Healthy"
UNCERTAIN_BELOW = 0.5

# File names are free-form and misspelled ("Lea_Blast", "Bacteria_Leat"), so the
# true class is read from a keyword rather than the exact canonical string.
LABEL_KEYWORDS = (
    ("bacteri", "Bacterial_Leaf_Blight"),
    ("narrow", "Narrow_Brown"),  # before brown_spot: "Narrow_Brown_Spot" contains both
    ("brown_spot", "Brown_Spot"),
    ("blast", "Leaf_Blast"),
    ("tungro", "Rice_Tungro"),
    ("sheath", "Sheath_Blight"),
    ("healthy", HEALTHY),
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def true_label(path):
    name = path.stem.lower()
    return next(label for key, label in LABEL_KEYWORDS if key in name)


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


# Photos already used in earlier evals; reported, but kept out of the fresh score.
SEEN = {md5(p) for p in ROOT.glob("*.jp*g")}

#%%
def raw_activation(data, filename):
    """Max pre-threshold class score per class, to tell a near-miss from a blind spot."""
    image = decode_image(data, filename)
    tensor, _ = to_tensor(image, get_settings().yolo_input_size)
    out0 = get_model().run(tensor)[0]
    scores = out0[0, 4:4 + len(CLASS_NAMES), :]
    return {name: round(float(scores[i].max()), 4) for i, name in enumerate(CLASS_NAMES)}


results = []
for path in sorted(p for p in IMAGE_DIR.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
    data = path.read_bytes()
    label = true_label(path)
    analysis = analyze_image(data, filename=path.name, with_overlay=False)
    dets = sorted(analysis.result.detections, key=lambda d: d.confidence, reverse=True)
    top = dets[0] if dets else None
    classes = sorted({d.class_name for d in dets})

    if label == HEALTHY:
        verdict = "correct" if not dets else "false_positive"
    elif top is None:
        verdict = "missed"
    elif top.class_name == label:
        verdict = "correct"
    elif label in classes:
        verdict = "found_not_top"
    else:
        verdict = "wrong"

    activation = raw_activation(data, path.name)
    row = {
        "file": path.name,
        "label": label,
        "seen_before": md5(path) in SEEN,
        "size": f"{analysis.result.width}x{analysis.result.height}",
        "verdict": verdict,
        "top": top.class_name if top else None,
        "top_conf": round(top.confidence, 3) if top else None,
        "classes": classes,
        "n_detections": len(dets),
        "affected_pct": round(analysis.result.affected_ratio * 100, 2),
        "severity": severity_from_area(analysis.result.affected_ratio).value if dets else None,
        "raw_true_class": activation.get(label),
        "raw_top_class": max(activation, key=activation.get),
    }
    results.append(row)

#%%
for r in results:
    seen = " (seen)" if r["seen_before"] else ""
    extra = [c for c in r["classes"] if c != r["top"]]
    print(f"{r['file']:28} {r['label']:22} {r['verdict']:15} top={r['top']} {r['top_conf']} "
          f"also={extra} sev={r['severity']} {r['affected_pct']}% "
          f"raw_true={r['raw_true_class']} {r['size']}{seen}")


def summarize(rows):
    diseased = [r for r in rows if r["label"] != HEALTHY]
    healthy = [r for r in rows if r["label"] == HEALTHY]
    return {
        "n": len(rows),
        "top1_correct": f"{sum(r['verdict'] == 'correct' for r in diseased)}/{len(diseased)}",
        "found_anywhere": f"{sum(r['verdict'] in ('correct', 'found_not_top') for r in diseased)}/{len(diseased)}",
        "healthy_clean": f"{sum(r['verdict'] == 'correct' for r in healthy)}/{len(healthy)}",
        "multi_class_images": sum(len(r["classes"]) > 1 for r in rows),
        "confident_wrong": sum(r["verdict"] == "wrong" and r["top_conf"] >= UNCERTAIN_BELOW
                               for r in rows),
    }


per_class = {}
for label in (*CLASS_NAMES, HEALTHY):
    rows = [r for r in results if r["label"] == label]
    per_class[label] = f"{sum(r['verdict'] == 'correct' for r in rows)}/{len(rows)}"

summary = {
    "all": summarize(results),
    "fresh_only": summarize([r for r in results if not r["seen_before"]]),
    "per_class_top1": per_class,
    "confusions": dict(Counter(f"{r['label']} -> {r['top']}" for r in results
                               if r["verdict"] in ("wrong", "found_not_top", "false_positive"))),
}
print(json.dumps(summary, indent=2))

#%%
with OUT_PATH.open("w", encoding="utf-8") as f:
    json.dump({"summary": summary, "results": results}, f, indent=2)
