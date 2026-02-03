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
    """Parse an email thread - extract only the main/top message, not quoted content."""
    messages = []

    headers = extract_header_info(text)

    # Patterns indicating start of quoted content
    quote_start_patterns = [
        r'On\s+\w{3},\s+\w{3}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}',
        r'On\s+[\w,\s]+\d{4}[,\s]+(?:at\s+)?\d{1,2}:\d{2}[^<]*<[^>]+>\s*wrote:',
        r'On\s+[\w,\s]+\d{4}[,\s]+\d{1,2}:\d{2}\s*(?:AM|PM)?[^<]*wrote:',
        r'-{3,}\s*Original message\s*-{3,}',
        r'----+\s*Original message',
        r'^>{1,2}\s*On\s+',
        r'Sent using BlackBerry',
        r'Sent from my iPhone',
        r'Sent from my iPod',
        r'\nFrom:\s*[^\n]+\nDate:',
    ]

    # Find the earliest quote boundary
    quote_start = len(text)
    for pattern in quote_start_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and match.start() < quote_start:
            quote_start = match.start()

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

    return messages


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
