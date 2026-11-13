"""Normalización de texto sin dependencias."""
from __future__ import annotations

import re
import unicodedata


def fold(text: str) -> str:
    """Minúsculas, sin acentos (ñ→n) y espacios colapsados."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


STOP = set("""a al algo como con de del el en es esta este la las lo los mas me mi mis muy no o para pero por que se si sin su sus te tu un una uno y ya yo
the a an and or of to for in on at with is are be it this that my your i you we our""".split())


def content_tokens(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP and len(t) > 2}
