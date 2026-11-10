"""Colour utilities: parse what the client wrote ("cream and deep brown", "#1E40AF"), build palettes, check contrast."""
from __future__ import annotations

import colorsys
import re
from typing import Iterable, List, Optional, Tuple

# Tasteful designer values for colour words clients actually use (longest names matched first).
NAMED = {
    "off white": "#F7F4EE", "off-white": "#F7F4EE", "ivory": "#FBF6EA", "cream": "#F3E9DA", "beige": "#E8DCC6", "sand": "#DCC9A6",
    "white": "#FFFFFF", "black": "#111111", "jet black": "#0B0B0C", "charcoal": "#2B2D31", "graphite": "#3A3D44",
    "grey": "#8C93A1", "gray": "#8C93A1", "warm grey": "#A39E93", "warm gray": "#A39E93", "light grey": "#E5E7EB", "light gray": "#E5E7EB",
    "dark grey": "#3F444D", "dark gray": "#3F444D", "silver": "#C0C5CE", "slate": "#475569", "stone": "#A8A29E",
    "brown": "#6F4A30", "deep brown": "#3E2516", "deep-brown": "#3E2516", "dark brown": "#3B2416", "chocolate": "#4A2A1A",
    "espresso": "#3B2416", "coffee": "#6F4E37", "mocha": "#8A6A55", "caramel": "#C68B45", "tan": "#C9A27E", "copper": "#B8693D",
    "terracotta": "#C5643E", "rust": "#A9472A", "burnt orange": "#CC5500", "orange": "#F2852B", "peach": "#F7B998", "apricot": "#F5B57E",
    "coral": "#FF6F59", "salmon": "#F48C78", "red": "#D7263D", "crimson": "#B5172E", "scarlet": "#E3242B", "cherry": "#B1122C",
    "burgundy": "#6D1A36", "maroon": "#6B1E2C", "wine": "#5E1B30", "pink": "#F06292", "hot pink": "#FF3E8A", "blush": "#F2C4C0",
    "rose": "#E07A8A", "dusty rose": "#C98B8B", "magenta": "#C2187A", "fuchsia": "#D9218C", "purple": "#6A4C93", "violet": "#7C3AED",
    "lavender": "#B8A6E0", "lilac": "#C8A2C8", "plum": "#6E3A5E", "indigo": "#3F3D99", "navy": "#14213D", "navy blue": "#14213D",
    "midnight blue": "#121B33", "dark blue": "#1B2F5B", "royal blue": "#2546B5", "cobalt": "#1F4FD1", "blue": "#1E64C8",
    "sky blue": "#7CC6F2", "light blue": "#A7D3F2", "baby blue": "#B9DCF2", "powder blue": "#B6D0E2", "teal": "#0F766E",
    "turquoise": "#2CC2B4", "aqua": "#3DD6D0", "cyan": "#18B6D6", "mint": "#A8E6CF", "sage": "#9CAF88", "sage green": "#9CAF88",
    "olive": "#6B7A3A", "khaki": "#B5A66B", "forest green": "#1F4D3A", "dark green": "#1D4D32", "emerald": "#11845B",
    "green": "#2E8B57", "lime": "#9BD53B", "light green": "#9ED9A6", "bottle green": "#0F4C3A", "mustard": "#E1A730",
    "gold": "#C9A227", "golden": "#C9A227", "yellow": "#F6C90E", "lemon": "#F7E463", "butter": "#F6E7A1", "amber": "#F0A202",
    "bronze": "#A6743B", "champagne": "#E9D8B4", "pastel": "#F3D9E0", "neon green": "#39FF88", "neon": "#39FF88",
}
_NAME_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(n) for n in NAMED), key=len, reverse=True)) + r")\b", re.I)
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def norm(hex_: str) -> str:
    h = hex_.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()[:6]


def rgb(hex_: str) -> Tuple[float, float, float]:
    h = norm(hex_)[1:]
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def to_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in (r, g, b))


def hls(hex_: str) -> Tuple[float, float, float]:
    return colorsys.rgb_to_hls(*rgb(hex_))


def from_hls(h: float, l: float, s: float) -> str:
    return to_hex(*colorsys.hls_to_rgb(h % 1.0, max(0, min(1, l)), max(0, min(1, s))))


def mix(a: str, b: str, t: float) -> str:
    ra, rb = rgb(a), rgb(b)
    return to_hex(*(x + (y - x) * t for x, y in zip(ra, rb)))


