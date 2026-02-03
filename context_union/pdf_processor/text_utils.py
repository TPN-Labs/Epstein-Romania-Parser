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


def fix_date_ocr_errors(date_str: str) -> str:
    """Fix common OCR errors in date strings."""
    if not date_str:
        return date_str

    # Fix letter/number confusions in day positions
    # "Sep I," -> "Sep 1," (letter I for number 1)
    # "Sep l," -> "Sep 1," (lowercase L for number 1)
    date_str = re.sub(r'([A-Za-z]{3,})\s+([Il])\s*,', r'\1 1,', date_str)
    date_str = re.sub(r'([A-Za-z]{3,})\s+([Il])(\s|$)', r'\1 1\3', date_str)

    # Fix "O" for "0" in dates (e.g., "2OO9" -> "2009", "O1" -> "01")
    # But be careful not to replace O in month names
    date_str = re.sub(r'(\d)O', r'\g<1>0', date_str)  # 2O -> 20
    date_str = re.sub(r'O(\d)', r'0\1', date_str)      # O9 -> 09

    # Fix "S" for "5" (e.g., "200S" -> "2005")
    date_str = re.sub(r'(\d{3})S(\s|$|,)', r'\g<1>5\2', date_str)

    # Fix "B" for "8" in years
    date_str = re.sub(r'(\d{2})B(\d)', r'\g<1>8\2', date_str)

    # Fix common month OCR errors
    date_str = re.sub(r'\blan\b', 'Jan', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bJari\b', 'Jan', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bMar\s*ch\b', 'March', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bApr\s*il\b', 'April', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bJuiy\b', 'July', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bAugust\b', 'August', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bSept\b', 'Sep', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bNov\s*ember\b', 'November', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bDec\s*ember\b', 'December', date_str, flags=re.IGNORECASE)

    # Fix ":" confused with ";" in times
    date_str = re.sub(r'(\d{1,2});(\d{2})\s*(AM|PM|am|pm)', r'\1:\2 \3', date_str)

    # Fix spaces in times (e.g., "8: 21" -> "8:21")
    date_str = re.sub(r'(\d{1,2}):\s+(\d{2})', r'\1:\2', date_str)

    # Fix "l" for "1" in times (e.g., "l2:30" -> "12:30")
    date_str = re.sub(r'\bl(\d:\d{2})', r'1\1', date_str)

    return date_str


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats found in emails."""
    if not date_str:
        return None

    date_str = re.sub(r'\s+', ' ', date_str.strip())

    # Fix OCR errors before parsing
    date_str = fix_date_ocr_errors(date_str)

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

    # Remove email confidentiality footers (with or without quote markers)
    # Pattern for "The information contained in this communication..." footer
    body = re.sub(
        r'(?:^>?\s*[w\*]{5,}\s*\n)?'  # Optional asterisk/w line
        r'(?:^>?\s*)*The information contained in this communication is'
        r'[\s\S]*?'
        r'(?:including all attachments|all copies thereof|attachments)\s*\.?',
        '', body, flags=re.MULTILINE | re.IGNORECASE
    )

    # Remove lines that are just quote markers and asterisks/w characters
    body = re.sub(r'^>\s*[w\*]+\s*$', '', body, flags=re.MULTILINE)

    # Remove "property of Jeffrey Epstein" footer fragments
    body = re.sub(
        r'(?:^>?\s*)*(?:It is the )?property of\s*\n?(?:^>?\s*)*Jeffrey Epstein[\s\S]*?(?:attachments\.?|thereof[,.])',
        '', body, flags=re.MULTILINE | re.IGNORECASE
    )

    # Remove standalone confidentiality fragments that might remain
    body = re.sub(r'(?:^>?\s*)*and may be unlawful[\s\S]*?attachments\.?', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'(?:^>?\s*)*confidential,?\s*may be attorney-client privileged[\s\S]*?addressee\.?', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'(?:^>?\s*)*If you have received this[\s\S]*?(?:attachments\.?|thereof[,.])', '', body, flags=re.MULTILINE | re.IGNORECASE)

    # Clean up multiple blank lines
    body = re.sub(r'\n{3,}', '\n\n', body)

    return body.strip()
