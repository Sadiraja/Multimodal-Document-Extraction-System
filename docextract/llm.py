"""Claude vision extractor. Requires ANTHROPIC_API_KEY (and `pip install anthropic`).

The model is forced to answer through a tool call, so the output is already structured JSON;
it is then validated by Pydantic and cross-checked against OCR text (grounding) in pipeline.py.
"""
from __future__ import annotations

import base64
import mimetypes
import os

SYSTEM = (
    "You extract structured data from scanned invoices and receipts. Read the image carefully. "
    "Return null for anything not visibly present - never guess or infer values. Dates must be ISO "
    "YYYY-MM-DD (if day/month order is ambiguous, say so in `note` and lower confidence). Money values are "
    "plain numbers without currency symbols or thousands separators. `confidence` is your honest probability (0-1) "
    "that the value is exactly right; lower it for blur, smudges, handwriting, or ambiguity."
)

_scalar = lambda t: {"type": "object", "properties": {
    "value": {"type": [t, "null"]}, "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "note": {"type": "string"}}, "required": ["value", "confidence"]}

TOOL = {
    "name": "record_document",
    "description": "Record the fields extracted from the document.",
    "input_schema": {"type": "object", "properties": {
        "invoice_number": _scalar("string"), "date": _scalar("string"), "vendor": _scalar("string"),
        "currency": _scalar("string"), "subtotal": _scalar("number"), "tax": _scalar("number"),
        "total": _scalar("number"),
        "line_items": {"type": "array", "items": {"type": "object", "properties": {
            "description": {"type": "string"}, "quantity": {"type": ["number", "null"]},
            "unit_price": {"type": ["number", "null"]}, "amount": {"type": ["number", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
            "required": ["description", "confidence"]}}},
        "required": ["invoice_number", "date", "vendor", "currency", "subtotal", "tax", "total", "line_items"]},
}


def extract(image_path: str, model: str | None = None) -> dict:
    import anthropic  # imported lazily so rules mode needs no SDK

    media = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    data = base64.standard_b64encode(open(image_path, "rb").read()).decode()
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=2000, system=SYSTEM, tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
            {"type": "text", "text": "Extract all fields from this document."}]}])
    block = next(b for b in resp.content if b.type == "tool_use")
    raw = block.input
    fields = {k: {"value": raw[k].get("value"), "conf": float(raw[k].get("confidence", 0.0)),
                  "reasons": [raw[k]["note"]] if raw[k].get("note") else []}
              for k in ("invoice_number", "date", "vendor", "currency", "subtotal", "tax", "total")}
    items = [{"description": i["description"], "quantity": i.get("quantity"), "unit_price": i.get("unit_price"),
              "amount": i.get("amount"), "conf": float(i.get("confidence", 0.0))} for i in raw.get("line_items", [])]
    return {"fields": fields, "line_items": items}
