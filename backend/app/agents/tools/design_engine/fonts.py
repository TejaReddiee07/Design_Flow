"""Typography for the design engine.

Text is shaped with HarfBuzz (kerning, ligatures) and drawn as vector outlines taken from the
font files with fontTools, so every SVG/PNG/PDF looks identical everywhere and no font has to be
installed on the viewer's machine. All fonts are open-licence (SIL OFL) and live in app/assets/fonts.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

# family -> (file, variable?) ; static families may map weight -> file
FAMILIES: Dict[str, Dict[str, object]] = {
    "Inter": {"file": "Inter[opsz,wght].ttf", "pin": {"opsz": 28}},
    "Montserrat": {"file": "Montserrat[wght].ttf"},
    "Playfair Display": {"file": "PlayfairDisplay[wght].ttf"},
    "Space Grotesk": {"file": "SpaceGrotesk[wght].ttf"},
    "Lora": {"file": "Lora[wght].ttf"},
    "Oswald": {"file": "Oswald[wght].ttf"},
    "Raleway": {"file": "Raleway[wght].ttf"},
    "Nunito": {"file": "Nunito[wght].ttf"},
    "Poppins": {"static": {400: "Poppins-Regular.ttf", 700: "Poppins-Bold.ttf"}},
    "DM Serif Display": {"static": {400: "DMSerifDisplay-Regular.ttf"}},
    "Archivo Black": {"static": {400: "ArchivoBlack-Regular.ttf"}},
    "Bebas Neue": {"static": {400: "BebasNeue-Regular.ttf"}},
    "Pacifico": {"static": {400: "Pacifico-Regular.ttf"}},
    "Abril Fatface": {"static": {400: "AbrilFatface-Regular.ttf"}},
}

_lock = threading.Lock()


@lru_cache(maxsize=32)
def _ttfont(path: str) -> TTFont:
    return TTFont(path, lazy=False)


@lru_cache(maxsize=32)
def _blob(path: str) -> bytes:
    return Path(path).read_bytes()


@dataclass
class Shaped:
    glyphs: List[Tuple[str, float, float]]  # (glyph name, x, y) in font units
    advance: float  # total advance in font units


class Face:
    """One family at one weight."""

    def __init__(self, family: str, weight: int = 400) -> None:
        spec = FAMILIES.get(family) or FAMILIES["Inter"]
        if family not in FAMILIES:
            family = "Inter"
        self.family = family
        self.weight = int(weight)
        self.location: Dict[str, float] = {}
        if "static" in spec:
            files: Dict[int, str] = spec["static"]  # type: ignore[assignment]
            best = min(files, key=lambda w: abs(w - self.weight))
            self.path = str(FONT_DIR / files[best])
            self.weight = best
        else:
            self.path = str(FONT_DIR / str(spec["file"]))
        self.tt = _ttfont(self.path)
        if "fvar" in self.tt:
            for axis in self.tt["fvar"].axes:
                if axis.axisTag == "wght":
                    self.location["wght"] = float(max(axis.minValue, min(axis.maxValue, self.weight)))
                else:
                    pin = (spec.get("pin") or {}).get(axis.axisTag)  # type: ignore[union-attr]
                    self.location[axis.axisTag] = float(pin if pin is not None else axis.defaultValue)
        self.upem = self.tt["head"].unitsPerEm
        os2 = self.tt["OS/2"]
        hhea = self.tt["hhea"]
        self.ascent = float(getattr(os2, "sTypoAscender", 0) or hhea.ascent)
        self.descent = float(getattr(os2, "sTypoDescender", 0) or hhea.descent)
        self.cap_height = float(getattr(os2, "sCapHeight", 0) or self.ascent * 0.7)
        self.x_height = float(getattr(os2, "sxHeight", 0) or self.cap_height * 0.72)
        self.order = self.tt.getGlyphOrder()
        self.glyphset = self.tt.getGlyphSet(location=self.location) if self.location else self.tt.getGlyphSet()
        hb_face = hb.Face(_blob(self.path))
        self.hb_font = hb.Font(hb_face)
        if self.location:
            self.hb_font.set_variations(self.location)
        self.key = f"{''.join(ch for ch in family if ch.isalnum()).lower()}{self.weight}"
        self._paths: Dict[str, str] = {}

    # --- shaping ---------------------------------------------------------
    def clean(self, text: str) -> str:
        """Drop characters this font cannot draw (emoji, rare symbols) instead of showing empty boxes."""
        if not hasattr(self, "_cmap"):
            self._cmap = self.tt.getBestCmap() or {}
        swaps = {"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-", "…": "..."}
        out = []
        for ch in str(text):
            if ch in (" ", "\n") or ord(ch) in self._cmap:
                out.append(ch)
            elif ch in swaps and all(ord(s) in self._cmap for s in swaps[ch]):
                out.append(swaps[ch])
        return "".join(out)

    def shape(self, text: str, tracking: float = 0.0) -> Shaped:
        """tracking is letter-spacing in em (0.1 = +10% of the font size between letters)."""
        text = self.clean(text)
        if not text:
            return Shaped([], 0.0)
        with _lock:
            buf = hb.Buffer()
            buf.add_str(text)
            buf.guess_segment_properties()
            hb.shape(self.hb_font, buf, {"kern": True, "liga": True})
            infos, positions = buf.glyph_infos, buf.glyph_positions
        extra = tracking * self.upem
        x = 0.0
        out: List[Tuple[str, float, float]] = []
        for i, (info, pos) in enumerate(zip(infos, positions)):
            name = self.order[info.codepoint] if info.codepoint < len(self.order) else ".notdef"
            out.append((name, x + pos.x_offset, pos.y_offset))
            x += pos.x_advance + (extra if i < len(infos) - 1 else 0.0)
        return Shaped(out, x)

    def width(self, text: str, size: float, tracking: float = 0.0) -> float:
        return self.shape(text, tracking).advance * size / self.upem

    def glyph_path(self, name: str) -> str:
        d = self._paths.get(name)
        if d is None:
            pen = SVGPathPen(self.glyphset, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
            try:
                self.glyphset[name].draw(pen)
                d = pen.getCommands()
            except KeyError:
                d = ""
            self._paths[name] = d
        return d

    # --- metrics in px for a font size -----------------------------------
    def cap(self, size: float) -> float:
        return self.cap_height * size / self.upem

    def asc(self, size: float) -> float:
        return self.ascent * size / self.upem

    def desc(self, size: float) -> float:
        return -self.descent * size / self.upem


_faces: Dict[Tuple[str, int], Face] = {}


def face(family: str, weight: int = 400) -> Face:
    key = (family, int(weight))
    f = _faces.get(key)
    if f is None:
        with _lock:
            f = _faces.get(key)
            if f is None:
                f = Face(family, weight)
                _faces[key] = f
    return f


def wrap(text: str, fc: Face, size: float, max_width: float, tracking: float = 0.0) -> List[str]:
    """Greedy word wrap; honours explicit line breaks; breaks over-long words."""
    lines: List[str] = []
    for para in str(text).replace("\r", "").split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if not line or fc.width(trial, size, tracking) <= max_width:
                line = trial
                continue
            lines.append(line)
            line = word
            while fc.width(line, size, tracking) > max_width and len(line) > 2:  # very long word
                cut = len(line) - 1
                while cut > 1 and fc.width(line[:cut] + "-", size, tracking) > max_width:
                    cut -= 1
                lines.append(line[:cut] + "-")
                line = line[cut:]
        lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def fit(text: str, fc: Face, max_width: float, max_height: float, *, max_size: float, min_size: float = 8.0,
        line_height: float = 1.1, max_lines: int = 6, tracking: float = 0.0) -> Tuple[float, List[str]]:
    """Largest font size (<= max_size) for which the wrapped text fits the box."""
    lo, hi = min_size, max_size
    best = (min_size, wrap(text, fc, min_size, max_width, tracking))
    for _ in range(18):
        mid = (lo + hi) / 2
        lines = wrap(text, fc, mid, max_width, tracking)
        height = mid * line_height * (len(lines) - 1) + fc.cap(mid) + fc.desc(mid) * 0.6
        widest = max((fc.width(l, mid, tracking) for l in lines), default=0)
        if len(lines) <= max_lines and height <= max_height and widest <= max_width + 0.5:
            best = (mid, lines)
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.25:
            break
    return best
