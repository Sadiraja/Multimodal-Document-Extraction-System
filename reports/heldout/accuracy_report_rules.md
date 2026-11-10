# Accuracy report - `rules` extractor

Documents: **30** synthetic scanned invoices/receipts (3 layouts x varied degradation). Review threshold: 0.85.

## Field-level accuracy

| Field | Accuracy |
|---|---|
| invoice_number | 93.3% |
| date | 93.3% |
| vendor | 100.0% |
| currency | 96.7% |
| subtotal | 93.3% |
| tax | 93.3% |
| total | 96.7% |
| **scalar fields (macro avg)** | **95.2%** |

**Line items** (strict: description >=85% similar AND qty, unit price, amount all exact): precision 97.8%, recall 87.5%, F1 92.4% (104 ground-truth items).

**Documents with every field and every line item correct:** 83.3%

## Accuracy by layout (scalar fields)

| Layout | Accuracy |
|---|---|
| invoice | 95.7% |
| receipt | 98.6% |
| vat | 91.4% |

## Human-review flagging

| Metric | Value |
|---|---|
| Documents flagged for review | 26.7% |
| Scalar fields flagged | 7.6% |
| **Error recall** (wrong fields that were flagged) | **90.0%** (9/10) |
| Flag precision (flagged fields that were wrong) | 56.2% |
| Accuracy of fields NOT flagged | 99.5% |
| Accuracy of documents NOT flagged (all fields + items) | 100.0% |

## Every error

| File | Layout | Field | Expected | Got | Conf | Flagged | Reasons |
|---|---|---|---|---|---|---|---|
| doc_000_invoice.jpg | invoice | invoice_number | INV-2024-6183 | 2074 | 0.81 | yes |  |
| doc_000_invoice.jpg | invoice | subtotal | 3178.19 | None | 0.0 | yes | not found |
| doc_000_invoice.jpg | invoice | tax | 158.91 | None | 0.0 | yes | not found |
| doc_000_invoice.jpg | invoice | line_items | 5 items | 0 items, 0 exact |  | yes | no line items found |
| doc_009_invoice.jpg | invoice | line_items | 3 items | 3 items, 2 exact |  | yes | line items sum to 2838.91 but subtotal is 2858.91; Wireless mouse: qty x unit_price != amount |
| doc_011_vat.jpg | vat | invoice_number | 185996 | None | 0.0 | yes | not found |
| doc_011_vat.jpg | vat | date | 2023-06-26 | None | 0.0 | yes | not found |
| doc_011_vat.jpg | vat | currency | GBP | USD | 0.9 | **NO** |  |
| doc_011_vat.jpg | vat | subtotal | 872.26 | None | 0.0 | yes | not found |
| doc_011_vat.jpg | vat | tax | 174.45 | None | 0.0 | yes | not found |
| doc_011_vat.jpg | vat | total | 1046.71 | None | 0.0 | yes | not found |
| doc_011_vat.jpg | vat | line_items | 3 items | 0 items, 0 exact |  | yes | no line items found |
| doc_016_receipt.jpg | receipt | date | 2023-09-16 | 2623-09-16 | 0.486 | yes | implausible date (year out of range) |
| doc_016_receipt.jpg | receipt | line_items | 3 items | 0 items, 0 exact |  | yes | no line items found |
| doc_024_invoice.jpg | invoice | line_items | 5 items | 5 items, 4 exact |  | yes | Safety gloves pair: qty x unit_price != amount |
