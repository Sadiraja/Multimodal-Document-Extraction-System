"""python -m docextract.cli <file-or-dir> [--mode rules|llm|hybrid] [--out output/] [--threshold 0.85]"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .pipeline import extract_document
from .schema import SCALAR_FIELDS

EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="docextract")
    ap.add_argument("path")
    ap.add_argument("--mode", default="rules", choices=["rules", "llm", "hybrid"])
    ap.add_argument("--out", default="output")
    ap.add_argument("--threshold", type=float, default=0.85)
    a = ap.parse_args(argv)

    p = Path(a.path)
    files = sorted(f for f in p.iterdir() if f.suffix.lower() in EXT) if p.is_dir() else [p]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    queue = []
    for f in files:
        ext = extract_document(str(f), a.mode, a.threshold)
        (out / f"{f.stem}.json").write_text(ext.model_dump_json(indent=2))
        for k in SCALAR_FIELDS:
            fr = getattr(ext, k)
            if fr.needs_review:
                queue.append([f.name, k, fr.value, fr.confidence, "; ".join(fr.reasons)])
        if ext.line_items_needs_review:
            queue.append([f.name, "line_items", f"{len(ext.line_items)} items", "", "; ".join(ext.line_items_reasons)])
        print(f"{f.name}: {'REVIEW' if ext.needs_review else 'ok'}")
    with open(out / "review_queue.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["file", "field", "value", "confidence", "reasons"]); w.writerows(queue)
    print(f"\n{len(files)} documents -> {out}/ ; {len(queue)} items queued for human review "
          f"({out}/review_queue.csv)")


if __name__ == "__main__":
    main()
