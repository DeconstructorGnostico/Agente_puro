"""Normalización y utilidad de texto (español)."""

from __future__ import annotations

import re
import unicodedata

_STOPWORDS = {
    "a", "al", "algo", "algun", "alguna", "algunas", "algunos", "ante", "antes",
    "como", "con", "contra", "cual", "cuando", "de", "del", "desde", "donde",
    "durante", "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estas", "este", "esto", "estos",
    "ha", "haber", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me",
    "mi", "mis", "muy", "ni", "no", "nos", "o", "para", "pero", "por", "porque",
    "que", "se", "sea", "segun", "sin", "sobre", "su", "sus", "tambien", "te",
    "tiene", "todo", "un", "una", "unas", "unos", "y", "ya", "yo",
    "the", "and", "or", "of", "to", "for", "in", "on", "at", "with", "an",
}

_WORD_RE = re.compile(r"[a-z0-9áéíóúüñ]+", re.IGNORECASE)


def fold(text: str) -> str:
    """Minúsculas sin diacríticos (ñ se conserva como n)."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def tokenize(text: str, *, drop_stopwords: bool = False) -> list[str]:
    tokens = _WORD_RE.findall(fold(text))
    if drop_stopwords:
        return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return tokens


def token_set(text: str) -> set[str]:
    return set(tokenize(text, drop_stopwords=True))


def overlap(a: str, b: str) -> set[str]:
    return token_set(a) & token_set(b)


def first_sentence(text: str, max_len: int = 280) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    sentence = parts[0].strip()
    if len(sentence) > max_len:
        sentence = sentence[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return sentence


def clip(text: str, max_len: int = 400) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rsplit(" ", 1)[0] + "…"


def contains_any(text: str, needles: list[str] | tuple[str, ...]) -> list[str]:
    folded = fold(text)
    hits = []
    for needle in needles:
        if fold(needle) in folded:
            hits.append(needle)
    return hits
