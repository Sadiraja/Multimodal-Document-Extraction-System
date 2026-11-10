import pytest

from docextract import rules, validate
from docextract.ocr import Line, Word
from docextract.schema import Extraction, FieldResult


def mkline(text, conf=0.95, y=0):
    return Line([Word(t, conf, i * 50, y, 40, 10) for i, t in enumerate(text.split())])


def test_parse_money():
    assert rules.parse_money("1,234.50") == 1234.5


@pytest.mark.parametrize("s,iso", [
    ("Date: 2024-03-14", "2024-03-14"), ("Mar 14, 2024", "2024-03-14"),
    ("14 March 2024", "2024-03-14"), ("14-Mar-2024", "2024-03-14"), ("03/14/2024", "2024-03-14"),
    ("14/03/2024", "2024-03-14")])
def test_parse_date(s, iso):
    assert rules.parse_date(s)[0] == iso


def test_ambiguous_date_is_flagged():
    iso, _, amb = rules.parse_date("03/04/2024")
    assert amb
    ir = rules.extract([mkline("Acme Corp"), mkline("Date: 03/04/2024")])
    assert ir["fields"]["date"]["conf"] < 0.85


def test_rules_extract_table_invoice():
    lines = [mkline("Acme Supply"), mkline("INVOICE"), mkline("Invoice No: INV-2024-0412"),
             mkline("Date: 2024-03-14"), mkline("Due Date: 2024-04-13"),
             mkline("Description Qty Unit Price Amount"),
             mkline("Copper pipe 15mm 2 $10.00 $20.00"),
             mkline("Subtotal: $20.00"), mkline("Tax (10%): $2.00"), mkline("Total: $22.00")]
    ir = rules.extract(lines)["fields"]
    assert ir["vendor"]["value"] == "Acme Supply"
    assert ir["invoice_number"]["value"] == "INV-2024-0412"
    assert ir["date"]["value"] == "2024-03-14"          # not the due date
    assert (ir["subtotal"]["value"], ir["tax"]["value"], ir["total"]["value"]) == (20.0, 2.0, 22.0)


def _ir(sub, tax, tot, items):
    f = lambda v: {"value": v, "conf": 0.9, "reasons": []}
    return {"fields": {"invoice_number": f("INV-1234"), "date": f("2024-01-01"), "vendor": f("Acme"),
                       "currency": f("USD"), "subtotal": f(sub), "tax": f(tax), "total": f(tot)},
            "line_items": items}


ITEM = {"description": "x", "quantity": 2.0, "unit_price": 10.0, "amount": 20.0, "conf": 0.8}


def test_consistent_arithmetic_raises_confidence():
    e = validate.finalize(_ir(20.0, 2.0, 22.0, [ITEM]))
    assert e.total.confidence >= 0.9 and not e.needs_review


def test_arithmetic_mismatch_flags_money_fields():
    e = validate.finalize(_ir(20.0, 2.0, 99.0, [ITEM]))
    assert e.total.needs_review and e.subtotal.needs_review and e.needs_review


def test_line_item_sum_mismatch_flags():
    e = validate.finalize(_ir(50.0, 5.0, 55.0, [ITEM]))
    assert e.line_items_needs_review and e.subtotal.needs_review


def test_missing_field_flagged():
    ir = _ir(20.0, 2.0, 22.0, [ITEM]); ir["fields"]["invoice_number"] = {"value": None, "conf": 0, "reasons": []}
    assert validate.finalize(ir).invoice_number.needs_review


def test_schema_rejects_bad_date():
    ok = FieldResult(value="x", confidence=1, needs_review=False)
    with pytest.raises(ValueError):
        Extraction(invoice_number=ok, date=FieldResult(value="14/03/2024", confidence=1), vendor=ok,
                   currency=ok, subtotal=ok, tax=ok, total=ok)
