"""
Data models for PDF processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Set, Tuple, Dict
from collections import defaultdict


@dataclass
class EmailMessage:
    """Represents a single email message extracted from a PDF."""
    sender: str = ""
    recipient: str = ""
    date: Optional[datetime] = None
    date_str: str = ""
    subject: str = ""
    body: str = ""
    source_file: str = ""
    raw_text: str = ""

    def __hash__(self):
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
    """Represents a parsed PDF document."""
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
    """A group of related documents forming a conversation."""
    id: int
    documents: List[Document] = field(default_factory=list)
    messages: List[EmailMessage] = field(default_factory=list)
    participants: Set[str] = field(default_factory=set)
    subject: str = ""
    date_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
    confidence: str = "high"  # high, probable


class NameRegistry:
    """Tracks names across documents for cross-referencing censored names."""

    def __init__(self):
        self.email_to_names: Dict[str, Set[str]] = defaultdict(set)
        self.name_occurrences: Dict[str, List[str]] = defaultdict(list)  # name -> [source files]
        self.censored_resolutions: Dict[str, Dict[str, str]] = {}  # email -> {source_file: resolved_name}

    def register_name(self, name: str, email: str, source_file: str):
        """Register a name associated with an email."""
        if name and email:
            self.email_to_names[email.lower()].add(name)
            self.name_occurrences[name].append(source_file)

    def resolve_censored(self, email: str, context: str = "") -> str:
        """Try to resolve a censored name by email address."""
        email_lower = email.lower() if email else ""
        if email_lower in self.email_to_names:
            names = self.email_to_names[email_lower]
            if names:
                name = list(names)[0]
                sources = self.name_occurrences.get(name, [])
                if sources:
                    return f"[REDACTED - identified as: {name} in {sources[0]}]"
        return "[REDACTED]"
