"""
Text processing utilities for PDF content.
"""

import re
from typing import Optional, Set, Dict
from datetime import datetime
from dateutil import parser as date_parser

from .config import JUNK_PATTERNS


def clean_text(text: str) -> str:
    """Remove junk text patterns from extracted PDF text."""
    if not text:
        return ""

    cleaned = text

    for pattern in JUNK_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # Normalize whitespace
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()

    return cleaned


def normalize_email(email: str) -> str:
    """Normalize an email address, fixing common OCR errors."""
    email = email.lower().strip()

    # Fix common OCR errors in domain
    email = email.replace('Ogmail', '@gmail')
    email = email.replace('agmail', '@gmail')
    email = email.replace('egmail', '@gmail')
    email = email.replace('Sgmail', '@gmail')
    email = email.replace('@ernail', '@email')
    email = email.replace('@grnail', '@gmail')
    email = email.replace('®', '@')  # OCR often gets @ as ®

    # Fix common OCR errors in jeevacation specifically
    if 'vacation@' in email and email.startswith('j'):
        prefix = email.split('vacation@')[0]
        suffix = 'vacation@' + email.split('vacation@')[1]
        if len(prefix) <= 4 and prefix.startswith('j'):
            email = 'jeevacation@' + email.split('vacation@')[1]

    return email


def extract_email_addresses(text: str) -> Set[str]:
    """Extract all email addresses from text."""
    pattern = r'[\w\.\-®]+@[\w\.-]+\.\w+'
    emails = re.findall(pattern, text, re.IGNORECASE)
    cleaned = set()
    for email in emails:
        normalized = normalize_email(email)
        cleaned.add(normalized)
    return cleaned


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats found in emails."""
    if not date_str:
        return None

    date_str = re.sub(r'\s+', ' ', date_str.strip())

    try:
        return date_parser.parse(date_str, fuzzy=True)
    except:
        return None


def extract_header_info(text: str) -> Dict[str, str]:
    """Extract email headers from text."""
    headers = {}

    # Get only the first few lines for header extraction
    first_lines = '\n'.join(text.split('\n')[:10])

    # To field
    to_match = re.search(r'^To:\s*(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if to_match:
        headers['to'] = to_match.group(1).strip()

    # From field
    from_match = re.search(r'^From:\s*(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if from_match:
        headers['from'] = from_match.group(1).strip()

    # Sent/Date field
    sent_match = re.search(r'^(?:Sent|Date)[:\s]+(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if sent_match:
        headers['sent'] = sent_match.group(1).strip()

    # Subject field
    subj_match = re.search(r'^Subject:\s*(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if subj_match:
        headers['subject'] = subj_match.group(1).strip()

    return headers


def extract_names(text: str) -> Set[str]:
    """Extract potential person names from text."""
    names = set()

    known_names = [
        'Jeffrey Epstein', 'Ghislaine Maxwell', 'Virginia Giuffre',
        'Prince Andrew', 'Bill Clinton', 'Donald Trump'
    ]

    for name in known_names:
        if name.lower() in text.lower():
            names.add(name)

    # Pattern for names in email headers
    name_in_email = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*<', text)
    names.update(name_in_email)

    return names


def identify_document_type(text: str) -> str:
    """Identify the type of document based on content."""
    text_lower = text.lower()

    # Email indicators
    email_indicators = ['to:', 'from:', 'sent:', 'subject:', 'wrote:', 're:']
    email_score = sum(1 for ind in email_indicators if ind in text_lower)

    # Interview indicators
    interview_indicators = ['q:', 'a:', 'question:', 'answer:', 'interview', 'deposition']
    interview_score = sum(1 for ind in interview_indicators if ind in text_lower)

    # Financial indicators
    financial_indicators = ['account', 'balance', 'transaction', 'payment', 'invoice', '$', 'usd']
    financial_score = sum(1 for ind in financial_indicators if ind in text_lower)

    # Article indicators
    article_indicators = ['article', 'news', 'published', 'reporter', 'newspaper']
    article_score = sum(1 for ind in article_indicators if ind in text_lower)

    scores = {
        'email': email_score,
        'interview': interview_score,
        'financial': financial_score,
        'article': article_score
    }

    max_type = max(scores, key=scores.get)
    if scores[max_type] >= 2:
        return max_type
    return 'other'


def clean_message_body(body: str) -> str:
    """Clean up message body, removing duplicate headers and junk."""
    if not body:
        return ""

    body = clean_text(body)

    # Remove header info that might be duplicated
    body = re.sub(r'^To:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^From:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Fran:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Sent:?.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Subject:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Date:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)

    # Remove image metadata lines
    body = re.sub(r'^[Ii]?lane-Images:.*$', '', body, flags=re.MULTILINE)
    body = re.sub(r'^\d{4,}_\d+.*jpg.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^\d+\s+\d+;\s+\d+\s+\d+:\d+_\w+\.?jpg.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^\d{4,}\s+\d+;\s+\d+\s+\d+:\d+_njpg.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)

    # Remove lines that are just numbers (OCR artifacts)
    body = re.sub(r'^\s*\d{5,}\s*$', '', body, flags=re.MULTILINE)

    # Remove EFTA references
    body = re.sub(r'EFTA_R\d+_\d+\s*', '', body)
    body = re.sub(r'EFTA\d{8,}\s*', '', body)

    # Clean up multiple blank lines
    body = re.sub(r'\n{3,}', '\n\n', body)

    return body.strip()
