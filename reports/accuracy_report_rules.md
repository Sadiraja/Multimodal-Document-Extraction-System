# Accuracy report - `rules` extractor

Documents: **36** synthetic scanned invoices/receipts (3 layouts x varied degradation). Review threshold: 0.85.

## Field-level accuracy

| Field | Accuracy |
|---|---|
| invoice_number | 77.8% |
| date | 83.3% |
| vendor | 94.4% |
| currency | 97.2% |
| subtotal | 86.1% |
| tax | 83.3% |
| total | 97.2% |
| **scalar fields (macro avg)** | **88.5%** |

**Line items** (strict: description >=85% similar AND qty, unit price, amount all exact): precision 96.5%, recall 87.3%, F1 91.7% (126 ground-truth items).

**Documents with every field and every line item correct:** 77.8%

## Accuracy by layout (scalar fields)

| Layout | Accuracy |
|---|---|
| invoice | 91.7% |
| receipt | 79.8% |
| vat | 94.0% |

## Human-review flagging

| Metric | Value |
|---|---|
| Documents flagged for review | 44.4% |
| Scalar fields flagged | 17.5% |
| **Error recall** (wrong fields that were flagged) | **96.6%** (28/29) |
| Flag precision (flagged fields that were wrong) | 63.6% |
| Accuracy of fields NOT flagged | 99.5% |
| Accuracy of documents NOT flagged (all fields + items) | 100.0% |

## Every error

| File | Layout | Field | Expected | Got | Conf | Flagged | Reasons |
|---|---|---|---|---|---|---|---|
| doc_004_receipt.jpg | receipt | invoice_number | INV472030 | IMv372039 | 0.0 | yes |  |
| doc_004_receipt.jpg | receipt | subtotal | 2266.34 | 2265.34 | 0.232 | yes | arithmetic mismatch: 2265.34 + 169.93 != 2436.32; line items sum to 2266.34 |
| doc_004_receipt.jpg | receipt | tax | 169.98 | 169.93 | 0.57 | yes | arithmetic mismatch: 2265.34 + 169.93 != 2436.32 |
| doc_006_invoice.jpg | invoice | invoice_number | INV117119 | None | 0.0 | yes | not found |
| doc_006_invoice.jpg | invoice | date | 2023-03-24 | 2025-04-23 | 0.833 | yes |  |
| doc_006_invoice.jpg | invoice | subtotal | 2254.51 | None | 0.0 | yes | not found |
| doc_006_invoice.jpg | invoice | tax | 180.36 | None | 0.0 | yes | not found |
| doc_006_invoice.jpg | invoice | line_items | 3 items | 2 items, 1 exact |  | **NO** |  |
| doc_007_receipt.jpg | receipt | invoice_number | INV-2023-3785 | None | 0.0 | yes | not found |
| doc_007_receipt.jpg | receipt | date | 2024-02-16 | None | 0.0 | yes | not found |
| doc_007_receipt.jpg | receipt | vendor | Blue Harbor Logistics | 6BLUE HARBOR LOGISTICS | 0.627 | yes |  |
| doc_007_receipt.jpg | receipt | subtotal | 1359.12 | 9.12 | 0.396 | yes | arithmetic mismatch: 9.12 + 235.93 != 1495.03 |
| doc_007_receipt.jpg | receipt | tax | 135.91 | 235.93 | 0.48 | yes | arithmetic mismatch: 9.12 + 235.93 != 1495.03 |
| doc_007_receipt.jpg | receipt | line_items | 2 items | 0 items, 0 exact |  | yes | no line items found |
| doc_013_receipt.jpg | receipt | invoice_number | R714807 | None | 0.0 | yes | not found |
| doc_013_receipt.jpg | receipt | date | 2024-04-01 | None | 0.0 | yes | not found |
| doc_013_receipt.jpg | receipt | vendor | Sunrise Bakery | SUNRISE BAXERY | 0.855 | **NO** |  |
| doc_013_receipt.jpg | receipt | subtotal | 581.37 | None | 0.0 | yes | not found |
| doc_013_receipt.jpg | receipt | tax | 46.51 | None | 0.0 | yes | not found |
| doc_013_receipt.jpg | receipt | line_items | 4 items | 1 items, 0 exact |  | yes | Cscresso tests 333: qty x unit_price != amount |
| doc_016_receipt.jpg | receipt | invoice_number | INV-2023-8763 | None | 0.0 | yes | not found |
| doc_016_receipt.jpg | receipt | date | 2024-07-02 | None | 0.0 | yes | not found |
| doc_016_receipt.jpg | receipt | tax | 17.16 | None | 0.0 | yes | not found |
| doc_016_receipt.jpg | receipt | line_items | 2 items | 2 items, 0 exact |  | yes | line items sum to 85.92 but subtotal is 85.81; Wireless rouse: qty x unit_price != amount |
| doc_017_vat.jpg | vat | invoice_number | SI-2023-8959 | None | 0.0 | yes | not found |
| doc_017_vat.jpg | vat | date | 2023-01-13 | 2075-01-13 | 0.482 | yes | implausible date (year out of range) |
| doc_017_vat.jpg | vat | currency | GBP | USD | 0.6 | yes | currency symbol evidence weak |
| doc_017_vat.jpg | vat | subtotal | 3360.62 | None | 0.0 | yes | not found |
| doc_017_vat.jpg | vat | total | 4032.74 | None | 0.0 | yes | not found |
| doc_017_vat.jpg | vat | line_items | 2 items | 0 items, 0 exact |  | yes | no line items found |
| doc_028_receipt.jpg | receipt | invoice_number | SI-2024-1661 | None | 0.0 | yes | not found |
| doc_033_invoice.jpg | invoice | invoice_number | 860389 | None | 0.0 | yes | not found |
| doc_033_invoice.jpg | invoice | date | 2024-05-18 | 2024-05-16 | 0.69 | yes |  |
| doc_033_invoice.jpg | invoice | tax | 88.4 | None | 0.0 | yes | not found |
| doc_033_invoice.jpg | invoice | line_items | 5 items | 1 items, 1 exact |  | yes | line items sum to 187.0 but subtotal is 1178.68 |
