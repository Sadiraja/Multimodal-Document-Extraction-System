"""Cross-field validation + confidence calibration + review flagging.

Key idea: OCR/LLM confidence alone is a weak signal, but arithmetic is a strong one.
If subtotal + tax == total and sum(line items) == subtotal, three or more independently
read numbers agree, so the chance they are all wrong is negligible -> confidence is raised.
If the arithmetic fails, at least one number is wrong -> every field involved is penalised and flagged.
"""
from __future__ import annotations

import re
from datetime import date

from .schema import Extraction, FieldResult, LineItem, SCALAR_FIELDS, MONEY_FIELDS

TOL = 0.011
CONSISTENT_FLOOR = 0.92   # confidence floor when an arithmetic identity holds
MISMATCH_FACTOR = 0.6


def _close(a, b, tol=TOL):
    return a is not None and b is not None and abs(a - b) <= tol


def finalize(ir: dict, threshold: float = 0.85, source_file: str = "", extractor: str = "") -> Extraction:
    F = {k: dict(v) for k, v in ir["fields"].items()}
    for k in SCALAR_FIELDS:
        F.setdefault(k, {"value": None, "conf": 0.0, "reasons": ["not found"]})
        F[k]["reasons"] = list(F[k].get("reasons", []))
    items = [dict(i) for i in ir.get("line_items", [])]
    for it in items:
        it["reasons"] = []

    def penalise(name, why):
        F[name]["conf"] *= MISMATCH_FACTOR
        F[name]["reasons"].append(why)

    def support(name):
        F[name]["conf"] = max(F[name]["conf"], CONSISTENT_FLOOR) if F[name]["value"] is not None else 0.0

    # --- format sanity checks
    inv = F["invoice_number"]["value"]
    if inv is not None and not re.fullmatch(r"(?=.*\d)[A-Za-z0-9\-/]{3,25}", str(inv)):
        penalise("invoice_number", "implausible identifier format")

    d = F["date"]["value"]
    if d is not None and not (1990 <= int(str(d)[:4]) <= date.today().year + 1):
        penalise("date", "implausible date (year out of range)")

    sub, tax, tot = (F[k]["value"] for k in ("subtotal", "tax", "total"))

    # --- subtotal + tax == total
    if None not in (sub, tax, tot):
        if _close(sub + tax, tot):
            for k in ("subtotal", "tax", "total"):
                support(k)
        else:
            for k in ("subtotal", "tax", "total"):
                penalise(k, f"arithmetic mismatch: {sub} + {tax} != {tot}")

    # --- per-item qty * unit_price == amount
    for it in items:
        if None not in (it.get("quantity"), it.get("unit_price"), it.get("amount")):
            if _close(it["quantity"] * it["unit_price"], it["amount"], 0.02):
                it["conf"] = max(it["conf"], CONSISTENT_FLOOR)
            else:
                it["conf"] *= MISMATCH_FACTOR
                it["reasons"].append("qty x unit_price != amount")
        else:
            it["conf"] *= 0.5
            it["reasons"].append("missing numeric field")

    # --- sum(line items) == subtotal
    li_reasons: list[str] = []
    if items and sub is not None:
        s = round(sum(i["amount"] or 0 for i in items), 2)
        if _close(s, sub, 0.02):
            support("subtotal")
            for it in items:
                if not it["reasons"]:
                    it["conf"] = max(it["conf"], CONSISTENT_FLOOR)
        else:
            li_reasons.append(f"line items sum to {s} but subtotal is {sub}")
            penalise("subtotal", f"line items sum to {s}")
    elif not items:
        li_reasons.append("no line items found")

    # --- build typed result
    out = {}
    for k in SCALAR_FIELDS:
        c = round(min(max(F[k]["conf"], 0.0), 1.0), 3)
        reasons = F[k]["reasons"]
        flag = c < threshold or F[k]["value"] is None or any(
            r.startswith(("arithmetic", "line items", "extractors disagree", "implausible")) for r in reasons)
        v = F[k]["value"]
        if k in MONEY_FIELDS and v is not None:
            v = round(float(v), 2)
        out[k] = FieldResult(value=v, confidence=c, needs_review=flag, reasons=reasons)

    li = [LineItem(description=i["description"], quantity=i.get("quantity"), unit_price=i.get("unit_price"),
                   amount=i.get("amount"), confidence=round(min(i["conf"], 1.0), 3)) for i in items]
    for it, raw in zip(li, items):
        if raw["reasons"]:
            li_reasons.append(f"{it.description}: " + "; ".join(raw["reasons"]))
    li_flag = bool(li_reasons) or any(i.confidence < threshold for i in li)
    if any(i.confidence < threshold for i in li) and not li_reasons:
        li_reasons.append(f"item confidence below {threshold}")

    ext = Extraction(**out, line_items=li, line_items_needs_review=li_flag, line_items_reasons=li_reasons,
                     needs_review=li_flag or any(f.needs_review for f in out.values()),
                     source_file=source_file, extractor=extractor)
    return ext
