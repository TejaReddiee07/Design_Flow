"""Hand-built vector icons (100x100 box) and industry detection.

Icons are geometric and filled so they work as logo marks, badges and infographic glyphs at any size.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

from app.agents.tools.design_engine.canvas import Canvas, _n


def circ(cx: float, cy: float, r: float) -> str:
    return f"M{_n(cx - r)} {_n(cy)}a{_n(r)} {_n(r)} 0 1 0 {_n(2 * r)} 0a{_n(r)} {_n(r)} 0 1 0 {_n(-2 * r)} 0Z"


def ell(cx: float, cy: float, rx: float, ry: float, rot: float = 0) -> str:
    a = math.radians(rot)
    x1, y1 = cx - rx * math.cos(a), cy - rx * math.sin(a)
    x2, y2 = cx + rx * math.cos(a), cy + rx * math.sin(a)
    return f"M{_n(x1)} {_n(y1)}A{_n(rx)} {_n(ry)} {_n(rot)} 1 0 {_n(x2)} {_n(y2)}A{_n(rx)} {_n(ry)} {_n(rot)} 1 0 {_n(x1)} {_n(y1)}Z"


def rrect(x: float, y: float, w: float, h: float, r: float) -> str:
    r = min(r, w / 2, h / 2)
    return (f"M{_n(x + r)} {_n(y)}H{_n(x + w - r)}A{_n(r)} {_n(r)} 0 0 1 {_n(x + w)} {_n(y + r)}V{_n(y + h - r)}A{_n(r)} {_n(r)} 0 0 1 {_n(x + w - r)} {_n(y + h)}"
            f"H{_n(x + r)}A{_n(r)} {_n(r)} 0 0 1 {_n(x)} {_n(y + h - r)}V{_n(y + r)}A{_n(r)} {_n(r)} 0 0 1 {_n(x + r)} {_n(y)}Z")


def star_points(cx: float, cy: float, r_out: float, r_in: float, n: int = 5, rot: float = -90) -> List[Tuple[float, float]]:
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def poly(pts: Sequence[Tuple[float, float]]) -> str:
    return "M" + "L".join(f"{_n(x)} {_n(y)}" for x, y in pts) + "Z"


def _gear() -> str:
    pts = []
    n = 8
    for i in range(n * 4):
        a = math.radians(i * 360 / (n * 4) - 90)
        r = 46 if (i % 4) in (1, 2) else 36
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    return poly(pts) + circ(50, 50, 15)


# Each icon: list of (kind, *args). kinds: p=filled path (evenodd), s=stroke path (width)
ICONS: Dict[str, List[tuple]] = {
    "bean": [("g", "rotate(35 50 50)", [("p", ell(50, 50, 27, 39) + "M50 13C40 30 59 40 48 50C38 60 57 70 50 87C61 70 42 60 53 50C63 40 45 30 50 13Z")])],
    "cup": [
        ("p", "M22 40H72V57C72 71 61 81 47 81C33 81 22 71 22 57Z"),
        ("p", circ(73, 56, 13) + circ(73, 56, 6.5)),
        ("p", "M12 87H82C82 90 78 93 74 93H20C16 93 12 90 12 87Z"),
        ("s", "M38 31C32 25 44 20 38 12", 5), ("s", "M55 31C49 25 61 20 55 12", 5),
    ],
    "wheat": [("s", "M50 94V20", 5)]
    + [("p", ell(39, 34 + i * 15, 6.5, 12, -38)) for i in range(4)]
    + [("p", ell(61, 34 + i * 15, 6.5, 12, 38)) for i in range(4)]
    + [("p", ell(50, 17, 6, 12, 0))],
    "cutlery": [
        ("p", "M20 10H24V32H28V10H32V32H36V10H40V36C40 44 35 49 32 50V88C32 92 28 92 28 88V50C25 49 20 44 20 36Z"),
        ("p", "M64 10C77 15 82 31 80 53L71 55V88C71 92 64 92 64 88Z"),
    ],
    "chef": [("p", circ(32, 42, 16) + circ(50, 32, 19)), ("p", circ(68, 42, 16)), ("p", "M32 48H68V72H32Z"), ("p", rrect(32, 76, 36, 12, 3))],
    "bolt": [("p", "M58 6L22 56H46L38 94L78 40H54Z")],
    "nodes": [
        ("s", poly([(50 + 36 * math.cos(math.radians(a)), 50 + 36 * math.sin(math.radians(a))) for a in range(-90, 270, 60)]), 6),
        ("s", "M50 50L50 14M50 50L81.2 68M50 50L18.8 68", 5),
        ("p", circ(50, 50, 10)), ("p", circ(50, 14, 7)), ("p", circ(81.2, 68, 7)), ("p", circ(18.8, 68, 7)),
    ],
    "dumbbell": [("p", "M28 45H72V55H28Z"), ("p", rrect(10, 28, 12, 44, 3)), ("p", rrect(22, 35, 8, 30, 2)), ("p", rrect(78, 28, 12, 44, 3)), ("p", rrect(70, 35, 8, 30, 2))],
    "flame": [("p", "M50 6C58 26 80 38 80 62C80 80 66 94 50 94C34 94 20 80 20 62C20 46 30 36 36 26C38 40 44 46 50 48C46 34 44 20 50 6Z"
                     "M50 60C56 68 62 73 62 79C62 86 56 90 50 90C44 90 38 86 38 79C38 73 44 68 50 60Z")],
    "lotus": [("p", "M50 18C63 34 63 58 50 76C37 58 37 34 50 18Z"),
              ("g", "rotate(-36 50 76)", [("p", "M50 30C60 42 60 62 50 76C40 62 40 42 50 30Z")]),
              ("g", "rotate(36 50 76)", [("p", "M50 30C60 42 60 62 50 76C40 62 40 42 50 30Z")]),
              ("g", "rotate(-70 50 76)", [("p", "M50 44C57 52 57 66 50 76C43 66 43 52 50 44Z")]),
              ("g", "rotate(70 50 76)", [("p", "M50 44C57 52 57 66 50 76C43 66 43 52 50 44Z")]),
              ("p", rrect(24, 82, 52, 6, 3))],
    "drop": [("p", "M50 8C50 8 20 44 20 62C20 79 33 92 50 92C67 92 80 79 80 62C80 44 50 8 50 8Z")],
    "flower": [("g", f"rotate({a} 50 50)", [("p", ell(50, 24, 9, 15))]) for a in range(0, 360, 60)] + [("p", circ(50, 50, 9))],
    "gem": [("p", "M30 16H70L87 37H13Z"), ("p", "M13 43H87L50 90Z")],
    "home": [("p", "M50 10L92 46H81V88H19V46H8Z" + rrect(42, 62, 16, 26, 2) + rrect(26, 52, 12, 12, 1) + rrect(62, 52, 12, 12, 1))],
    "key": [("p", circ(30, 50, 21) + circ(30, 50, 10)), ("p", "M49 45H92V55H49Z"), ("p", "M74 55H83V68H74Z"), ("p", "M60 55H67V64H60Z")],
    "plus": [("p", "M39 10H61V39H90V61H61V90H39V61H10V39H39Z")],
    "heart": [("p", "M50 88C20 66 8 50 8 34C8 21 18 12 31 12C39 12 46 16 50 23C54 16 61 12 69 12C82 12 92 21 92 34C92 50 80 66 50 88Z")],
    "tooth": [("p", "M30 12C40 12 44 17 50 17C56 17 60 12 70 12C83 12 89 23 87 39C85 55 78 63 76 78C74 90 70 94 66 94C59 94 60 74 50 74C40 74 41 94 34 94C30 94 26 90 24 78C22 63 15 55 13 39C11 23 17 12 30 12Z")],
    "chart": [("p", rrect(12, 60, 18, 30, 3)), ("p", rrect(38, 46, 18, 44, 3)), ("p", rrect(64, 30, 18, 60, 3)),
              ("s", "M12 42L34 26L52 32L80 10", 5), ("p", "M86 4L71 7L83 19Z")],
    "shield": [("p", "M50 6L86 18V46C86 70 70 86 50 94C30 86 14 70 14 46V18Z" + "M30 50L43 63L71 35L77 41L43 75L24 56Z")],
    "book": [("p", "M47 26C37 18 24 16 8 18V78C24 76 37 78 47 86Z"), ("p", "M53 26C63 18 76 16 92 18V78C76 76 63 78 53 86Z")],
    "grad": [("p", "M50 16L94 36L50 56L6 36Z"), ("p", "M24 46V64C24 73 37 80 50 80C63 80 76 73 76 64V46L50 58Z"), ("s", "M86 40V64", 4), ("p", circ(86, 67, 4))],
    "plane": [("p", "M50 6C54 6 56 11 56 17V39L91 58V67L56 56V77L67 85V92L50 87L33 92V85L44 77V56L9 67V58L44 39V17C44 11 46 6 50 6Z")],
    "mountain": [("p", "M3 86L36 32L53 58L65 42L97 86Z"), ("p", circ(76, 22, 9))],
    "compass": [("p", circ(50, 50, 44) + circ(50, 50, 35)), ("p", "M50 20L60 50L50 80L40 50Z" + circ(50, 50, 4))],
    "note": [("p", "M38 22L84 10V68C84 77 76 83 67 83C59 83 53 77 53 70C53 63 59 57 67 57C70 57 73 58 75 59V28L47 35V76C47 85 39 91 30 91C22 91 16 85 16 78C16 71 22 65 30 65C33 65 36 66 38 67Z")],
    "wave": [("s", "M6 38C20 28 32 28 46 38C60 48 72 48 94 34", 7), ("s", "M6 60C20 50 32 50 46 60C60 70 72 70 94 56", 7), ("s", "M6 82C20 72 32 72 46 82C60 92 72 92 94 78", 7)],
    "paw": [("p", "M50 52C62 52 76 66 76 78C76 86 70 90 62 90C56 90 54 86 50 86C46 86 44 90 38 90C30 90 24 86 24 78C24 66 38 52 50 52Z"),
            ("p", ell(23, 44, 8, 11, -20)), ("p", ell(40, 25, 8, 12, -8)), ("p", ell(60, 25, 8, 12, 8)), ("p", ell(77, 44, 8, 11, 20))],
    "gear": [("p", _gear())],
    "scales": [("s", "M50 12V86M16 26H84M30 90H70", 6), ("s", "M18 26L8 54M18 26L28 54M82 26L72 54M82 26L92 54", 3),
               ("p", "M5 54H31C31 62 25 67 18 67C11 67 5 62 5 54Z"), ("p", "M69 54H95C95 62 89 67 82 67C75 67 69 62 69 54Z"), ("p", circ(50, 12, 5))],
    "columns": [("p", "M50 8L92 30H8Z"), ("p", "M14 34H86V40H14Z"), ("p", "M20 44H30V78H20Z"), ("p", "M45 44H55V78H45Z"), ("p", "M70 44H80V78H70Z"), ("p", "M10 82H90V92H10Z")],
    "camera": [("p", "M14 28H31L38 18H62L69 28H86C90 28 93 31 93 35V80C93 84 90 87 86 87H14C10 87 7 84 7 80V35C7 31 10 28 14 28Z" + circ(50, 56, 19) + circ(50, 56, 11))],
    "leaf": [("p", "M14 86C14 44 44 14 88 12C88 56 58 86 14 86Z" + "M20 80C38 62 56 44 78 22L81 25C60 46 42 64 23 83Z")],
    "sprout": [("s", "M50 92V52", 6), ("p", "M50 60C29 60 17 47 15 30C34 30 48 41 50 60Z"), ("p", "M50 50C52 30 64 18 85 16C85 37 71 50 50 50Z")],
    "spark": [("p", "M50 4C54 34 66 46 96 50C66 54 54 66 50 96C46 66 34 54 4 50C34 46 46 34 50 4Z")],
    "star": [("p", poly(star_points(50, 52, 46, 19)))],
    "scissors": [("p", circ(27, 74, 14) + circ(27, 74, 7)), ("p", circ(73, 74, 14) + circ(73, 74, 7)),
                 ("p", "M33 62L74 8L80 13L42 67Z"), ("p", "M67 62L26 8L20 13L58 67Z")],
    "car": [("p", "M8 62C8 55 13 51 20 49L31 31C33 27 37 25 41 25H61C65 25 69 27 71 31L81 49C88 51 92 55 92 62V71C92 73 90 75 88 75H12C10 75 8 73 8 71Z"
                   "M36 34L29 48H48V34ZM54 34V48H72L65 34Z"), ("p", circ(28, 76, 11) + circ(28, 76, 4)), ("p", circ(72, 76, 11) + circ(72, 76, 4))],
    "globe": [("s", circ(50, 50, 40), 6), ("s", "M10 50H90M50 10C28 30 28 70 50 90M50 10C72 30 72 70 50 90", 5)],
    "bag": [("p", "M16 34H84L79 92H21Z"), ("s", "M36 44V28C36 18 42 12 50 12C58 12 64 18 64 28V44", 6)],
    "pen": [("p", "M50 4L78 40L63 90H37L22 40Z" + circ(50, 50, 7) + "M48.5 10H51.5V44H48.5Z")],
    "megaphone": [("p", "M12 40H30L76 14V86L30 60H12C9 60 8 58 8 56V44C8 42 9 40 12 40Z"), ("p", "M30 62H44L50 88H38Z"), ("s", "M86 38C91 44 91 56 86 62", 5)],
    "shirt": [("p", "M31 10L12 22L21 40L30 35V90H70V35L79 40L88 22L69 10C65 19 58 23 50 23C42 23 35 19 31 10Z")],
    "rocket": [("p", "M50 6C66 18 72 40 68 64H32C28 40 34 18 50 6Z" + circ(50, 36, 8)), ("p", "M32 50L17 68V80L32 71Z"), ("p", "M68 50L83 68V80L68 71Z"), ("p", "M41 70H59L50 92Z")],
    "users": [("p", circ(36, 32, 14)), ("p", "M10 82C10 64 22 54 36 54C50 54 62 64 62 82Z"), ("p", circ(68, 36, 11)), ("p", "M66 82C66 70 62 62 56 57C60 55 64 54 68 54C80 54 90 63 90 78V82Z")],
    "target": [("p", circ(50, 50, 44) + circ(50, 50, 34)), ("p", circ(50, 50, 24) + circ(50, 50, 14)), ("p", circ(50, 50, 6))],
    "clock": [("p", circ(50, 50, 44) + circ(50, 50, 35)), ("s", "M50 26V50L66 60", 7)],
    "check": [("p", circ(50, 50, 44) + "M28 52L43 66L73 36L79 42L43 78L22 58Z")],
    "arrow": [("p", "M8 43H62V24L94 50L62 76V57H8Z")],
    "pin": [("p", "M50 6C33 6 20 19 20 36C20 60 50 94 50 94C50 94 80 60 80 36C80 19 67 6 50 6Z" + circ(50, 36, 11))],
    "phone": [("p", "M28 8C32 8 36 10 38 14L44 28C46 32 45 36 42 39L35 45C40 56 46 62 57 67L63 60C66 57 70 56 74 58L88 64C92 66 94 70 94 74V82C94 89 88 94 81 94C42 92 10 60 8 21C8 14 13 8 20 8Z")],
    "mail": [("p", rrect(6, 18, 88, 64, 8) + "M14 28L50 54L86 28V34L50 60L14 34Z")],
    "web": [("p", circ(50, 50, 44) + circ(50, 50, 36)), ("s", "M14 50H86M50 14C34 30 34 70 50 86M50 14C66 30 66 70 50 86", 5)],
    "quote": [("p", "M10 54C10 32 22 18 42 14L45 22C34 26 28 34 28 44H42V82H10ZM56 54C56 32 68 18 88 14L91 22C80 26 74 34 74 44H88V82H56Z")],
    "play": [("p", circ(50, 50, 44) + "M40 30L72 50L40 70Z")],
}

# keyword patterns -> (industry label, motif icon, default palette [primary, dark, light, accent])
INDUSTRIES: List[Tuple[str, str, str, List[str]]] = [
    (r"coffee|caf[eé]|espresso|roast|barista|latte", "Coffee & café", "bean", ["#8A4F2A", "#2E1B12", "#F4EBDD", "#C98B45"]),
    (r"bak(e|er|ery)|bread|pastr|cake|patisserie|dessert|cupcake", "Bakery", "wheat", ["#B5651D", "#3D2314", "#FBF3E4", "#E3B04B"]),
    (r"restaurant|food|kitchen|chef|bistro|grill|pizza|burger|dining|catering|takeaway|curry", "Food & dining", "cutlery", ["#C0392B", "#22120C", "#FFF6EC", "#F2A541"]),
    (r"tech|software|saas|\bapp\b|\bai\b|startup|digital|cloud|data|cyber|web3|platform|developer|analytic|forecast|automation|machine learning", "Technology", "nodes", ["#3B5BFD", "#0B1026", "#F4F6FF", "#22D3EE"]),
    (r"gym|fitness|workout|personal train|crossfit|athlet|sport", "Fitness", "dumbbell", ["#E4572E", "#121212", "#F6F6F4", "#F3C623"]),
    (r"yoga|pilates|meditat|wellness|mindful|retreat", "Wellness", "lotus", ["#7A9E7E", "#1F3A2E", "#F5F1EA", "#D8A47F"]),
    (r"skin|beauty|cosmetic|salon|spa|nail|lash|makeup|hair", "Beauty", "drop", ["#C9848C", "#3A1F2B", "#FBF2F0", "#E8C39E"]),
    (r"barber|grooming", "Barbering", "scissors", ["#1C3D5A", "#111418", "#F2EFEA", "#C8A253"]),
    (r"fashion|cloth|apparel|boutique|wear|streetwear|tailor", "Fashion", "shirt", ["#111111", "#0A0A0A", "#F5F2EE", "#C8A253"]),
    (r"jewel|diamond|ring|gold", "Jewellery", "gem", ["#1B2A41", "#0C1320", "#F7F3EC", "#C9A227"]),
    (r"real estate|property|homes?\b|estate agent|letting|mortgage|interior|architect", "Property", "home", ["#1F4E79", "#0F2133", "#F3F6F9", "#E0A458"]),
    (r"dent(al|ist)|orthodont|smile", "Dental", "tooth", ["#1C8C9C", "#0E2A33", "#F2FAFB", "#7FD1C7"]),
    (r"clinic|health|medical|pharma|doctor|care home|physio|hospital|therapy|nurse", "Healthcare", "plus", ["#1E7A8C", "#0D2B33", "#F2F8F9", "#5BC0BE"]),
    (r"financ|account|bank|invest|insur|tax|wealth|fintech|bookkeep", "Finance", "chart", ["#0F4C81", "#0A1F33", "#F3F6FA", "#2EC4B6"]),
    (r"law|legal|solicitor|attorney|barrister|notary", "Legal", "scales", ["#1D2D50", "#0C1426", "#F6F4EF", "#B08D57"]),
    (r"consult|agency|strategy|advis", "Consulting", "target", ["#25316D", "#0E1330", "#F5F6FB", "#F4A259"]),
    (r"school|educat|tutor|course|academy|learning|training|universit|college", "Education", "grad", ["#2D5DA8", "#13213D", "#F5F8FD", "#F2B134"]),
    (r"travel|tour|holiday|hotel|airline|trip|adventure|hostel", "Travel", "plane", ["#0E7C86", "#0B2A2E", "#F2FAF9", "#F6AE2D"]),
    (r"music|band|studio|record|dj|podcast|audio|singer", "Music", "note", ["#7B2CBF", "#140A24", "#F7F2FC", "#FF9E00"]),
    (r"\bpet|dog|cat|vet|groom", "Pets", "paw", ["#E07A5F", "#2B1D1A", "#FDF6F0", "#81B29A"]),
    (r"construct|build|engineer|repair|plumb|electric|roof|joiner|carpent|renovat|trade", "Construction", "gear", ["#F2A900", "#1D1D1F", "#F7F6F2", "#2E5E8C"]),
    (r"photo|film|video|media|cinema|production", "Media", "camera", ["#222222", "#0D0D0D", "#F4F4F2", "#E94F37"]),
    (r"garden|plant|organic|eco|green|farm|florist|landscap|sustain", "Garden & eco", "leaf", ["#3A7D44", "#14301A", "#F3F8EF", "#C9B458"]),
    (r"flower|floral|bouquet|wedding|bridal|event|party", "Events & florals", "flower", ["#B5838D", "#3A2430", "#FBF4F2", "#E5989B"]),
    (r"car|auto|garage|motor|vehicle|detailing|tyre", "Automotive", "car", ["#C1121F", "#111418", "#F4F4F4", "#669BBC"]),
    (r"shop|store|retail|e-?commerce|market|brand", "Retail", "bag", ["#E76F51", "#1F2421", "#FAF6F1", "#2A9D8F"]),
    (r"marketing|creative|design|social media|content", "Creative", "pen", ["#6C47FF", "#120E2B", "#F6F4FF", "#FF7A59"]),
    (r"ocean|surf|beach|swim|marine|water", "Coastal", "wave", ["#0077B6", "#03243A", "#F0F8FC", "#F4A261"]),
    (r"energy|power|solar|electric", "Energy", "bolt", ["#F4B400", "#1C1C1C", "#FFFBEF", "#0F9D58"]),
    (r"rocket|launch|space", "Launch", "rocket", ["#5B5BD6", "#0D0D2B", "#F5F5FF", "#FF6B6B"]),
]
DEFAULT_INDUSTRY = ("General business", "spark", ["#4F46E5", "#12122A", "#F6F6FB", "#F59E0B"])


# words a client (or the Design Agent) uses for a symbol -> icon key
MOTIF_WORDS: Dict[str, List[str]] = {
    "bean": ["coffee bean", "coffee-bean", "coffee beans"], "cup": ["cup", "mug", "coffee cup", "teacup"], "leaf": ["leaf", "leaves", "branch", "botanical", "foliage"],
    "wheat": ["wheat", "grain", "ear of wheat"], "flower": ["flower", "floral", "petal", "bloom"], "star": ["star"], "heart": ["heart"], "drop": ["droplet", "water drop", "drop"],
    "flame": ["flame", "fire"], "mountain": ["mountain", "peak", "hill"], "wave": ["wave", "waves", "ocean"], "sprout": ["sprout", "seedling", "shoot"], "paw": ["paw", "paw print"],
    "gem": ["gem", "diamond", "jewel", "crystal"], "home": ["house", "roof", "home icon"], "key": ["key"], "book": ["book"], "note": ["music note", "musical note"],
    "camera": ["camera", "lens"], "plane": ["plane", "aeroplane", "airplane"], "compass": ["compass"], "rocket": ["rocket"], "globe": ["globe", "world map"],
    "bolt": ["lightning", "bolt"], "shield": ["shield", "crest"], "lotus": ["lotus"], "spark": ["spark", "sparkle", "starburst"], "scissors": ["scissors"],
    "gear": ["gear", "cog"], "tooth": ["tooth"], "chef": ["chef hat", "chef's hat"], "cutlery": ["fork", "knife", "cutlery"], "pen": ["pen nib", "nib", "pen"],
    "target": ["target", "bullseye"], "car": ["car"], "shirt": ["t-shirt", "shirt"], "bag": ["shopping bag", "bag"], "chart": ["chart", "graph"],
}
_NEG = re.compile(r"\b(?:avoid(?:ing)?|no|not|without|never|don'?t (?:use|want|include)|steer clear of|nothing like|instead of)\b([^.;:!?\n]{0,48})", re.I)


def _motif_hits(text: str) -> List[Tuple[int, str]]:
    hits = []
    low = text.lower()
    for key, words in MOTIF_WORDS.items():
        for w in sorted(words, key=len, reverse=True):
            for m in re.finditer(r"\b" + re.escape(w) + r"s?\b", low):
                hits.append((m.start(), key))
    return sorted(hits)


_MARK_WORDS = re.compile(r"\b(mark|icon|symbol|logo|emblem|element|illustration|motif|graphic|badge|featuring|feature|with an?|include|including|shaped)\b", re.I)
_USAGE_BEFORE = re.compile(r"\b(on|onto|for|across|printed on|use(?:d)? on|goes on|work(?:s)? (?:small|big|well) on)\s+(?:the\s+|our\s+|a\s+)?$", re.I)


# the obvious symbols per industry, skipped when a client asks to avoid clichés
CLICHES: Dict[str, set] = {
    "Coffee & café": {"bean", "cup"}, "Bakery": {"wheat"}, "Food & dining": {"cutlery", "chef"}, "Technology": {"nodes", "bolt"},
    "Fitness": {"dumbbell", "flame"}, "Property": {"home", "key"}, "Dental": {"tooth"}, "Healthcare": {"plus", "heart"}, "Finance": {"chart"},
    "Legal": {"scales", "columns"}, "Education": {"grad", "book"}, "Travel": {"plane", "globe"}, "Music": {"note"}, "Pets": {"paw"},
}


def motif_preferences(client_texts: List[str], agent_texts: List[str], brand_name: str = "", feedback_texts: Optional[List[str]] = None) -> Tuple[List[str], set]:
    """(wanted motifs in priority order, motifs to avoid). The client's own words outrank the agents'.
    In the client's text a symbol only counts when it is described as part of the mark ("a simple leaf mark",
    "featuring a star"); "it must work on cups" is about usage, not the symbol."""
    avoid: set = set()
    wanted: List[str] = []
    name_rx = re.compile(re.escape(brand_name), re.I) if brand_name else None
    # priority: feedback from a rework/revision (explicit instruction), the client's own words, then the agents
    for strict, group in ((False, feedback_texts or []), (True, client_texts), (False, agent_texts)):
        for t in group:
            if not t:
                continue
            text = name_rx.sub(" ", str(t)) if name_rx else str(t)
            neg_spans = []
            for m in _NEG.finditer(text):
                neg_spans.append((m.start(1), m.end(1)))
                for _, key in _motif_hits(m.group(1)):
                    avoid.add(key)
            for pos, key in _motif_hits(text):
                if any(a <= pos < b for a, b in neg_spans):
                    continue
                if strict:
                    before, after = text[max(0, pos - 30): pos], text[pos: pos + 40]
                    if _USAGE_BEFORE.search(before) or not (_MARK_WORDS.search(before) or _MARK_WORDS.search(after)):
                        continue
                if key not in wanted:
                    wanted.append(key)
    return [k for k in wanted if k not in avoid], avoid


def detect_industry(*texts: Optional[str]) -> Tuple[str, str, List[str]]:
    blob = " ".join(t for t in texts if t).lower()
    for pattern, label, motif, palette in INDUSTRIES:
        if re.search(pattern, blob):
            return label, motif, palette
    return DEFAULT_INDUSTRY


def draw_icon(c: Canvas, name: str, x: float, y: float, size: float, color: str, opacity: float = 1.0) -> None:
    spec = ICONS.get(name) or ICONS["spark"]
    k = size / 100.0
    with c.group(transform=f"translate({_n(x)} {_n(y)}) scale({k:.4f})", opacity=opacity):
        _draw(c, spec, color)


def _draw(c: Canvas, spec: List[tuple], color: str) -> None:
    for item in spec:
        kind = item[0]
        if kind == "p":
            c.path(item[1], fill=color, evenodd=True)
        elif kind == "s":
            c.path(item[1], stroke=color, sw=item[2])
        elif kind == "g":
            with c.group(transform=item[1]):
                _draw(c, item[2], color)