def lighten(c: str, t: float) -> str:
    return mix(c, "#FFFFFF", t)


def darken(c: str, t: float) -> str:
    return mix(c, "#000000", t)


def with_lightness(c: str, l: float) -> str:
    h, _, s = hls(c)
    return from_hls(h, l, s)


def saturate(c: str, factor: float) -> str:
    h, l, s = hls(c)
    return from_hls(h, l, s * factor)


def rotate(c: str, degrees: float) -> str:
    h, l, s = hls(c)
    return from_hls(h + degrees / 360.0, l, s)


def luminance(c: str) -> float:
    def ch(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(v) for v in rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def chroma(c: str) -> float:
    _, l, s = hls(c)
    return s * (1 - abs(2 * l - 1))


def is_neutral(c: str) -> bool:
    return chroma(c) < 0.12


def readable_on(bg: str, *candidates: str, minimum: float = 4.5) -> str:
    """First candidate with enough contrast on bg, else whichever of near-black / white is better."""
    for c in candidates:
        if c and contrast(c, bg) >= minimum:
            return c
    best = max(candidates or ("#111111",), key=lambda c: contrast(c, bg)) if candidates else "#111111"
    if contrast(best, bg) >= minimum:
        return best
    return "#FFFFFF" if contrast("#FFFFFF", bg) >= contrast("#141414", bg) else "#141414"


# Colour words that are also everyday nouns ("coffee roastery", "gold jewellery", "rose garden"): in free text they
# only count as colours when colour vocabulary is close by. In the brand-colours field everything counts.
AMBIGUOUS = {"coffee", "espresso", "mocha", "chocolate", "caramel", "sand", "stone", "gold", "golden", "silver", "rose", "wine", "cherry", "lemon",
             "butter", "mint", "olive", "peach", "apricot", "salmon", "plum", "emerald", "rust", "copper", "bronze", "champagne", "lime", "slate",
             "graphite", "khaki", "tan", "amber", "pastel", "neon", "sage", "lavender", "lilac", "coral", "sky blue", "white", "black", "cream", "ivory"}
_COLOUR_CONTEXT = re.compile(r"colou?r|palette|tone|shade|hue|tint|accent|background|-coloured|-colored|scheme", re.I)


def extract(texts: Iterable[Optional[str]], *, strict_from: int = 1) -> List[str]:
    """All colours mentioned, in order of first mention (hex codes and colour words).
    Texts at index >= strict_from are free text: ambiguous words need colour vocabulary within ~40 characters."""
    found: List[Tuple[int, int, str]] = []
    for ti, text in enumerate(texts):
        if not text:
            continue
        s = str(text)
        for m in _HEX_RE.finditer(s):
            found.append((ti, m.start(), norm(m.group(0))))
        hex_spans = [(h.start(), h.end()) for h in _HEX_RE.finditer(s)]
        for m in _NAME_RE.finditer(s):
            word = m.group(1).lower()
            # "soft green #8DA47E" / "#6F4E37 (coffee brown)": the hex code is the client's exact colour, the words only describe it
            if any(abs(m.start() - he) <= 14 or abs(hs - m.end()) <= 14 for hs, he in hex_spans):
                continue
            if ti >= strict_from and word in AMBIGUOUS:
                after = s[m.end(): m.end() + 26]
                before = s[max(0, m.start() - 14): m.start()]
                if re.match(r"-(?!colou?red|toned)[A-Za-z]", after):  # "coffee-bean", "gold-plated"
                    continue
                if not (_COLOUR_CONTEXT.search(after) or _COLOUR_CONTEXT.search(before)):
                    continue
            found.append((ti, m.start(), NAMED[word]))
    found.sort()
    out: List[str] = []
    for _, _, c in found:
        if c not in out and all(contrast(c, o) >= 1.12 for o in out):  # skip exact and near-identical repeats
            out.append(c)
    return out


def cmyk(c: str) -> Tuple[int, int, int, int]:
    r, g, b = rgb(c)
    k = 1 - max(r, g, b)
    if k >= 0.999:
        return 0, 0, 0, 100
    return tuple(round(100 * v) for v in ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k))  # type: ignore[return-value]


def rgb255(c: str) -> Tuple[int, int, int]:
    return tuple(round(v * 255) for v in rgb(c))  # type: ignore[return-value]
