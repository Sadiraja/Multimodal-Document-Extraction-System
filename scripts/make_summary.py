"""Combine dev + held-out metrics into reports/ACCURACY_REPORT.md"""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "reports"
sets = [("Dev set (`data/samples`, seed 7)", json.load(open(R / "metrics_rules.json"))),
        ("Held-out set (`data/heldout`, seed 99)", json.load(open(R / "heldout" / "metrics_rules.json")))]
p = lambda x: f"{100 * x:.1f}%"
fields = list(sets[0][1]["field_accuracy"])
L = ["# Accuracy report (offline OCR + rules extractor)", "",
     "Metrics are **field-level exact match** after light normalisation (case/punctuation-insensitive for text, "
     "+-0.005 for money, exact ISO date). A missing value counts as wrong.", "",
     "The dev set was used while building the pipeline (including choosing preprocessing). The held-out set was "
     "generated afterwards with a different seed and evaluated **once**, with no changes made after seeing it.", "",
     "| | " + " | ".join(n for n, _ in sets) + " |", "|---|" + "---|" * len(sets)]
L.append("| Documents | " + " | ".join(str(m["n_documents"]) for _, m in sets) + " |")
for f in fields:
    L.append(f"| {f} | " + " | ".join(p(m["field_accuracy"][f]) for _, m in sets) + " |")
L += ["| **Scalar fields, macro avg** | " + " | ".join(f"**{p(m['scalar_macro_accuracy'])}**" for _, m in sets) + " |",
      "| Line items F1 (strict) | " + " | ".join(p(m["line_items"]["f1"]) for _, m in sets) + " |",
      "| Line items precision / recall | " + " | ".join(f"{p(m['line_items']['precision'])} / {p(m['line_items']['recall'])}" for _, m in sets) + " |",
      "| Documents 100% correct | " + " | ".join(p(m["documents_fully_correct"]) for _, m in sets) + " |",
      "| **Human-review flagging** | | |",
      "| Documents flagged | " + " | ".join(p(m["review"]["docs_flagged_pct"]) for _, m in sets) + " |",
      "| Error recall (wrong fields caught) | " + " | ".join(f"{p(m['review']['error_recall'])} ({m['review']['wrong_and_flagged']}/{m['review']['wrong_fields']})" for _, m in sets) + " |",
      "| Flag precision | " + " | ".join(p(m["review"]["flag_precision"]) for _, m in sets) + " |",
      "| Accuracy of unflagged fields | " + " | ".join(p(m["review"]["accuracy_unflagged_fields"]) for _, m in sets) + " |",
      "| Accuracy of unflagged documents | " + " | ".join(p(m["review"]["accuracy_unflagged_docs"]) for _, m in sets) + " |", "",
      "Per-document error tables: `accuracy_report_rules.md` (dev) and `heldout/accuracy_report_rules.md`.", ""]
(R / "ACCURACY_REPORT.md").write_text("\n".join(L))
print("\n".join(L))
