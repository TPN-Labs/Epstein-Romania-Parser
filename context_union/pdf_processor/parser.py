"""
PDF parsing and email extraction.
"""

import os
import re
from typing import Optional, List

import pdfplumber

from .models import Document, EmailMessage
from .text_utils import (
    clean_text,
    extract_email_addresses,
    extract_names,
    extract_header_info,
    identify_document_type,
    parse_date,
)


def parse_email_thread(text: str, source_file: str) -> List[EmailMessage]:
    """Parse an email thread - extract main message AND quoted messages."""
    messages = []

    headers = extract_header_info(text)

    # Patterns indicating start of quoted content (with date extraction)
    quote_header_patterns = [
        # "On Thu, Dec 18, 2008 at 12:17 PM, Name <email> wrote:"
        r'On\s+([\w,\s]+\d{4}[,\s]+(?:at\s+)?\d{1,2}:\d{2}\s*(?:AM|PM)?)[,\s]*([^<\n]*)?(?:<([^>]+)>)?\s*(?:>?\s*wrote:)?',
    ]

    # Find the quote boundary
    quote_start = len(text)
    quote_match = None
    for pattern in quote_header_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and match.start() < quote_start:
            quote_start = match.start()
            quote_match = match

    # Also check simpler patterns that don't extract info
    simple_quote_patterns = [
        r'-{3,}\s*Original message\s*-{3,}',
        r'----+\s*Original message',
        r'Sent using BlackBerry',
        r'Sent from my iPhone',
        r'Sent from my iPod',
    ]
    for pattern in simple_quote_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and match.start() < quote_start:
            quote_start = match.start()
            quote_match = None  # Simple pattern, no metadata

    # Extract just the main message content
    main_content = text[:quote_start].strip()

    # Remove header lines from the body
    body_lines = main_content.split('\n')
    body_start_idx = 0
    for i, line in enumerate(body_lines):
        line_lower = line.lower().strip()
        if any(line_lower.startswith(h) for h in ['to:', 'from:', 'sent:', 'date:', 'subject:', 'fran:']):
            body_start_idx = i + 1
        elif line_lower and not any(line_lower.startswith(h) for h in ['to:', 'from:', 'sent:', 'date:', 'subject:', 'fran:']):
            break

    main_body = '\n'.join(body_lines[body_start_idx:]).strip()

    main_msg = EmailMessage(
        sender=headers.get('from', ''),
        recipient=headers.get('to', ''),
        date_str=headers.get('sent', ''),
        date=parse_date(headers.get('sent', '')),
        subject=headers.get('subject', ''),
        body=clean_text(main_body) if main_body else '',
        source_file=source_file,
        raw_text=main_content
    )

    if main_msg.body and len(main_msg.body.strip()) > 5:
        messages.append(main_msg)

    # Now extract the quoted message if we found one
    if quote_start < len(text):
        quoted_text = text[quote_start:].strip()
        quoted_msg = _parse_quoted_message(quoted_text, source_file, quote_match, main_msg)
        if quoted_msg and quoted_msg.body and len(quoted_msg.body.strip()) > 10:
            messages.append(quoted_msg)

    return messages


def _parse_quoted_message(quoted_text: str, source_file: str, quote_match, parent_msg: EmailMessage) -> Optional[EmailMessage]:
    """Parse a quoted message from email thread."""
    # Extract date and sender from the "On ... wrote:" line
    quoted_date_str = ""
    quoted_sender = ""

    if quote_match:
        # Group 1: date string, Group 2: name, Group 3: email
        if quote_match.lastindex >= 1:
            quoted_date_str = quote_match.group(1).strip() if quote_match.group(1) else ""
        if quote_match.lastindex >= 2:
            name = quote_match.group(2).strip().rstrip(',') if quote_match.group(2) else ""
            # Clean up name - remove trailing junk like "> wrote:" or ">"
            name = re.sub(r'\s*>?\s*wrote:?\s*$', '', name, flags=re.IGNORECASE).strip()
            name = name.rstrip('>').strip()
            if quote_match.lastindex >= 3 and quote_match.group(3):
                email = quote_match.group(3).strip()
                quoted_sender = f'"{name}" <{email}>' if name else email
            elif name:
                quoted_sender = name

    # Find the body - everything after "wrote:" line
    body_start = 0
    wrote_match = re.search(r'wrote:\s*', quoted_text, re.IGNORECASE)
    if wrote_match:
        body_start = wrote_match.end()
    else:
        # Try to find past the "On ... " line
        on_match = re.search(r'On\s+[^\n]+\n', quoted_text)
        if on_match:
            body_start = on_match.end()

    quoted_body = quoted_text[body_start:].strip()

    # Remove quote markers like "> " at the start of lines
    quoted_body = re.sub(r'^>\s?', '', quoted_body, flags=re.MULTILINE)

    # Remove trailing signature or additional quotes
    # Stop at next "On ... wrote:" pattern or signature
    next_quote = re.search(r'\n\s*On\s+[\w,\s]+\d{4}', quoted_body)
    if next_quote:
        quoted_body = quoted_body[:next_quote.start()]

    # Remove common signatures
    sig_patterns = [
        r'\n--\s*\n.*',
        r'\nSent from my.*',
        r'\n_{3,}.*',
    ]
    for pat in sig_patterns:
        quoted_body = re.sub(pat, '', quoted_body, flags=re.DOTALL | re.IGNORECASE)

    quoted_body = clean_text(quoted_body)

    # The recipient of the quoted message is the sender of the reply
    quoted_recipient = parent_msg.sender

    return EmailMessage(
        sender=quoted_sender,
        recipient=quoted_recipient,
        date_str=quoted_date_str,
        date=parse_date(quoted_date_str),
        subject=parent_msg.subject,
        body=quoted_body,
        source_file=source_file,
        raw_text=quoted_text[:500]  # Keep truncated for reference
    )


def parse_pdf(filepath: str) -> Optional[Document]:
    """Parse a single PDF file."""
    filename = os.path.basename(filepath)

    try:
        with pdfplumber.open(filepath) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return None

    if not text.strip():
        return None

    doc = Document(filename=filename)
    doc.text = text
    doc.doc_type = identify_document_type(text)
    doc.email_addresses = extract_email_addresses(text)
    doc.names = extract_names(text)

    headers = extract_header_info(text)
    doc.subject = headers.get('subject', '')

    if doc.doc_type == 'email':
        doc.emails = parse_email_thread(text, filename)
        for msg in doc.emails:
            if msg.sender:
                doc.participants.add(msg.sender)
            if msg.recipient:
                doc.participants.add(msg.recipient)
            if msg.date:
                doc.dates.append(msg.date)

    return doc
