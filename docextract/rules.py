"""Offline extractor: regex/heuristics over OCR lines. No network, no API key.

Returns the intermediate representation (IR) consumed by validate.finalize():
    {"fields": {name: {"value", "conf", "reasons"}}, "line_items": [{...,"conf"}]}
"""
from __future__ import annotations

import re
from datetime import date

from .ocr import Line

MONEY = r"\d[\d,]*\.\d{2}"
MONEY_RE = re.compile(MONEY)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_money(s: str) -> float:
    return float(s.replace(",", ""))


def _tok_conf(line: Line, text: str) -> float:
    """Mean OCR confidence of the words in `line` that make up `text`."""
    toks = text.split()
    hits = [w.conf for w in line.words if any(w.text in t or t in w.text for t in toks)]
    return sum(hits) / len(hits) if hits else line.conf


def _field(value, conf, reasons=None):
    return {"value": value, "conf": float(conf), "reasons": reasons or []}


# ---------------------------------------------------------------- dates
def parse_date(text: str):
    """Returns (iso, matched_text, ambiguous) or None."""
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        y, mo, d = map(int, m.groups())
        return _mk(y, mo, d, m.group(0), False)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if m:
        a, b, y = map(int, m.groups())
        if a > 12:                       # unambiguously DD/MM
            return _mk(y, b, a, m.group(0), False)
        return _mk(y, a, b, m.group(0), a != b and b <= 12)   # assume US MM/DD, flag if ambiguous
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", text)
    if m and m.group(1)[:3].lower() in MONTHS:
        return _mk(int(m.group(3)), MONTHS[m.group(1)[:3].lower()], int(m.group(2)), m.group(0), False)
    m = re.search(r"\b(\d{1,2})[ \-]([A-Za-z]{3,9})\.?[ \-,]+(\d{4})\b", text)
    if m and m.group(2)[:3].lower() in MONTHS:
        return _mk(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1)), m.group(0), False)
    return None


def _mk(y, mo, d, raw, amb):
    try:
        return date(y, mo, d).isoformat(), raw, amb
    except ValueError:
        return None


# ------------------------------------------------------------ main entry
INV_RE = re.compile(r"(?i)\b(?:invoice|inv|receipt|rcpt)\s*(?:number|num\.?|no\.?|#)?\s*[:#.]*\s*"
                    r"([A-Za-z0-9][A-Za-z0-9\-/]{2,})")
SUB_RE = re.compile(r"(?i)\b(sub\s*-?\s*total|net\s+total|net\s+amount)\b")
TOT_RE = re.compile(r"(?i)\b(grand\s+total|amount\s+due|balance\s+due|total\s+due|total)\b")
TAX_RE = re.compile(r"(?i)\b(tax|vat|gst)\b")
ROW_TABLE = re.compile(rf"^(?P<d>.*?[A-Za-z].*?)\s+(?P<q>\d{{1,4}})\s+\W?\s?(?P<p>{MONEY})\s+\W?\s?(?P<a>{MONEY})\s*\W?$")
ROW_RCPT = re.compile(rf"^\W*(?P<q>\d+(?:\.\d+)?)\s*[xX\u00d7]\s*\W?(?P<p>{MONEY})\s+\W?(?P<a>{MONEY})\s*$")
DOCWORDS = re.compile(r"(?i)^\W*(tax\s+)?(invoice|receipt)\W*$")


def extract(lines: list[Line]) -> dict:
    F: dict = {}
    text = "\n".join(l.text for l in lines)

    # vendor: first substantive line that is not just a document title
    vendor = None
    for l in lines[:6]:
        clean = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.)]+$", "", l.text)
        if len(re.sub(r"[^A-Za-z]", "", clean)) >= 3 and not DOCWORDS.match(clean):
            vendor = _field(clean, l.conf)
            break
    F["vendor"] = vendor or _field(None, 0.0, ["not found"])

    # invoice number
    F["invoice_number"] = _field(None, 0.0, ["not found"])
    for l in lines:
        for m in INV_RE.finditer(l.text):
            tok = m.group(1)
            if any(c.isdigit() for c in tok):
                F["invoice_number"] = _field(tok, _tok_conf(l, tok))
                break
        else:
            continue
        break

    # date (first non-"due" date, top to bottom)
    F["date"] = _field(None, 0.0, ["not found"])
    for l in lines:
        if re.search(r"(?i)\bdue\b", l.text):
            continue
        r = parse_date(l.text)
        if r:
            iso, raw, amb = r
            F["date"] = _field(iso, _tok_conf(l, raw) * (0.7 if amb else 1.0),
                               ["ambiguous day/month order (assumed MM/DD)"] if amb else [])
            break

    # currency: code wins; otherwise majority vote over symbols (one misread glyph must not decide)
    cur = None
    m = re.search(r"\b(USD|GBP|EUR|CAD|AUD|INR|PKR)\b", text)
    if m:
        cur = _field(m.group(1), 0.9)
    else:
        counts = sorted(((text.count(sym), code) for sym, code in
                         (("\u00a3", "GBP"), ("\u20ac", "EUR"), ("$", "USD"))), reverse=True)
        if counts[0][0] > 0:
            top, second = counts[0], counts[1]
            # "$" is shared by USD/CAD/AUD, hence not 1.0
            cur = _field(top[1], 0.88 if top[0] >= 3 and top[0] >= 2 * second[0] else 0.6,
                         [] if top[0] >= 3 and top[0] >= 2 * second[0] else ["currency symbol evidence weak"])
    F["currency"] = cur or _field(None, 0.0, ["not found"])

    # money fields from labelled lines
    sub_idx = None
    for name, rx, pick_last in (("subtotal", SUB_RE, False), ("tax", TAX_RE, False), ("total", TOT_RE, True)):
        F[name] = _field(None, 0.0, ["not found"])
        hits = []
        for i, l in enumerate(lines):
            if name == "total" and (SUB_RE.search(l.text) or re.search(r"(?i)line\s+total", l.text)):
                continue
            mm = rx.search(l.text)
            amts = MONEY_RE.findall(l.text)
            if mm and amts:
                hits.append((i, l, mm.group(1), amts[-1]))
        if hits:
            i, l, lab, amt = hits[-1] if pick_last else hits[0]
            F[name] = _field(parse_money(amt), (_tok_conf(l, lab) + _tok_conf(l, amt)) / 2)
            if name == "subtotal":
                sub_idx = i

    # line items: everything above the first totals line
    end = sub_idx if sub_idx is not None else len(lines)
    items, i = [], 0
    while i < end:
        l = lines[i]
        m = ROW_TABLE.match(l.text)
        if m:
            items.append({"description": m["d"].strip(), "quantity": float(m["q"]),
                          "unit_price": parse_money(m["p"]), "amount": parse_money(m["a"]), "conf": l.conf})
        else:
            m = ROW_RCPT.match(l.text)
            if m and i > 0:
                prev = lines[i - 1]
                desc = re.sub(r"^\W+|\W+$", "", prev.text)
                items.append({"description": desc, "quantity": float(m["q"]),
                              "unit_price": parse_money(m["p"]), "amount": parse_money(m["a"]),
                              "conf": (l.conf + prev.conf) / 2})
        i += 1
    return {"fields": F, "line_items": items}
