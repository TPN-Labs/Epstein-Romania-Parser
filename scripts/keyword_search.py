"""Keyword matching and result handling."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


def normalize_text(text: str) -> str:
    """
    Normalize text by removing diacritics for comparison.

    Converts characters like 'ș', 'ț', 'ă', 'â', 'î' to their base forms
    ('s', 't', 'a', 'a', 'i') to enable diacritic-insensitive matching.

    Args:
        text: Text to normalize

    Returns:
        Text with diacritics removed
    """
    # NFD decomposes characters (e.g., 'ș' -> 's' + combining cedilla)
    # Then we remove all combining marks (diacritics)
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


@dataclass
class SearchResult:
    """A single keyword match result."""
    folder: str
    filename: str
    page: int
    keyword: str
    context: str


def load_keywords(filepath: str | Path) -> list[str]:
    """
    Load keywords from a text file (one per line).

    Args:
        filepath: Path to keywords file

    Returns:
        List of keywords (lowercase, stripped)
    """
    keywords = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            keyword = line.strip().lower()
            if keyword:
                keywords.append(keyword)
    return keywords


def search_text(
    text: str,
    keywords: list[str],
    context_chars: int = 50
) -> list[tuple[str, str]]:
    """
    Find keyword matches in text with surrounding context.

    Matching is case-insensitive and diacritic-insensitive, so searching for
    "timisoara" will match "Timișoara", "TIMISOARA", "tiMiSoara", etc.

    Args:
        text: Text to search
        keywords: List of keywords to find
        context_chars: Characters to include around match

    Returns:
        List of (keyword, context) tuples
    """
    matches = []
    # Normalize text for diacritic-insensitive comparison
    text_normalized = normalize_text(text).lower()

    for keyword in keywords:
        # Normalize keyword for matching
        keyword_normalized = normalize_text(keyword).lower()
        # Find all occurrences in normalized text
        pattern = re.compile(re.escape(keyword_normalized), re.IGNORECASE)
        for match in pattern.finditer(text_normalized):
            # Use match positions to extract context from original text
            # (preserving original characters including diacritics)
            start = max(0, match.start() - context_chars)
            end = min(len(text), match.end() + context_chars)
            context = text[start:end].replace("\n", " ").strip()
            # Add ellipsis if truncated
            if start > 0:
                context = "..." + context
            if end < len(text):
                context = context + "..."
            matches.append((keyword, context))

    return matches


def create_result(
    folder: str,
    filename: str,
    page: int,
    keyword: str,
    context: str
) -> SearchResult:
    """Create a SearchResult instance."""
    return SearchResult(
        folder=folder,
        filename=filename,
        page=page,
        keyword=keyword,
        context=context
    )
