"""Generate synthetic scanned invoices/receipts + ground-truth JSON.

Three layouts (table invoice, thermal receipt, serif/VAT invoice) with varied label wording,
date formats and currencies, then degraded to look scanned: rotation, blur, noise, tinted
paper, uneven lighting, JPEG artefacts, reduced resolution.

    python scripts/generate_samples.py --n 36 --out data/samples
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
F = lambda name, size: ImageFont.truetype(FONT_DIR + name, size)

VENDORS = ["Acme Industrial Supply", "Brightwater Coffee Co", "Northwind Traders", "Pinecrest Hardware",
           "Blue Harbor Logistics", "Sunrise Bakery", "Greenleaf Organics", "Summit Office Products",
           "Orion Electronics", "Maple Street Printing", "Redwood Consulting", "Cobalt Cloud Services",
           "Lakeside Pharmacy", "Harvest Moon Farms", "Ironclad Tools Ltd", "Silverline Travel",
           "Quantum Parts Inc", "Bluebird Stationery", "Evergreen Landscaping", "Atlas Freight Group"]
ITEMS = ["Copper pipe 15mm", "Ceramic mug", "USB-C cable 2m", "Printer toner black", "A4 paper ream",
         "Consulting hour", "Hex bolt M8 box", "Espresso beans 1kg", "Cleaning service", "LED desk lamp",
         "Cat6 patch cable", "Shipping surcharge", "Hand soap 5L", "Safety gloves pair", "Wireless mouse",
         "Cloud storage plan", "Sourdough loaf", "Organic apples 2kg", "Label stickers roll", "Paint brush set",
         "Monitor stand", "Notebook pack of 5", "Whiteboard markers", "Steel shelf bracket", "Data backup fee"]
STREETS = ["12 Market Street", "88 Industrial Way", "301 Harbor Road", "5 Elm Avenue", "47 Cedar Lane"]
CITIES = ["Springfield", "Rivertown", "Lakeview", "Oakdale", "Fairmont"]


def money(x: float) -> str:
    return f"{x:,.2f}"


def make_truth(rng: random.Random, tmpl: str) -> dict:
    n = rng.randint(2, 6) if tmpl != "receipt" else rng.randint(2, 5)
    items = []
    for desc in rng.sample(ITEMS, n):
        qty = rng.randint(1, 12)
        price = round(rng.choice([rng.uniform(1.5, 25), rng.uniform(25, 480)]), 2)
        items.append({"description": desc, "quantity": float(qty), "unit_price": price,
                      "amount": round(qty * price, 2)})
    sub = round(sum(i["amount"] for i in items), 2)
    rate = rng.choice([0.05, 0.075, 0.08, 0.10, 0.20]) if tmpl != "vat" else 0.20
    tax = round(sub * rate, 2)
    d = date(2023, 1, 1) + timedelta(days=rng.randint(0, 700))
    prefix = rng.choice(["INV-", "INV", "", "SI-", "R"])
    num = f"{prefix}{rng.choice([2023, 2024])}-{rng.randint(1000, 9999)}" if prefix in ("INV-", "SI-") \
        else f"{prefix}{rng.randint(10000, 999999)}"
    return {"invoice_number": num, "date": d.isoformat(), "vendor": rng.choice(VENDORS),
            "currency": "GBP" if tmpl == "vat" else "USD", "subtotal": sub, "tax": tax,
            "total": round(sub + tax, 2), "line_items": items, "_rate": rate, "_layout": tmpl}


def render_invoice(t: dict, rng: random.Random) -> Image.Image:
    W, H = 1240, 1000 + 70 * len(t["line_items"])
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    d.text((60, 50), t["vendor"], font=F("DejaVuSans-Bold.ttf", 44), fill="black")
    d.text((60, 110), f"{rng.choice(STREETS)}, {rng.choice(CITIES)}", font=F("DejaVuSans.ttf", 24), fill="#333")
    d.text((60, 170), "INVOICE", font=F("DejaVuSans-Bold.ttf", 52), fill="#222")
    dt = date.fromisoformat(t["date"])
    datestr = rng.choice([dt.strftime("%b %d, %Y"), dt.strftime("%d %b %Y"), dt.isoformat(), dt.strftime("%m/%d/%Y")])
    numlabel = rng.choice(["Invoice No:", "Invoice #:", "Invoice Number:", "Inv No."])
    f = F("DejaVuSans.ttf", 28)
    d.text((60, 260), f"{numlabel} {t['invoice_number']}", font=f, fill="black")
    d.text((60, 305), f"Date: {datestr}", font=f, fill="black")
    due = (dt + timedelta(days=30)).strftime("%b %d, %Y")
    d.text((60, 350), f"Due Date: {due}", font=f, fill="black")
    d.text((700, 260), "Bill To:", font=F("DejaVuSans-Bold.ttf", 26), fill="black")
    d.text((700, 300), "Customer Services Dept", font=F("DejaVuSans.ttf", 24), fill="black")
    y = 430
    d.line((60, y - 8, W - 60, y - 8), fill="black", width=2)
    hf = F("DejaVuSans-Bold.ttf", 26)
    for x, s in [(60, "Description"), (640, "Qty"), (780, "Unit Price"), (1000, "Amount")]:
        d.text((x, y), s, font=hf, fill="black")
    d.line((60, y + 42, W - 60, y + 42), fill="black", width=2)
    y += 65
    for it in t["line_items"]:
        d.text((60, y), it["description"], font=f, fill="black")
        d.text((640, y), str(int(it["quantity"])), font=f, fill="black")
        d.text((780, y), f"${money(it['unit_price'])}", font=f, fill="black")
        d.text((1000, y), f"${money(it['amount'])}", font=f, fill="black")
        y += 58
    d.line((60, y, W - 60, y), fill="black", width=2); y += 25
    tl = rng.choice(["Total:", "Total Due:", "Amount Due:"])
    for lab, val, bold in [("Subtotal:", t["subtotal"], False), (f"Tax ({t['_rate']*100:g}%):", t["tax"], False),
                           (tl, t["total"], True)]:
        ff = F("DejaVuSans-Bold.ttf", 30) if bold else f
        d.text((700, y), lab, font=ff, fill="black"); d.text((1000, y), f"${money(val)}", font=ff, fill="black")
        y += 52
    return img.crop((0, 0, W, y + 80))


def render_receipt(t: dict, rng: random.Random) -> Image.Image:
    W, H = 640, 700 + 52 * len(t["line_items"])
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    mono, monob = F("DejaVuSansMono.ttf", 26), F("DejaVuSansMono-Bold.ttf", 32)
    def center(y, s, font):
        w = d.textlength(s, font=font); d.text(((W - w) / 2, y), s, font=font, fill="black")
    center(30, t["vendor"].upper(), monob)
    center(80, f"{rng.choice(STREETS)}", mono)
    center(115, f"{rng.choice(CITIES)}", mono)
    dt = date.fromisoformat(t["date"])
    datestr = rng.choice([dt.isoformat(), dt.strftime("%m/%d/%Y")]) + f" {rng.randint(8,21):02d}:{rng.randint(0,59):02d}"
    d.text((30, 180), f"Receipt #: {t['invoice_number']}", font=mono, fill="black")
    d.text((30, 215), f"Date: {datestr}", font=mono, fill="black")
    d.text((30, 255), "-" * 40, font=mono, fill="black")
    y = 295
    for it in t["line_items"]:
        d.text((30, y), it["description"], font=mono, fill="black")
        d.text((30, y + 30), f"  {int(it['quantity'])} x {money(it['unit_price'])}", font=mono, fill="black")
        a = f"{money(it['amount'])}"
        d.text((W - 30 - d.textlength(a, font=mono), y + 30), a, font=mono, fill="black")
        y += 72
    d.text((30, y), "-" * 40, font=mono, fill="black"); y += 40
    for lab, val, font in [("SUBTOTAL", t["subtotal"], mono), ("TAX", t["tax"], mono), ("TOTAL", t["total"], monob)]:
        s = f"${money(val)}"
        d.text((30, y), lab, font=font, fill="black")
        d.text((W - 30 - d.textlength(s, font=font), y), s, font=font, fill="black"); y += 45
    center(y + 20, "THANK YOU!", mono)
    return img.crop((0, 0, W, y + 90))


def render_vat(t: dict, rng: random.Random) -> Image.Image:
    W, H = 1240, 1000 + 70 * len(t["line_items"])
    img = Image.new("RGB", (W, H), "#fdfbf4"); d = ImageDraw.Draw(img)
    serif, serifb = F("DejaVuSerif.ttf", 27), F("DejaVuSerif-Bold.ttf", 27)
    d.text((60, 40), "TAX INVOICE", font=F("DejaVuSerif-Bold.ttf", 40), fill="#111")
    d.text((60, 110), t["vendor"], font=F("DejaVuSerif-Bold.ttf", 36), fill="#111")
    d.text((60, 160), f"{rng.choice(STREETS)}, {rng.choice(CITIES)}", font=serif, fill="#333")
    dt = date.fromisoformat(t["date"])
    datestr = rng.choice([dt.strftime("%d %B %Y"), dt.strftime("%d-%b-%Y"), dt.strftime("%d %b %Y")])
    d.text((60, 250), f"Invoice Number: {t['invoice_number']}", font=serif, fill="black")
    d.text((60, 295), f"Issue Date: {datestr}", font=serif, fill="black")
    d.text((60, 340), f"Payment Terms: 30 days", font=serif, fill="black")
    y = 420
    for x, s in [(60, "Item"), (620, "Qty"), (760, "Price"), (990, "Line Total")]:
        d.text((x, y), s, font=serifb, fill="black")
    d.line((60, y + 42, W - 60, y + 42), fill="black", width=2); y += 65
    for it in t["line_items"]:
        d.text((60, y), it["description"], font=serif, fill="black")
        d.text((620, y), str(int(it["quantity"])), font=serif, fill="black")
        d.text((760, y), f"\u00a3{money(it['unit_price'])}", font=serif, fill="black")
        d.text((990, y), f"\u00a3{money(it['amount'])}", font=serif, fill="black")
        y += 58
    d.line((60, y, W - 60, y), fill="black", width=2); y += 25
    for lab, val, bold in [("Net Total", t["subtotal"], False), ("VAT (20%)", t["tax"], False),
                           ("Amount Due", t["total"], True)]:
        ff = serifb if bold else serif
        d.text((680, y), lab, font=ff, fill="black"); d.text((990, y), f"\u00a3{money(val)}", font=ff, fill="black")
        y += 52
    d.text((60, y + 30), "All amounts in GBP", font=F("DejaVuSerif.ttf", 22), fill="#444")
    return img.crop((0, 0, W, y + 100))


def degrade(img: Image.Image, rng: random.Random, np_rng: np.random.Generator) -> tuple[Image.Image, dict]:
    p = {"rotation": round(rng.uniform(-2.5, 2.5), 2), "blur": round(rng.choice([0, 0, 0.6, 1.0, 1.5]), 2),
         "noise": rng.choice([0, 6, 12, 22]), "scale": round(rng.choice([1.0, 0.85, 0.7, 0.55]), 2),
         "jpeg": rng.choice([95, 70, 45])}
    bg = tuple(rng.randint(225, 255) for _ in range(3))
    img = img.rotate(p["rotation"], expand=True, fillcolor=bg, resample=Image.BICUBIC)
    if p["scale"] < 1:
        img = img.resize((int(img.width * p["scale"]), int(img.height * p["scale"])), Image.LANCZOS)
    if p["blur"]:
        img = img.filter(ImageFilter.GaussianBlur(p["blur"]))
    a = np.asarray(img).astype(np.float32)
    # uneven lighting gradient (shadow from a scanner lid / phone)
    grad = np.linspace(rng.uniform(0.82, 1.0), 1.0, a.shape[1])[None, :, None]
    a = a * grad
    if p["noise"]:
        a += np_rng.normal(0, p["noise"], a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=36)
    ap.add_argument("--out", default="data/samples")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rng, np_rng = random.Random(a.seed), np.random.default_rng(a.seed)
    layouts = [("invoice", render_invoice), ("receipt", render_receipt), ("vat", render_vat)]
    for i in range(a.n):
        name, fn = layouts[i % 3]
        t = make_truth(rng, name)
        img, deg = degrade(fn(t, rng), rng, np_rng)
        stem = f"doc_{i:03d}_{name}"
        img.save(out / f"{stem}.jpg", quality=deg["jpeg"])
        gt = {k: v for k, v in t.items() if not k.startswith("_")}
        gt["_meta"] = {"layout": name, "degradation": deg}
        (out / f"{stem}.json").write_text(json.dumps(gt, indent=2))
    print(f"wrote {a.n} documents to {out}")


if __name__ == "__main__":
    main()
