"""
text_sanitizer.py
Text Sanitization and Cleaning Pipeline for Astronomical Corpus Ingestion.

Ensures clean, robust text ingestion into LightRAG by:
1. Stripping Unicode replacement characters (\ufffd), zero-width characters, and control codes.
2. Removing OCR noise, dead image links (![...](...)), base64 blobs, and empty broken markdown tables.
3. Normalizing floating page numbers, running headers, and excessive empty lines.
4. Pre-filtering sensitive/non-astronomical terms that trigger API 422 censorship errors.
5. Providing chunk-level validation before embedding/graph extraction.
"""
import re
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger("astronomy_lightrag.text_sanitizer")

# ── 1. Regular Expression Patterns ───────────────────────────────────────────

# Invisible control characters (excluding \t, \n, \r)
RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Zero-width spaces and byte-order-marks
RE_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060]")

# Unicode replacement character
RE_REPLACEMENT_CHAR = re.compile(r"\ufffd")

# Embedded image markdown: ![alt](url)
# Especially removes base64 data images or pure file links
RE_MARKDOWN_IMAGES = re.compile(r"!\[([^\]]*)\]\([^)]+\)")

# Broken or empty HTML tags like <img ...>, <br>, etc.
RE_HTML_IMG_TAGS = re.compile(r"<img\b[^>]*>", re.IGNORECASE)

# Isolated page numbers: lines consisting solely of "Page 123", "p. 45", or bare numbers
RE_PAGE_NUMBERS = re.compile(
    r"(?m)^\s*(?:Page|p\.|P\.)?\s*\d{1,4}\s*$",
    re.IGNORECASE
)

# Broken markdown table lines (pure dashes and pipes without text)
RE_EMPTY_TABLE_ROWS = re.compile(r"(?m)^\s*\|(?:\s*[-:]+\s*\|)+\s*$")

# Repetitive empty lines (more than 3 consecutive newlines)
RE_EXCESSIVE_NEWLINES = re.compile(r"\n{4,}")

# Consecutive horizontal rules or junk delimiters
RE_EXCESSIVE_DIVIDERS = re.compile(r"(?m)^(?:[-*_~]{3,}\s*){2,}")

# ── 2. Anti-Censorship / Safety Filter for Online LLMs ────────────────────────
# Maps known false-positive triggering words or non-astronomy sensitive phrases to neutral equivalents
SENSITIVE_SUBSTITUTIONS = {
    # If any OCR artifact or historical footnote contains sensitive phrases, neutralize
    r"\b(法轮功|FLG)\b": "[REDACTED]",
    r"\b(六四|8964|天安门事件)\b": "[REDACTED_EVENT]",
    # Common OCR false joins that look like profanity or banned phrases
}

COMPILED_SENSITIVE_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), repl)
    for pat, repl in SENSITIVE_SUBSTITUTIONS.items()
]


def clean_markdown_text(
    text: str,
    keep_image_captions: bool = True,
    remove_page_numbers: bool = True,
    apply_safety_filter: bool = True
) -> str:
    """
    Cleans raw Markdown book content prior to chunking and LightRAG ingestion.

    Args:
        text: Raw markdown text string from MinerU/OCR or translated book.
        keep_image_captions: If True, preserves ![Caption](url) as ' [图: Caption] '.
        remove_page_numbers: If True, strips isolated page number lines.
        apply_safety_filter: If True, replaces API-blocking sensitive keywords.

    Returns:
        Sanitized markdown string.
    """
    if not text:
        return ""

    # 1. Clean control characters and zero-width codes
    cleaned = RE_CONTROL_CHARS.sub("", text)
    cleaned = RE_ZERO_WIDTH.sub("", cleaned)
    cleaned = RE_REPLACEMENT_CHAR.sub("", cleaned)

    # 2. Clean HTML image tags
    cleaned = RE_HTML_IMG_TAGS.sub("", cleaned)

    # 3. Clean Markdown images
    if keep_image_captions:
        # Retain descriptive caption if available
        cleaned = RE_MARKDOWN_IMAGES.sub(lambda m: f" [图: {m.group(1)}] " if m.group(1).strip() else "", cleaned)
    else:
        cleaned = RE_MARKDOWN_IMAGES.sub("", cleaned)

    # 4. Remove isolated page numbers
    if remove_page_numbers:
        cleaned = RE_PAGE_NUMBERS.sub("", cleaned)

    # 5. Remove empty table rows
    cleaned = RE_EMPTY_TABLE_ROWS.sub("", cleaned)

    # 6. Apply safety/censorship filter
    if apply_safety_filter:
        for pattern, replacement in COMPILED_SENSITIVE_PATTERNS:
            if pattern.search(cleaned):
                cleaned = pattern.sub(replacement, cleaned)
                logger.warning(f"Sanitized sensitive term matching pattern '{pattern.pattern}'")

    # 7. Normalize whitespace and newlines
    cleaned = RE_EXCESSIVE_DIVIDERS.sub("---", cleaned)
    cleaned = RE_EXCESSIVE_NEWLINES.sub("\n\n\n", cleaned)

    return cleaned.strip()


def validate_text_chunk(chunk: str, min_chars: int = 30) -> Tuple[bool, str]:
    """
    Validates whether a text chunk is meaningful for knowledge graph extraction.

    Args:
        chunk: Text chunk string to evaluate.
        min_chars: Minimum character threshold for a meaningful chunk.

    Returns:
        tuple (is_valid, rejection_reason)
    """
    if not chunk or not chunk.strip():
        return False, "Empty or whitespace-only chunk"

    stripped = chunk.strip()

    if len(stripped) < min_chars:
        return False, f"Chunk too short (< {min_chars} chars): {len(stripped)}"

    # Check alphanumeric content ratio (must not be pure punctuation/special characters)
    alnum_count = sum(1 for c in stripped if c.isalnum() or '\u4e00' <= c <= '\u9fff')
    if alnum_count / len(stripped) < 0.3:
        return False, f"Low alphanumeric density ({alnum_count}/{len(stripped)})"

    # Reject if it's purely a table of contents or index page consisting of dots/numbers
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if lines:
        toc_like = sum(1 for line in lines if re.search(r"\.{4,}\s*\d+$", line))
        if toc_like / len(lines) > 0.6:
            return False, "Detected high density Table of Contents / Index pattern"

    return True, "Valid"
