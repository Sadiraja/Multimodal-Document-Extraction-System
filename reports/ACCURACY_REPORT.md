# Accuracy report (offline OCR + rules extractor)

Metrics are **field-level exact match** after light normalisation (case/punctuation-insensitive for text, +-0.005 for money, exact ISO date). A missing value counts as wrong.

The dev set was used while building the pipeline (including choosing preprocessing). The held-out set was generated afterwards with a different seed and evaluated **once**, with no changes made after seeing it.

| | Dev set (`data/samples`, seed 7) | Held-out set (`data/heldout`, seed 99) |
|---|---|---|
| Documents | 36 | 30 |
| invoice_number | 77.8% | 93.3% |
| date | 83.3% | 93.3% |
| vendor | 94.4% | 100.0% |
| currency | 97.2% | 96.7% |
| subtotal | 86.1% | 93.3% |
| tax | 83.3% | 93.3% |
| total | 97.2% | 96.7% |
| **Scalar fields, macro avg** | **88.5%** | **95.2%** |
| Line items F1 (strict) | 91.7% | 92.4% |
| Line items precision / recall | 96.5% / 87.3% | 97.8% / 87.5% |
| Documents 100% correct | 77.8% | 83.3% |
| **Human-review flagging** | | |
| Documents flagged | 44.4% | 26.7% |
| Error recall (wrong fields caught) | 96.6% (28/29) | 90.0% (9/10) |
| Flag precision | 63.6% | 56.2% |
| Accuracy of unflagged fields | 99.5% | 99.5% |
| Accuracy of unflagged documents | 100.0% | 100.0% |

Per-document error tables: `accuracy_report_rules.md` (dev) and `heldout/accuracy_report_rules.md`.
