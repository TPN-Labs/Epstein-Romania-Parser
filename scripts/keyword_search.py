"""Keyword matching and result handling."""

import re
from dataclasses import dataclass
from pathlib import Path


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

    Args:
        text: Text to search
        keywords: List of keywords to find
        context_chars: Characters to include around match

    Returns:
        List of (keyword, context) tuples
    """
    matches = []
    text_lower = text.lower()

    for keyword in keywords:
        # Find all occurrences
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        for match in pattern.finditer(text):
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
