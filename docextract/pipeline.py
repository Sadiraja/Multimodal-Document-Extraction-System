from __future__ import annotations

import re
from pathlib import Path

from . import rules, validate
from .ocr import Line, run_ocr, VARIANTS
from .schema import Extraction, SCALAR_FIELDS

UNGROUNDED_FACTOR = 0.7


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _ground(ir: dict, lines: list[Line]) -> dict:
    """LLM values should be visible in independent OCR text. Values the OCR cannot find are penalised -
    this catches hallucinations and misread digits that the model is confident about."""
    blob = _norm(" ".join(l.text for l in lines))
    for k, f in ir["fields"].items():
        v = f["value"]
        if v is None or k in ("currency", "date"):
            continue
        cand = [f"{float(v):.2f}", f"{float(v):,.2f}"] if k in ("subtotal", "tax", "total") else [str(v)]
        if not any(_norm(c) in blob for c in cand):
            f["conf"] *= UNGROUNDED_FACTOR
            f["reasons"].append("value not found in OCR text")
    for it in ir["line_items"]:
        if it.get("amount") is not None and _norm(f"{it['amount']:.2f}") not in blob \
                and _norm(f"{it['amount']:,.2f}") not in blob:
            it["conf"] *= UNGROUNDED_FACTOR
    return ir


def _merge(a: dict, b: dict) -> dict:
    """a = rules IR, b = LLM IR. Agreement raises confidence; disagreement flags the field."""
    fields = {}
    for k in SCALAR_FIELDS:
        fa, fb = a["fields"][k], b["fields"][k]
        same = fa["value"] is not None and _norm(fa["value"]) == _norm(fb["value"])
        if same:
            fields[k] = {"value": fa["value"], "conf": min(0.99, 1 - (1 - fa["conf"]) * (1 - fb["conf"])),
                         "reasons": []}
        else:
            best = fb if fb["conf"] >= fa["conf"] else fa
            fields[k] = {"value": best["value"], "conf": best["conf"] * 0.5,
                         "reasons": ["extractors disagree: rules=%r llm=%r" % (fa["value"], fb["value"])]}
    return {"fields": fields, "line_items": b["line_items"] or a["line_items"]}


def _score(ext: Extraction) -> float:
    """How much do the validators trust this reading? (sum of field + line-item confidences)"""
    return sum(getattr(ext, k).confidence for k in SCALAR_FIELDS) + sum(i.confidence for i in ext.line_items)


def best_ocr(path: str, threshold: float, variants=VARIANTS) -> list[Line]:
    """Multi-pass OCR: different binarisations fail on different scans. Run each, extract + validate,
    and keep the reading whose cross-checks (arithmetic, formats) leave the highest confidence.
    Stops early as soon as a pass produces a fully-consistent document."""
    best, best_s = None, -1.0
    for v in variants:
        lines = run_ocr(path, v)
        ext = validate.finalize(rules.extract(lines), threshold)
        if not ext.needs_review:
            return lines
        s = _score(ext)
        if s > best_s:
            best, best_s = lines, s
    return best


def extract_document(path: str, mode: str = "rules", threshold: float = 0.85,
                     lines: list[Line] | None = None, model: str | None = None) -> Extraction:
    """mode: 'rules' (offline) | 'llm' (Claude vision, OCR-grounded) | 'hybrid' (rules first, LLM only when flagged)."""
    path = str(path)
    if lines is None:
        lines = best_ocr(path, threshold)
    if mode == "rules":
        ir = rules.extract(lines)
    else:
        from . import llm
        if mode == "llm":
            ir = _ground(llm.extract(path, model), lines)
        elif mode == "hybrid":
            r_ir = rules.extract(lines)
            first = validate.finalize(r_ir, threshold)
            if not first.needs_review:
                ir = r_ir
            else:
                ir = _merge(r_ir, _ground(llm.extract(path, model), lines))
        else:
            raise ValueError(f"unknown mode {mode!r}")
    return validate.finalize(ir, threshold, source_file=Path(path).name, extractor=mode)
