"""AI image generation for the Design Agent (the same kind of model ChatGPT uses to create images).

Providers
  openai  gpt-image-1 via the Images API (OPENAI_API_KEY). Best at spelling brand names correctly.
  gemini  Gemini image model via the Generative Language API (GEMINI_API_KEY).
  none    no AI images; the vector design engine draws everything itself.

Every call is optional: on any error the caller falls back to the vector engine, so a request is never blocked.
Prompts contain the client's brief, so they are sent to the chosen provider; nothing is sent when no key is set.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional, Tuple

import httpx

from app.core.config import settings

log = logging.getLogger("ai_images")


def provider() -> str:
    p = (settings.ai_image_provider or "auto").lower()
    if p == "openai":
        return "openai" if settings.openai_api_key else "none"
    if p == "gemini":
        return "gemini" if settings.gemini_api_key else "none"
    if p == "none" or settings.app_env == "test":
        return "none"
    if settings.openai_api_key:
        return "openai"
    if settings.gemini_api_key:
        return "gemini"
    return "none"


def available() -> bool:
    return provider() != "none"


def label() -> str:
    p = provider()
    return {"openai": f"OpenAI {settings.openai_image_model}", "gemini": f"Google {settings.gemini_image_model}"}.get(p, "built-in vector engine")


def generate(prompt: str, *, size: str = "1024x1024", transparent: bool = False) -> Optional[bytes]:
    """Return PNG bytes, or None when no provider is configured or the call fails."""
    p = provider()
    try:
        if p == "openai":
            return _openai(prompt, size, transparent)
        if p == "gemini":
            return _gemini(prompt)
    except Exception as exc:  # network, quota, safety refusal, bad key...
        log.warning("AI image generation failed (%s): %s", p, exc)
    return None


def _openai(prompt: str, size: str, transparent: bool) -> Optional[bytes]:
    body = {"model": settings.openai_image_model, "prompt": prompt[:30000], "size": size, "n": 1,
            "quality": settings.openai_image_quality}
    if transparent:
        body["background"] = "transparent"
        body["output_format"] = "png"
    r = httpx.post("https://api.openai.com/v1/images/generations", json=body, timeout=240,
                   headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI {r.status_code}: {r.text[:300]}")
    item = (r.json().get("data") or [{}])[0]
    if item.get("b64_json"):
        return _to_png(base64.b64decode(item["b64_json"]))
    if item.get("url"):
        return _to_png(httpx.get(item["url"], timeout=120).content)
    return None


def _gemini(prompt: str) -> Optional[bytes]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_image_model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
    r = httpx.post(url, json=body, timeout=240, headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
    for cand in r.json().get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return _to_png(base64.b64decode(inline["data"]))
    return None


def _to_png(data: bytes) -> bytes:
    from PIL import Image

    im = Image.open(io.BytesIO(data))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def recenter(png: bytes, *, canvas: int = 2048, fill: float = 0.74, background: Optional[str] = None) -> Tuple[bytes, str]:
    """Trim the empty margin around an AI logo and place it dead centre on a square canvas with even margins.
    Returns (png bytes, background colour used)."""
    from PIL import Image, ImageChops

    im = Image.open(io.BytesIO(png)).convert("RGBA")
    if im.getchannel("A").getextrema()[0] < 250:  # has transparency: crop to opaque pixels
        bbox = im.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
        bg = background or "#FFFFFF"
    else:
        rgb = im.convert("RGB")
        w, h = rgb.size
        corners = [rgb.getpixel((2, 2)), rgb.getpixel((w - 3, 2)), rgb.getpixel((2, h - 3)), rgb.getpixel((w - 3, h - 3))]
        r_, g_, b_ = (sum(c[i] for c in corners) // 4 for i in range(3))
        bg = background or f"#{r_:02X}{g_:02X}{b_:02X}"
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (r_, g_, b_))).convert("L").point(lambda v: 255 if v > 22 else 0)
        bbox = diff.getbbox()
    if bbox:
        im = im.crop(bbox)
    scale = canvas * fill / max(im.size)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (canvas, canvas), bg)
    out.alpha_composite(im, ((canvas - im.width) // 2, (canvas - im.height) // 2))
    buf = io.BytesIO()
    out.convert("RGB").save(buf, "PNG", optimize=True)
    return buf.getvalue(), bg
