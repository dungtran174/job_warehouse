"""Conservative plain-text normalization with exact, terminated HTML entities."""

import re
import unicodedata
from html import unescape
from html.entities import html5

from job_warehouse.silver.models import TextResult

ENTITY = re.compile(r"&(?:#x[0-9A-Fa-f]+|#\d+|[A-Za-z][A-Za-z0-9]{1,31});")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HORIZONTAL = re.compile(r"[^\S\r\n]+")


def _decode(match: re.Match[str]) -> str:
    token = match.group()
    name = token[1:]
    if name in html5 or name.startswith("#"):
        return unescape(token)
    return token


def normalize_text(value: str | None, *, short: bool = False, max_depth: int = 4) -> TextResult:
    """Normalize raw input in plain mode; never strip tags or unknown entities.

    Replay means raw→clean. Depth-limited fallback retains the original normalized
    representation, so a second invocation cannot gradually decode deeper input.
    """
    if max_depth < 1:
        raise ValueError("Entity max_depth must be positive")
    if value is None:
        return TextResult(None, "missing")
    if not isinstance(value, str):
        raise TypeError("Text values must be strings or null")
    flags: set[str] = set()
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        flags.add("unicode_nfc")
    decoded = normalized
    depth = 0
    for step in range(1, max_depth + 1):
        following = ENTITY.sub(_decode, decoded)
        if following == decoded:
            break
        decoded = following
        depth = step
    if ENTITY.sub(_decode, decoded) != decoded:
        flags.add("entity_depth_exceeded")
        decoded, depth = normalized, 0
    elif depth:
        flags.add("entity_decoded")
    if "\ufffd" in decoded and "\ufffd" not in normalized:
        flags.add("entity_replacement_character")
    if CONTROL.search(decoded):
        flags.add("control_character_replaced")
        decoded = CONTROL.sub(" ", decoded)
    decoded = unicodedata.normalize("NFC", decoded).replace("\r\n", "\n").replace("\r", "\n")
    clean = re.sub(r"\s+", " ", decoded) if short else HORIZONTAL.sub(" ", decoded)
    clean = clean.strip()
    if clean != decoded:
        flags.add("whitespace_normalized")
    if not clean:
        return TextResult(None, "blank", tuple(sorted(flags)), depth)
    return TextResult(clean, "present", tuple(sorted(flags)), depth)


def normalize_content(value: str | None, *, requirements: bool = False) -> TextResult:
    result = normalize_text(value)
    if result.clean == ".":
        return TextResult(None, "placeholder", result.flags, result.decode_depth)
    if requirements and result.clean is not None:
        literal = result.clean.casefold()
        if literal == "không":
            return TextResult(result.clean, "ambiguous_literal", result.flags, result.decode_depth)
        if literal == "khác":
            return TextResult(result.clean, "other_unspecified", result.flags, result.decode_depth)
    return result
