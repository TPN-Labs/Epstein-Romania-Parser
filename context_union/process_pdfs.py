#!/usr/bin/env python3
"""
PDF Email Unification Script
Processes PDF files containing emails, identifies related/linked files,
and produces consolidated markdown reports.
"""

import os
import re
import json
import hashlib
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple
from pathlib import Path

import pdfplumber
from dateutil import parser as date_parser
from rapidfuzz import fuzz

# Configuration
PDF_DIR = Path("/Volumes/Maurice_SSD/Projects/EpParser/context_union/pdfs")
OUTPUT_DIR = Path("/Volumes/Maurice_SSD/Projects/EpParser/context_union/output_report")
CACHE_FILE = Path("/Volumes/Maurice_SSD/Projects/EpParser/context_union/.pdf_cache.json")

# Junk text patterns to remove
JUNK_PATTERNS = [
    # Confidentiality disclaimers
    r'\*{10,}[\s\S]*?The information contained in this communication is[\s\S]*?all rights reserved[\s\S]*?\*{5,}',
    r'The information contained in this communication is\s*confidential[\s\S]*?including all attachments\.?',
    r'\*{10,}[\s\S]*?confidential[\s\S]*?attachments[\s\S]*?\*{5,}',
    r'Unauthorized use,?\s*disc[\s\S]*?prohibited',
    r'copyright\s*-?\s*all rights reserved',
    # Sent from devices
    r'Sent from my iP(?:hone|od|ad)',
    r'Sent from Samsung Mobile',
    r'Sent from my BlackBerry',
    r'Sent from (?:a )?Samsung (?:device|Galaxy)',
    r'Sent from Samaung Malib',  # OCR typo
    r'Sent Irma Sainting.*',  # OCR artifact
    r'Sag from Si mmg Mat',  # OCR artifact
    # EFTA reference numbers at page bottoms
    r'EFTA_R\d+_\d+',
    r'EFTA\d{8,}(?:\s|$)',
    # XML/plist artifacts
    r'<\?xml[\s\S]*?\?>',
    r'<!DOCTYPE[\s\S]*?>',
    # Multiple asterisks
    r'\*{5,}',
    # Extra whitespace normalization
    r'\n{3,}',
]

@dataclass
class EmailMessage:
    """Represents a single email message extracted from a PDF"""
    sender: str = ""
    recipient: str = ""
    date: Optional[datetime] = None
    date_str: str = ""
    subject: str = ""
    body: str = ""
    source_file: str = ""
    raw_text: str = ""

    def __hash__(self):
        # Hash based on content for deduplication
        return hash((self.sender, self.recipient, self.date_str, self.body[:200] if self.body else ""))

    def __eq__(self, other):
        if not isinstance(other, EmailMessage):
            return False
        return (self.sender == other.sender and
                self.recipient == other.recipient and
                self.date_str == other.date_str and
                (self.body[:200] if self.body else "") == (other.body[:200] if other.body else ""))

@dataclass
class Document:
    """Represents a parsed PDF document"""
    filename: str
    doc_type: str = "unknown"  # email, interview, article, financial, other
    text: str = ""
    emails: List[EmailMessage] = field(default_factory=list)
    participants: Set[str] = field(default_factory=set)
    email_addresses: Set[str] = field(default_factory=set)
    dates: List[datetime] = field(default_factory=list)
    names: Set[str] = field(default_factory=set)
    subject: str = ""

@dataclass
class Conversation:
    """A group of related documents forming a conversation"""
    id: int
    documents: List[Document] = field(default_factory=list)
    messages: List[EmailMessage] = field(default_factory=list)
    participants: Set[str] = field(default_factory=set)
    subject: str = ""
    date_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
    confidence: str = "high"  # high, probable


class NameRegistry:
    """Tracks names across documents for cross-referencing censored names"""
    def __init__(self):
        self.email_to_names: Dict[str, Set[str]] = defaultdict(set)
        self.name_occurrences: Dict[str, List[str]] = defaultdict(list)  # name -> [source files]
        self.censored_resolutions: Dict[str, Dict[str, str]] = {}  # email -> {source_file: resolved_name}

    def register_name(self, name: str, email: str, source_file: str):
        """Register a name associated with an email"""
        if name and email:
            self.email_to_names[email.lower()].add(name)
            self.name_occurrences[name].append(source_file)

    def resolve_censored(self, email: str, context: str = "") -> str:
        """Try to resolve a censored name by email address"""
        email_lower = email.lower() if email else ""
        if email_lower in self.email_to_names:
            names = self.email_to_names[email_lower]
            if names:
                name = list(names)[0]
                sources = self.name_occurrences.get(name, [])
                if sources:
                    return f"[REDACTED - identified as: {name} in {sources[0]}]"
        return "[REDACTED]"


