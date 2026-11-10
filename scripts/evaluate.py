"""Field-level accuracy evaluation against ground-truth JSON.

    python scripts/evaluate.py --samples data/samples --mode rules --out reports
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docextract.pipeline import extract_document  # noqa: E402
from docextract.schema import SCALAR_FIELDS, MONEY_FIELDS  # noqa: E402

alnum = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())


def field_correct(name, pred, gt) -> bool:
    if pred is None:
        return False
    if name in MONEY_FIELDS:
        return abs(float(pred) - float(gt)) < 0.005
    return alnum(pred) == alnum(gt)


def match_items(pred: list[dict], gt: list[dict]):
    used, tp = set(), 0
    for g in gt:
        for j, p in enumerate(pred):
            if j in used:
                continue
            if SequenceMatcher(None, alnum(p["description"]), alnum(g["description"])).ratio() >= 0.85 \
                    and all(p[k] is not None and abs(p[k] - g[k]) < 0.005 for k in ("quantity", "unit_price", "amount")):
                used.add(j); tp += 1
                break
    return tp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default="data/samples")
    ap.add_argument("--mode", default="rules")
    ap.add_argument("--threshold", type=float, default=0.85)
    ap.add_argument("--out", default="reports")
    a = ap.parse_args()

    files = sorted(Path(a.samples).glob("*.jpg"))
    rows, errors = [], []
    per_field = defaultdict(lambda: [0, 0])
    per_layout = defaultdict(lambda: [0, 0])
    flag_stats = {"fields": 0, "flagged": 0, "wrong": 0, "wrong_flagged": 0, "right_unflagged": 0, "unflagged": 0}
    li_tp = li_pred = li_gt = 0
    doc_all_ok = doc_clean_ok = docs_clean = docs_flagged = 0

    for f in files:
        gt = json.loads(f.with_suffix(".json").read_text())
        layout = gt["_meta"]["layout"]
        ext = extract_document(str(f), a.mode, a.threshold)
        all_ok = True
        for k in SCALAR_FIELDS:
            fr = getattr(ext, k)
            ok = field_correct(k, fr.value, gt[k])
            all_ok &= ok
            per_field[k][0] += ok; per_field[k][1] += 1
            per_layout[layout][0] += ok; per_layout[layout][1] += 1
            flag_stats["fields"] += 1
            flag_stats["flagged"] += fr.needs_review
            if not ok:
                flag_stats["wrong"] += 1; flag_stats["wrong_flagged"] += fr.needs_review
                errors.append((f.name, layout, k, gt[k], fr.value, fr.confidence, fr.needs_review, "; ".join(fr.reasons)))
            if not fr.needs_review:
                flag_stats["unflagged"] += 1; flag_stats["right_unflagged"] += ok
        pred_items = [i.model_dump() for i in ext.line_items]
        tp = match_items(pred_items, gt["line_items"])
        li_tp += tp; li_pred += len(pred_items); li_gt += len(gt["line_items"])
        items_ok = tp == len(gt["line_items"]) == len(pred_items)
        if not items_ok:
            errors.append((f.name, layout, "line_items", f"{len(gt['line_items'])} items",
                           f"{len(pred_items)} items, {tp} exact", "", ext.line_items_needs_review,
                           "; ".join(ext.line_items_reasons)))
        all_ok &= items_ok
        doc_all_ok += all_ok
        if not ext.needs_review:
            docs_clean += 1; doc_clean_ok += all_ok
        docs_flagged += ext.needs_review

    n = len(files)
    P = li_tp / li_pred if li_pred else 0; R = li_tp / li_gt if li_gt else 0
    F1 = 2 * P * R / (P + R) if P + R else 0
    m = {
        "mode": a.mode, "threshold": a.threshold, "n_documents": n,
        "field_accuracy": {k: v[0] / v[1] for k, v in per_field.items()},
        "scalar_macro_accuracy": sum(v[0] / v[1] for v in per_field.values()) / len(per_field),
        "scalar_micro_accuracy": sum(v[0] for v in per_field.values()) / sum(v[1] for v in per_field.values()),
        "line_items": {"precision": P, "recall": R, "f1": F1, "gt_items": li_gt, "pred_items": li_pred},
        "layout_accuracy": {k: v[0] / v[1] for k, v in per_layout.items()},
        "documents_fully_correct": doc_all_ok / n,
        "review": {
            "docs_flagged_pct": docs_flagged / n,
            "fields_flagged_pct": flag_stats["flagged"] / flag_stats["fields"],
            "error_recall": flag_stats["wrong_flagged"] / flag_stats["wrong"] if flag_stats["wrong"] else 1.0,
            "flag_precision": flag_stats["wrong_flagged"] / flag_stats["flagged"] if flag_stats["flagged"] else 0.0,
            "accuracy_unflagged_fields": flag_stats["right_unflagged"] / flag_stats["unflagged"] if flag_stats["unflagged"] else 0.0,
            "accuracy_unflagged_docs": doc_clean_ok / docs_clean if docs_clean else 0.0,
            "wrong_fields": flag_stats["wrong"], "wrong_and_flagged": flag_stats["wrong_flagged"],
        },
    }
    out = Path(a.out); out.mkdir(exist_ok=True)
    (out / f"metrics_{a.mode}.json").write_text(json.dumps(m, indent=2))
    write_md(out / f"accuracy_report_{a.mode}.md", m, errors)
    print(json.dumps(m, indent=2))


def pct(x): return f"{100 * x:.1f}%"


def write_md(path: Path, m: dict, errors: list):
    r = m["review"]
    L = [f"# Accuracy report - `{m['mode']}` extractor", "",
         f"Documents: **{m['n_documents']}** synthetic scanned invoices/receipts (3 layouts x varied degradation). "
         f"Review threshold: {m['threshold']}.", "",
         "## Field-level accuracy", "", "| Field | Accuracy |", "|---|---|"]
    L += [f"| {k} | {pct(v)} |" for k, v in m["field_accuracy"].items()]
    li = m["line_items"]
    L += [f"| **scalar fields (macro avg)** | **{pct(m['scalar_macro_accuracy'])}** |", "",
          f"**Line items** (strict: description >=85% similar AND qty, unit price, amount all exact): "
          f"precision {pct(li['precision'])}, recall {pct(li['recall'])}, F1 {pct(li['f1'])} "
          f"({li['gt_items']} ground-truth items).", "",
          f"**Documents with every field and every line item correct:** {pct(m['documents_fully_correct'])}", "",
          "## Accuracy by layout (scalar fields)", "", "| Layout | Accuracy |", "|---|---|"]
    L += [f"| {k} | {pct(v)} |" for k, v in m["layout_accuracy"].items()]
    L += ["", "## Human-review flagging", "",
          "| Metric | Value |", "|---|---|",
          f"| Documents flagged for review | {pct(r['docs_flagged_pct'])} |",
          f"| Scalar fields flagged | {pct(r['fields_flagged_pct'])} |",
          f"| **Error recall** (wrong fields that were flagged) | **{pct(r['error_recall'])}** ({r['wrong_and_flagged']}/{r['wrong_fields']}) |",
          f"| Flag precision (flagged fields that were wrong) | {pct(r['flag_precision'])} |",
          f"| Accuracy of fields NOT flagged | {pct(r['accuracy_unflagged_fields'])} |",
          f"| Accuracy of documents NOT flagged (all fields + items) | {pct(r['accuracy_unflagged_docs'])} |", "",
          "## Every error", "",
          "| File | Layout | Field | Expected | Got | Conf | Flagged | Reasons |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {e[0]} | {e[1]} | {e[2]} | {e[3]} | {e[4]} | {e[5]} | {'yes' if e[6] else '**NO**'} | {e[7]} |" for e in errors]
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
