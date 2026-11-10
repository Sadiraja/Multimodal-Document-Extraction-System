# Multimodal Document Extraction

Extract structured data (**invoice number, date, vendor, currency, subtotal, tax, total, line items**) from
scanned invoices and receipts. Output is **schema-validated JSON**, every field carries a **confidence score**,
and low-confidence or self-inconsistent fields are **flagged for human review**. Includes a **field-level
accuracy harness** run on 66 documents.

```
 image ──► preprocess ──► Tesseract OCR ──► ┌─ rules extractor (offline) ─┐
 (jpg/png)  deskew,denoise  words + conf     │                             ├─► IR ─► validate ─► Pydantic JSON
            multi-binarisation               └─ Claude vision (optional) ──┘     arithmetic, formats,   + review_queue.csv
                                                  grounded against OCR text         confidence, flags
```

## Quick start

```bash
sudo apt-get install tesseract-ocr          # macOS: brew install tesseract
pip install -r requirements.txt

python -m docextract.cli data/samples --out output        # whole folder, offline
python -m docextract.cli my_invoice.png --mode hybrid      # rules first, Claude only for flagged docs
```

`output/` receives one JSON per document plus `review_queue.csv` (file, field, value, confidence, reasons).

LLM modes need `export ANTHROPIC_API_KEY=...` (optionally `CLAUDE_MODEL`, default `claude-sonnet-5-5`).

| Mode | What it does | Needs API |
|---|---|---|
| `rules` | OCR + regex/heuristics + validation | no |
| `llm` | Claude vision via forced tool-call -> JSON; values grounded against OCR text | yes |
| `hybrid` | `rules` first; only documents that get flagged are sent to Claude, and the two readings are merged (agreement raises confidence, disagreement flags) | yes |

## Output

```json
{
  "invoice_number": {"value": "SI-2023-4622", "confidence": 0.81, "needs_review": true, "reasons": []},
  "date":           {"value": "2024-08-22",   "confidence": 0.96, "needs_review": false, "reasons": []},
  "total":          {"value": 812.41,         "confidence": 0.95, "needs_review": false, "reasons": []},
  "line_items": [{"description": "A4 paper ream", "quantity": 2.0, "unit_price": 20.8, "amount": 41.6, "confidence": 0.947}],
  "line_items_needs_review": false,
  "needs_review": true
}
```
(full examples in `examples/`; `doc_004_receipt.json` shows an OCR digit error being caught by the arithmetic check)

## How confidence and flagging work

OCR confidence alone is a weak signal; **arithmetic is a strong one**. Confidence is built in layers (`docextract/validate.py`):

1. **Source confidence** - mean Tesseract confidence of the words that make up the value (rules), or the model's own
   confidence capped and **grounded**: an LLM value that cannot be found in independent OCR text is multiplied by 0.7.
2. **Cross-field checks** - `subtotal + tax == total`, `sum(line amounts) == subtotal`, `qty x unit_price == amount`.
   If an identity holds, several independently-read numbers agree, so confidence is raised to >=0.92. If it fails,
   at least one number is wrong, so *every field involved* is multiplied by 0.6 and flagged.
3. **Format/plausibility** - ISO date, year range (catches `2075`), identifier shape, ambiguous `03/04/2024`
   (day/month order) is explicitly down-weighted.
4. **Flag** if confidence < threshold (default 0.85), value missing, or any check failed.

Output is parsed through Pydantic (`docextract/schema.py`); malformed dates etc. raise instead of being emitted.

## Evaluation

`scripts/generate_samples.py` creates synthetic documents with ground truth: 3 layouts (table invoice, thermal
receipt, serif VAT invoice in GBP), varied label wording and date formats, then scan-style degradation (rotation
+-2.5 deg, blur, noise, uneven lighting, JPEG artefacts, down to 55% resolution).
`scripts/evaluate.py` scores field-level exact match. Full tables: [`reports/ACCURACY_REPORT.md`](reports/ACCURACY_REPORT.md).

| Offline `rules` extractor | Dev set (36 docs) | Held-out (30 docs) |
|---|---|---|
| invoice_number / date / vendor | 77.8% / 83.3% / 94.4% | 93.3% / 93.3% / 100% |
| currency / subtotal / tax / total | 97.2% / 86.1% / 83.3% / 97.2% | 96.7% / 93.3% / 93.3% / 96.7% |
| **Scalar macro accuracy** | **88.5%** | **95.2%** |
| Line items F1 (strict) | 91.7% | 92.4% |
| Documents 100% correct | 77.8% | 83.3% |
| **Error recall** (wrong fields that got flagged) | **96.6%** | **90.0%** |
| Accuracy of fields *not* flagged | 99.5% | 99.5% |
| Documents sent to review | 44% | 27% |

The practical reading: **auto-accepting unflagged fields is ~99.5% accurate, and no unflagged document had any
error**, while ~27-44% of documents go to a human. The dev set was used while tuning (e.g. choosing to run several
binarisations and keep the one the validators trust most: +7 points on scalar accuracy); the held-out set was run
once afterwards. The difference between the sets is mostly random degradation severity, so treat +-5 points as noise
with sets this small.

Reproduce: `python scripts/evaluate.py --samples data/samples --out reports` (~1-2 min, CPU).
Also works with `--mode hybrid` / `--mode llm` once an API key is set.

## Known limitations (read before trusting the numbers)

- **Documents are synthetic.** Layouts, fonts and label vocabulary are known to the generator, and the rules extractor
  was written with them in view. Real-world accuracy of `rules` will be lower; it is a strong offline baseline,
  not a general solution. Use `hybrid`/`llm` for diverse real documents and re-run `evaluate.py` on a labelled sample of yours.
- **`llm`/`hybrid` modes were implemented but not executed in my build environment (no API key), so no accuracy
  numbers are claimed for them.** Run the evaluator to get yours.
- Remaining errors are dominated by very low-resolution scans (OCR drops or garbles characters). They are mostly
  *flagged* rather than silently wrong; the exceptions are listed per document in the error tables
  (e.g. a `GBP` doc read as `USD`, a one-character vendor typo, a date month misread).
- Single-page, English, images only (PDF -> image conversion is not included). Line items require the
  `desc qty price amount` or `qty x price amount` shapes in `rules` mode.
- Day/month order is assumed US (`MM/DD`) when ambiguous and flagged.

## Layout

```
docextract/  ocr.py (preprocess+Tesseract)  rules.py  llm.py  validate.py  schema.py  pipeline.py  cli.py
scripts/     generate_samples.py  evaluate.py  make_summary.py
data/        samples/ (36 docs + ground truth)   heldout/ (30 docs + ground truth)
reports/     ACCURACY_REPORT.md  accuracy_report_rules.md  heldout/...  metrics*.json
examples/    sample JSON outputs        tests/  unit tests (pytest)
```

## Extending

Add a field: schema (`schema.py`) -> extractor (`rules.py` / LLM tool schema in `llm.py`) -> add a check in `validate.py`
-> ground truth in the generator. Tune review load vs. risk with `--threshold`.