def clean_text(text: str) -> str:
    """Remove junk text patterns from extracted PDF text"""
    if not text:
        return ""

    cleaned = text

    # Apply all junk patterns
    for pattern in JUNK_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # Normalize whitespace
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()

    return cleaned


def normalize_email(email: str) -> str:
    """Normalize an email address, fixing common OCR errors"""
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
    # jcovacation, jccvacation, jecvacation, etc. -> jeevacation
    if 'vacation@' in email and email.startswith('j'):
        prefix = email.split('vacation@')[0]
        suffix = 'vacation@' + email.split('vacation@')[1]
        # Normalize j*vacation to jeevacation
        if len(prefix) <= 4 and prefix.startswith('j'):
            email = 'jeevacation@' + email.split('vacation@')[1]

    return email


def extract_email_addresses(text: str) -> Set[str]:
    """Extract all email addresses from text"""
    pattern = r'[\w\.\-®]+@[\w\.-]+\.\w+'
    emails = re.findall(pattern, text, re.IGNORECASE)
    cleaned = set()
    for email in emails:
        normalized = normalize_email(email)
        cleaned.add(normalized)
    return cleaned


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats found in emails"""
    if not date_str:
        return None

    # Clean up the date string
    date_str = re.sub(r'\s+', ' ', date_str.strip())

    # Handle various formats
    formats_to_try = [
        r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM)?)',
        r'(\w+\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)',
        r'(\d{4}/\d{1,2}/\d{1,2})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
    ]

    try:
        return date_parser.parse(date_str, fuzzy=True)
    except:
        return None


def extract_header_info(text: str) -> Dict[str, str]:
    """Extract email headers from text"""
    headers = {}

    # Get only the first few lines for header extraction to avoid false matches
    first_lines = '\n'.join(text.split('\n')[:10])

    # To field - look in first few lines
    to_match = re.search(r'^To:\s*(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if to_match:
        headers['to'] = to_match.group(1).strip()

    # From field - look in first few lines
    from_match = re.search(r'^From:\s*(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if from_match:
        headers['from'] = from_match.group(1).strip()

    # Sent/Date field - look in first few lines
    sent_match = re.search(r'^(?:Sent|Date)[:\s]+(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if sent_match:
        headers['sent'] = sent_match.group(1).strip()

    # Subject field - look in first few lines
    subj_match = re.search(r'^Subject:\s*(.+?)(?:\n|$)', first_lines, re.IGNORECASE | re.MULTILINE)
    if subj_match:
        headers['subject'] = subj_match.group(1).strip()

    return headers


def parse_email_thread(text: str, source_file: str) -> List[EmailMessage]:
    """Parse an email thread - extract only the main/top message, not quoted content"""
    messages = []

    # Get the main email headers
    headers = extract_header_info(text)

    # Find where quoted content begins (to exclude it from main body)
    # Patterns indicating start of quoted content
    quote_start_patterns = [
        r'On\s+\w{3},\s+\w{3}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}',  # On Thu, Dec 18, 2008 at 12:17 PM
        r'On\s+[\w,\s]+\d{4}[,\s]+(?:at\s+)?\d{1,2}:\d{2}[^<]*<[^>]+>\s*wrote:',
        r'On\s+[\w,\s]+\d{4}[,\s]+\d{1,2}:\d{2}\s*(?:AM|PM)?[^<]*wrote:',
        r'-{3,}\s*Original message\s*-{3,}',
        r'----+\s*Original message',
        r'^>{1,2}\s*On\s+',  # Quoted with >
        r'Sent using BlackBerry',  # BlackBerry signature before quoted content
        r'Sent from my iPhone',
        r'Sent from my iPod',
        r'\nFrom:\s*[^\n]+\nDate:',  # Forwarded email header block
    ]

    # Find the earliest quote boundary
    quote_start = len(text)
    for pattern in quote_start_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and match.start() < quote_start:
            quote_start = match.start()

    # Extract just the main message content (before quotes)
    main_content = text[:quote_start].strip()

    # Remove header lines from the body portion
    body_lines = main_content.split('\n')
    body_start_idx = 0
    for i, line in enumerate(body_lines):
        line_lower = line.lower().strip()
        if any(line_lower.startswith(h) for h in ['to:', 'from:', 'sent:', 'date:', 'subject:', 'fran:']):
            body_start_idx = i + 1
        elif line_lower and not any(line_lower.startswith(h) for h in ['to:', 'from:', 'sent:', 'date:', 'subject:', 'fran:']):
            # Found actual content
            break

    main_body = '\n'.join(body_lines[body_start_idx:]).strip()

    # Create the main message
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

    # Only add if there's meaningful content
    if main_msg.body and len(main_msg.body.strip()) > 5:
        messages.append(main_msg)

    return messages


def identify_document_type(text: str) -> str:
    """Identify the type of document based on content"""
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


def extract_names(text: str) -> Set[str]:
    """Extract potential person names from text"""
    names = set()

    # Known names to look for
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


def parse_pdf(filepath: str) -> Optional[Document]:
    """Parse a single PDF file"""
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

    # Extract headers for subject
    headers = extract_header_info(text)
    doc.subject = headers.get('subject', '')

    # Parse email thread if it's an email
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


def calculate_link_score(doc1: Document, doc2: Document) -> Tuple[float, str]:
    """Calculate how likely two documents are part of the same conversation thread"""
    score = 0.0
    reasons = []

    # Common email addresses that should be excluded from scoring
    # (too common to be meaningful for linking)
    common_emails_to_ignore = {
        'jeevacation@gmail.com',
        'jee@his.com',
        'je@his.com',
    }

    # Quoted text matching - strong signal for same thread
    # But need to be careful to avoid matching common boilerplate
    if doc1.text and doc2.text:
        # Clean texts to remove common boilerplate that causes false matches
        def clean_for_matching(text):
            # Remove confidentiality disclaimers
            text = re.sub(r'The information contained in this communication[\s\S]*?all attachments\.?', '', text, flags=re.IGNORECASE)
            # Remove signatures
            text = re.sub(r'\*{5,}[\s\S]*?\*{5,}', '', text)
            # Remove EFTA references
            text = re.sub(r'EFTA\w*\d+', '', text)
            # Remove sent from device
            text = re.sub(r'Sent from my \w+', '', text, flags=re.IGNORECASE)
            # Remove email headers for matching
            text = re.sub(r'^(To|From|Sent|Subject|Date):.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
            return text

        clean1 = clean_for_matching(doc1.text)
        clean2 = clean_for_matching(doc2.text)

        # Check for substantial quoted text overlap (100+ chars of actual content)
        matched = False
        for i in range(0, len(clean1) - 100, 50):
            chunk = clean1[i:i+100]
            # Skip if chunk is mostly whitespace/junk
            if len(chunk.strip()) < 80:
                continue
            # Skip if chunk is mostly asterisks, dashes, or punctuation
            alpha_count = sum(1 for c in chunk if c.isalpha())
            if alpha_count < 40:
                continue
            if chunk in clean2:
                score += 60
                reasons.append("quoted text match")
                matched = True
                break

        if not matched:
            # Try reverse direction
            for i in range(0, len(clean2) - 100, 50):
                chunk = clean2[i:i+100]
                if len(chunk.strip()) < 80:
                    continue
                alpha_count = sum(1 for c in chunk if c.isalpha())
                if alpha_count < 40:
                    continue
                if chunk in clean1:
                    score += 60
                    reasons.append("quoted text match")
                    break

    # Same subject line (strong signal)
    if doc1.subject and doc2.subject:
        subj1 = re.sub(r'^(Re:\s*)+', '', doc1.subject, flags=re.IGNORECASE).strip()
        subj2 = re.sub(r'^(Re:\s*)+', '', doc2.subject, flags=re.IGNORECASE).strip()
        if subj1 and subj2 and len(subj1) > 3 and len(subj2) > 3:
            similarity = fuzz.ratio(subj1.lower(), subj2.lower())
            if similarity > 95:
                score += 50
                reasons.append("matching subject")
            elif similarity > 80:
                score += 25
                reasons.append("similar subject")

    # Close EFTA numbers AND same date = strong signal
    efta1 = re.search(r'EFTA(\d+)', doc1.filename)
    efta2 = re.search(r'EFTA(\d+)', doc2.filename)
    efta_close = False
    if efta1 and efta2:
        diff = abs(int(efta1.group(1)) - int(efta2.group(1)))
        if diff < 50:
            efta_close = True
            score += 10
            reasons.append("very close EFTA numbers")

    # Same date (moderate signal, stronger if EFTA close)
    same_date = False
    if doc1.dates and doc2.dates:
        for d1 in doc1.dates:
            for d2 in doc2.dates:
                if d1 and d2:
                    try:
                        d1_naive = d1.replace(tzinfo=None) if d1.tzinfo else d1
                        d2_naive = d2.replace(tzinfo=None) if d2.tzinfo else d2
                        diff = abs((d1_naive - d2_naive).days)
                        if diff == 0:
                            same_date = True
                            break
                    except:
                        pass
            if same_date:
                break

    if same_date and efta_close:
        score += 30
        reasons.append("same date + close EFTA")
    elif same_date:
        score += 5  # Same date alone is weak (many emails on same day)

    # Overlapping email addresses (only count non-common ones)
    email1_filtered = doc1.email_addresses - common_emails_to_ignore
    email2_filtered = doc2.email_addresses - common_emails_to_ignore
    common_emails = email1_filtered & email2_filtered

    if len(common_emails) >= 2:
        # Multiple non-common email addresses = moderate signal
        score += 20
        reasons.append(f"{len(common_emails)} shared emails")
    elif len(common_emails) == 1 and same_date:
        # One shared email + same date = weak signal
        score += 10
        reasons.append("1 shared email + same date")

    confidence = "high" if score >= 70 else "probable" if score >= 40 else "low"
    return score, confidence, "; ".join(reasons) if reasons else "no link"


def cluster_documents(documents: List[Document], threshold: float = 40.0) -> List[List[Document]]:
    """Cluster related documents together into conversation threads"""
    n = len(documents)

    # Build adjacency list based on link scores
    links = defaultdict(list)

    print(f"Calculating link scores for {n} documents...")
    total_pairs = n * (n - 1) // 2
    checked = 0

    for i in range(n):
        for j in range(i + 1, n):
            score, confidence, reason = calculate_link_score(documents[i], documents[j])
            if score >= threshold:
                links[i].append((j, score, confidence, reason))
                links[j].append((i, score, confidence, reason))

            checked += 1
            if checked % 10000 == 0:
                print(f"  Progress: {checked}/{total_pairs} pairs checked...")

    # Use union-find to cluster, but with size limits
    parent = list(range(n))
    rank = [0] * n

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def get_cluster_size(x):
        root = find(x)
        count = 0
        for i in range(n):
            if find(i) == root:
                count += 1
        return count

    def union(x, y, score):
        px, py = find(x), find(y)
        if px == py:
            return

        # Limit cluster size to prevent mega-clusters
        # Only merge if score is very high (quoted text) or clusters are small
        size_px = get_cluster_size(px)
        size_py = get_cluster_size(py)

        max_cluster_size = 15  # Max docs per conversation
        if size_px + size_py > max_cluster_size and score < 70:
            return  # Don't merge unless very strong link

        if rank[px] < rank[py]:
            parent[px] = py
        elif rank[px] > rank[py]:
            parent[py] = px
        else:
            parent[py] = px
            rank[px] += 1

    # Sort links by score (highest first) to prioritize strong links
    all_links = []
    for i in range(n):
        for j, score, conf, reason in links[i]:
            if i < j:
                all_links.append((score, i, j, conf, reason))

    all_links.sort(reverse=True)

    # Union documents starting with strongest links
    for score, i, j, conf, reason in all_links:
        union(i, j, score)

    # Group by cluster
    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(documents[i])

    return list(clusters.values())


def deduplicate_messages(messages: List[EmailMessage]) -> List[EmailMessage]:
    """Remove duplicate messages that appear in multiple quoted threads"""
    if not messages:
        return []

    unique = []
    seen_sigs = set()

    for msg in messages:
        if not msg.body:
            continue

        # Create a normalized signature based on cleaned body content
        body_clean = msg.body.strip()
        # Remove quoted text indicators
        body_clean = re.sub(r'^>.*$', '', body_clean, flags=re.MULTILINE)
        # Remove "On date, X wrote:" patterns (quoted headers)
        body_clean = re.sub(r'On\s+[\w,\s]+\d{4}.*?wrote:', '', body_clean, flags=re.IGNORECASE | re.DOTALL)
        # Remove "Subject Re:" type headers
        body_clean = re.sub(r'^Subject\s*Re:?\s*', '', body_clean, flags=re.MULTILINE | re.IGNORECASE)
        # Normalize whitespace
        body_clean = re.sub(r'\s+', ' ', body_clean).strip().lower()

        # Use the full cleaned content as signature for short messages,
        # first 100 chars for longer ones
        if len(body_clean) < 100:
            body_sig = body_clean
        else:
            body_sig = body_clean[:100]

        # Skip empty bodies
        if not body_sig:
            continue

        # Check if we've seen this exact signature
        if body_sig in seen_sigs:
            continue

        # Check for substring matches with existing messages
        is_duplicate = False
        for existing_sig in list(seen_sigs):
            # Check if one is contained in the other (for longer messages)
            if len(body_sig) > 20 and len(existing_sig) > 20:
                if body_sig in existing_sig or existing_sig in body_sig:
                    is_duplicate = True
                    break

        if not is_duplicate:
            seen_sigs.add(body_sig)
            unique.append(msg)

    return unique


def sort_messages_chronologically(messages: List[EmailMessage]) -> List[EmailMessage]:
    """Sort messages by date, oldest first"""
    def get_sort_key(msg):
        dt = None
        if msg.date:
            dt = msg.date
        elif msg.date_str:
            dt = parse_date(msg.date_str)

        if dt:
            # Make naive for consistent sorting
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt

        return datetime.max  # Put undated messages at the end

    return sorted(messages, key=get_sort_key)


def format_participant(participant: str, name_registry: NameRegistry) -> str:
    """Format a participant, resolving censored names if possible"""
    if not participant:
        return "[Unknown]"

    # Check if name is censored (empty or just email)
    participant = participant.strip()

    # Extract email if present
    email_match = re.search(r'<([^>]+)>', participant)
    email = email_match.group(1) if email_match else ""

    # Extract name part
    name_part = re.sub(r'<[^>]+>', '', participant).strip()

    # If no name but have email, try to resolve
    if not name_part and email:
        return name_registry.resolve_censored(email)

    return participant


def clean_participant(p: str) -> str:
    """Clean up participant string - extract just name and email"""
    if not p:
        return ""

    p = p.strip()

    # Skip if it looks like quoted message text
    if 'wrote:' in p.lower() or len(p) > 80:
        return ""

    # Skip if starts with "On " (date line from quoted message)
    if p.startswith('On '):
        return ""

    # Skip lines that are clearly message content
    if p.startswith('I ') or p.startswith('i ') or 'Sent from' in p:
        return ""

    # Skip garbled OCR text
    if p.startswith('ein(') or p.startswith('eini') or p.startswith('• '):
        return ""

    # Extract email if present - handle various bracket types
    email_match = re.search(r'[<\[\(]([^>\]\)]+@[^>\]\)]+)[>\]\)]', p)
    if email_match:
        email = normalize_email(email_match.group(1))
        # Extract name before email
        name_part = re.sub(r'[<\[\(].*', '', p).strip()
        # Clean up name - remove "On date, at time" prefix if present
        name_part = re.sub(r'^On.*?,\s*', '', name_part)
        if name_part and len(name_part) < 40 and not name_part.startswith('On '):
            return f"{name_part} <{email}>"
        else:
            return email

    # If it's just an email address (possibly with OCR brackets)
    email_only = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', p)
    if email_only:
        return normalize_email(email_only.group(0))

    # If it's just a name (short, no special chars)
    if len(p) < 40 and not any(c in p for c in [':', '@', '>', '<', '\n', '(']):
        # Skip numeric-only entries (likely OCR artifacts)
        if not re.match(r'^[\d\.\s]+$', p):
            return p

    return ""


def generate_markdown(conversation: Conversation, name_registry: NameRegistry) -> str:
    """Generate markdown output for a conversation"""
    lines = []

    lines.append(f"# Conversation {conversation.id:03d}")
    lines.append("")
    lines.append("## Metadata")

    # Source files
    source_files = sorted(set(doc.filename for doc in conversation.documents))
    lines.append(f"- **Original PDFs**: {', '.join(source_files)}")

    # Subject
    if conversation.subject:
        lines.append(f"- **Subject**: {conversation.subject}")

    # Date range
    if conversation.date_range[0] and conversation.date_range[1]:
        start = conversation.date_range[0].strftime("%B %d, %Y")
        end = conversation.date_range[1].strftime("%B %d, %Y")
        if start == end:
            lines.append(f"- **Date**: {start}")
        else:
            lines.append(f"- **Date Range**: {start} to {end}")

    # Participants - cleaned up with better deduplication
    if conversation.participants:
        lines.append("- **Participants**:")
        participant_map = {}  # normalized_key -> display_value

        for p in conversation.participants:
            cleaned = clean_participant(p)
            if not cleaned:
                continue

            # Normalize for deduplication
            # Remove quotes and normalize whitespace
            norm_key = cleaned.lower().strip()
            norm_key = norm_key.replace('"', '').replace("'", "")
            norm_key = re.sub(r'\s+', ' ', norm_key)

            # Extract email if present for better matching
            email_match = re.search(r'<([^>]+)>', cleaned)
            if email_match:
                email = normalize_email(email_match.group(1))
                norm_key = email  # Use email as key if available
            else:
                # Normalize name variations (OCR typos like Tamita vs Tarnita)
                # Use first 5 chars + last 3 chars as fuzzy key
                name_only = norm_key.split('<')[0].strip()
                if len(name_only) > 8:
                    norm_key = name_only[:5] + name_only[-3:]

            # Keep the version with more info (longer or with email)
            if norm_key not in participant_map:
                participant_map[norm_key] = cleaned
            elif len(cleaned) > len(participant_map[norm_key]):
                participant_map[norm_key] = cleaned

        # Format and output unique participants
        for p in sorted(set(participant_map.values())):
            formatted = format_participant(p, name_registry)
            # Remove surrounding quotes if present
            formatted = formatted.strip('"').strip("'")
            lines.append(f"  - {formatted}")

    # Confidence level
    lines.append(f"- **Link Confidence**: {conversation.confidence}")

    lines.append("")
    lines.append("## Conversation Thread")
    lines.append("")

    # Messages
    for i, msg in enumerate(conversation.messages, 1):
        lines.append(f"### Message {i}")

        sender = format_participant(msg.sender, name_registry) if msg.sender else "[Unknown Sender]"
        lines.append(f"- **From**: {sender}")

        if msg.recipient:
            recipient = format_participant(msg.recipient, name_registry)
            lines.append(f"- **To**: {recipient}")

        if msg.date_str:
            lines.append(f"- **Date**: {msg.date_str}")

        lines.append(f"- **Source**: {msg.source_file}")
        lines.append("")

        # Body
        if msg.body:
            body = clean_message_body(msg.body)
            if body:
                lines.append(body)

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def clean_message_body(body: str) -> str:
    """Clean up message body, removing duplicate headers and junk"""
    if not body:
        return ""

    body = clean_text(body)
    # Remove header info that might be duplicated in body
    body = re.sub(r'^To:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^From:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Fran:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Sent:?.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Subject:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^Date:.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    # Remove image metadata lines
    body = re.sub(r'^[Ii]?lane-Images:.*$', '', body, flags=re.MULTILINE)
    body = re.sub(r'^\d{4,}_\d+.*jpg.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    # Remove lines that look like image filename metadata (numbers with underscores)
    body = re.sub(r'^\d+\s+\d+;\s+\d+\s+\d+:\d+_\w+\.?jpg.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^\d{4,}\s+\d+;\s+\d+\s+\d+:\d+_njpg.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    # Remove lines that are just numbers (likely OCR artifacts)
    body = re.sub(r'^\s*\d{5,}\s*$', '', body, flags=re.MULTILINE)
    # Remove EFTA references
    body = re.sub(r'EFTA_R\d+_\d+\s*', '', body)
    body = re.sub(r'EFTA\d{8,}\s*', '', body)
    # Clean up multiple blank lines
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


def generate_standalone_markdown(doc: Document, doc_id: int, name_registry: NameRegistry) -> str:
    """Generate markdown for a standalone (unlinked) document"""
    lines = []

    lines.append(f"# Standalone Document {doc_id:03d}")
    lines.append("")
    lines.append("## Metadata")
    lines.append(f"- **Original PDF**: {doc.filename}")
    lines.append(f"- **Document Type**: {doc.doc_type}")

    if doc.subject:
        lines.append(f"- **Subject**: {doc.subject}")

    if doc.email_addresses:
        lines.append("- **Email Addresses**:")
        for email in sorted(doc.email_addresses):
            lines.append(f"  - {email}")

    if doc.names:
        lines.append("- **Names Mentioned**:")
        for name in sorted(doc.names):
            lines.append(f"  - {name}")

    lines.append("")
    lines.append("## Content")
    lines.append("")

    if doc.doc_type == 'email' and doc.emails:
        for i, msg in enumerate(doc.emails, 1):
            lines.append(f"### Message {i}")

            sender = format_participant(msg.sender, name_registry) if msg.sender else "[Unknown]"
            # Clean up sender - remove "To:" prefix if present (parsing error)
            sender = re.sub(r'^To:\s*', '', sender, flags=re.IGNORECASE)
            lines.append(f"- **From**: {sender}")

            if msg.recipient:
                recipient = format_participant(msg.recipient, name_registry)
                lines.append(f"- **To**: {recipient}")

            if msg.date_str:
                lines.append(f"- **Date**: {msg.date_str}")

            lines.append("")

            if msg.body:
                lines.append(clean_message_body(msg.body))

            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        # Just output cleaned text
        lines.append(clean_text(doc.text))

    return "\n".join(lines)


def generate_index(conversations: List[Conversation], standalone_count: int) -> str:
    """Generate index.md summarizing all outputs"""
    lines = []

    lines.append("# PDF Email Unification Index")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Conversations**: {len(conversations)}")
    lines.append(f"- **Standalone Documents**: {standalone_count}")
    lines.append(f"- **Total Output Files**: {len(conversations) + standalone_count}")
    lines.append("")

    lines.append("## Conversations")
    lines.append("")
    lines.append("| ID | Subject | Files | Date Range | Participants | Confidence |")
    lines.append("|---|---|---|---|---|---|")

    for conv in conversations:
        subj = conv.subject[:50] + "..." if len(conv.subject) > 50 else conv.subject
        files = len(conv.documents)

        if conv.date_range[0]:
            date_range = conv.date_range[0].strftime("%Y-%m-%d")
            if conv.date_range[1] and conv.date_range[1] != conv.date_range[0]:
                date_range += f" to {conv.date_range[1].strftime('%Y-%m-%d')}"
        else:
            date_range = "Unknown"

        participants = len(conv.participants)

        lines.append(f"| [{conv.id:03d}](conversation_{conv.id:03d}.md) | {subj} | {files} | {date_range} | {participants} | {conv.confidence} |")

    lines.append("")
    lines.append("## Standalone Documents")
    lines.append("")
    lines.append("Documents that could not be linked to any conversation thread:")
    lines.append("")

    for i in range(1, standalone_count + 1):
        lines.append(f"- [standalone_{i:03d}.md](standalone_{i:03d}.md)")

    return "\n".join(lines)


def main():
    """Main processing function"""
    print("=" * 60)
    print("PDF Email Unification Script")
    print("=" * 60)
    print()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get all PDF files
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")
    print()

    # Phase 1: Parse all PDFs
    print("Phase 1: Extracting and parsing PDFs...")
    documents = []
    name_registry = NameRegistry()

    for i, pdf_path in enumerate(pdf_files):
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(pdf_files)} files...")

        doc = parse_pdf(str(pdf_path))
        if doc:
            documents.append(doc)

            # Register names for cross-referencing
            for name in doc.names:
                for email in doc.email_addresses:
                    name_registry.register_name(name, email, doc.filename)

    print(f"  Successfully parsed {len(documents)} documents")
    print()

    # Categorize documents
    type_counts = defaultdict(int)
    for doc in documents:
        type_counts[doc.doc_type] += 1

    print("Document types found:")
    for doc_type, count in sorted(type_counts.items()):
        print(f"  - {doc_type}: {count}")
    print()

    # Phase 2: Cluster documents
    print("Phase 2: Clustering related documents...")
    clusters = cluster_documents(documents, threshold=30.0)

    multi_doc_clusters = [c for c in clusters if len(c) > 1]
    single_doc_clusters = [c for c in clusters if len(c) == 1]

    print(f"  Found {len(multi_doc_clusters)} conversation clusters")
    print(f"  Found {len(single_doc_clusters)} standalone documents")
    print()

    # Phase 3: Build conversations
    print("Phase 3: Building conversation threads...")
    conversations = []

    for i, cluster in enumerate(multi_doc_clusters, 1):
        conv = Conversation(id=i, documents=cluster)

        # Collect all messages
        all_messages = []
        for doc in cluster:
            all_messages.extend(doc.emails)
            conv.participants.update(doc.participants)

        # Deduplicate and sort
        unique_messages = deduplicate_messages(all_messages)
        conv.messages = sort_messages_chronologically(unique_messages)

        # Determine subject (most common non-empty subject)
        subjects = [doc.subject for doc in cluster if doc.subject]
        if subjects:
            # Strip "Re:" prefixes and find most common
            cleaned_subjects = [re.sub(r'^(Re:\s*)+', '', s, flags=re.IGNORECASE).strip() for s in subjects]
            conv.subject = max(set(cleaned_subjects), key=cleaned_subjects.count) if cleaned_subjects else subjects[0]

        # Determine date range
        all_dates = []
        for doc in cluster:
            all_dates.extend(doc.dates)
        for msg in conv.messages:
            if msg.date:
                all_dates.append(msg.date)

        if all_dates:
            # Make all dates naive for comparison
            naive_dates = []
            for d in all_dates:
                if d:
                    if d.tzinfo:
                        d = d.replace(tzinfo=None)
                    naive_dates.append(d)
            if naive_dates:
                conv.date_range = (min(naive_dates), max(naive_dates))

        # Determine confidence
        if len(cluster) >= 2:
            # Check link strength
            scores = []
            for j in range(len(cluster)):
                for k in range(j + 1, len(cluster)):
                    score, conf, _ = calculate_link_score(cluster[j], cluster[k])
                    scores.append(score)
            avg_score = sum(scores) / len(scores) if scores else 0
            conv.confidence = "high" if avg_score >= 50 else "probable"

        conversations.append(conv)

    # Sort conversations by date
    conversations.sort(key=lambda c: c.date_range[0] if c.date_range[0] else datetime.max)

    # Renumber after sorting
    for i, conv in enumerate(conversations, 1):
        conv.id = i

    print(f"  Built {len(conversations)} conversations with {sum(len(c.messages) for c in conversations)} total messages")
    print()

    # Phase 4: Generate output
    print("Phase 4: Generating markdown reports...")

    # Generate conversation files
    for conv in conversations:
        content = generate_markdown(conv, name_registry)
        output_path = OUTPUT_DIR / f"conversation_{conv.id:03d}.md"
        output_path.write_text(content)

    print(f"  Generated {len(conversations)} conversation files")

    # Generate standalone files
    standalone_count = 0
    for cluster in single_doc_clusters:
        doc = cluster[0]
        standalone_count += 1
        content = generate_standalone_markdown(doc, standalone_count, name_registry)
        output_path = OUTPUT_DIR / f"standalone_{standalone_count:03d}.md"
        output_path.write_text(content)

    print(f"  Generated {standalone_count} standalone files")

    # Generate index
    index_content = generate_index(conversations, standalone_count)
    (OUTPUT_DIR / "index.md").write_text(index_content)
    print("  Generated index.md")

    print()
    print("=" * 60)
    print("Processing complete!")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    # Verification: Check the test pairs
    print()
    print("Verification: Checking test pairs...")

    test_pairs = [
        ("EFTA02426598.pdf", "EFTA02426626.pdf"),
        ("EFTA01930157.pdf", "EFTA01930421.pdf"),
    ]

    for file1, file2 in test_pairs:
        # Find which conversation contains these files
        found = False
        for conv in conversations:
            filenames = [doc.filename for doc in conv.documents]
            if file1 in filenames and file2 in filenames:
                print(f"  OK: {file1} and {file2} are in conversation_{conv.id:03d}.md")
                found = True
                break

        if not found:
            # Check if they're in different conversations
            conv1 = conv2 = None
            for conv in conversations:
                filenames = [doc.filename for doc in conv.documents]
                if file1 in filenames:
                    conv1 = conv.id
                if file2 in filenames:
                    conv2 = conv.id

            if conv1 and conv2:
                print(f"  WARNING: {file1} (conv {conv1}) and {file2} (conv {conv2}) are in different conversations")
            else:
                print(f"  WARNING: {file1} and/or {file2} not found in any conversation")


if __name__ == "__main__":
    main()
