"""Image preprocessing + Tesseract OCR returning words with confidences, grouped into lines."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from pytesseract import Output


@dataclass
class Word:
    text: str
    conf: float  # 0..1
    x: int
    y: int
    w: int
    h: int


@dataclass
class Line:
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def conf(self) -> float:
        return sum(w.conf for w in self.words) / len(self.words) if self.words else 0.0

    @property
    def y(self) -> int:
        return min(w.y for w in self.words)


def _rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _deskew(gray: np.ndarray, max_angle: float = 4.0, step: float = 0.25) -> np.ndarray:
    """Projection-profile deskew: the angle whose row-sum histogram is sharpest wins."""
    small = cv2.resize(gray, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
    inv = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    best, best_score = 0.0, -1.0
    for a in np.arange(-max_angle, max_angle + step, step):
        score = np.var(_rotate(inv, a).sum(axis=1).astype(np.float64))
        if score > best_score:
            best, best_score = a, score
    return gray if abs(best) < 0.2 else _rotate(gray, best)


TARGET_W = 1400
VARIANTS = ("otsu", "gray", "adaptive")   # binarisation strategies; see pipeline for how the best is chosen


def preprocess(img: np.ndarray, variant: str = "otsu") -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    if w < TARGET_W:  # Tesseract wants roughly 300 DPI
        gray = cv2.resize(gray, None, fx=TARGET_W / w, fy=TARGET_W / w, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, h=8, templateWindowSize=7, searchWindowSize=21)
    gray = _deskew(gray)
    if variant == "gray":
        return gray
    if variant == "otsu":
        # flatten uneven lighting first, then global threshold
        bg = cv2.medianBlur(gray, 51)
        norm = cv2.divide(gray, bg, scale=255)
        return cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15)


def run_ocr(path: str, variant: str = "otsu") -> list[Line]:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    proc = preprocess(img, variant)
    d = pytesseract.image_to_data(proc, config="--oem 1 --psm 6", output_type=Output.DICT)
    lines: dict[tuple, Line] = {}
    for i, txt in enumerate(d["text"]):
        txt = txt.strip()
        conf = float(d["conf"][i])
        if not txt or conf < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        lines.setdefault(key, Line()).words.append(
            Word(txt, conf / 100.0, d["left"][i], d["top"][i], d["width"][i], d["height"][i]))
    out = sorted(lines.values(), key=lambda l: l.y)
    for l in out:
        l.words.sort(key=lambda w: w.x)
    return out
