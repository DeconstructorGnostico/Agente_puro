"""Utilidades de normalización de texto (sin dependencias)."""

from __future__ import annotations

import re
import unicodedata


def fold(text: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))
