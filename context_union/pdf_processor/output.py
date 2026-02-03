"""
Markdown output generation.
"""

import re
from datetime import datetime
from typing import List

from .models import Conversation, Document, NameRegistry, EmailMessage
from .text_utils import clean_text, clean_message_body, normalize_email


def format_participant(participant: str, name_registry: NameRegistry) -> str:
    """Format a participant, resolving censored names if possible."""
    if not participant:
        return "[Unknown]"

    participant = participant.strip()

    email_match = re.search(r'<([^>]+)>', participant)
    email = email_match.group(1) if email_match else ""

    name_part = re.sub(r'<[^>]+>', '', participant).strip()

    if not name_part and email:
        return name_registry.resolve_censored(email)

    return participant


def clean_participant(p: str) -> str:
    """Clean up participant string - extract just name and email."""
    if not p:
        return ""

    p = p.strip()

    if 'wrote:' in p.lower() or len(p) > 80:
        return ""

    if p.startswith('On '):
        return ""

    if p.startswith('I ') or p.startswith('i ') or 'Sent from' in p:
        return ""

    if p.startswith('ein(') or p.startswith('eini') or p.startswith('• '):
        return ""

    email_match = re.search(r'[<\[\(]([^>\]\)]+@[^>\]\)]+)[>\]\)]', p)
    if email_match:
        email = normalize_email(email_match.group(1))
        name_part = re.sub(r'[<\[\(].*', '', p).strip()
        name_part = re.sub(r'^On.*?,\s*', '', name_part)
        if name_part and len(name_part) < 40 and not name_part.startswith('On '):
            return f"{name_part} <{email}>"
        else:
            return email

    email_only = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', p)
    if email_only:
        return normalize_email(email_only.group(0))

    if len(p) < 40 and not any(c in p for c in [':', '@', '>', '<', '\n', '(']):
        if not re.match(r'^[\d\.\s]+$', p):
            return p

    return ""


def generate_markdown(conversation: Conversation, name_registry: NameRegistry) -> str:
    """Generate markdown output for a conversation."""
    lines = []

    lines.append(f"# Conversation {conversation.id:03d}")
    lines.append("")
    lines.append("## Metadata")

    source_files = sorted(set(doc.filename for doc in conversation.documents))
    lines.append(f"- **Original PDFs**: {', '.join(source_files)}")

    if conversation.subject:
        lines.append(f"- **Subject**: {conversation.subject}")

    if conversation.date_range[0] and conversation.date_range[1]:
        start = conversation.date_range[0].strftime("%B %d, %Y")
        end = conversation.date_range[1].strftime("%B %d, %Y")
        if start == end:
            lines.append(f"- **Date**: {start}")
        else:
            lines.append(f"- **Date Range**: {start} to {end}")

    if conversation.participants:
        lines.append("- **Participants**:")
        participant_map = {}

        for p in conversation.participants:
            cleaned = clean_participant(p)
            if not cleaned:
                continue

            norm_key = cleaned.lower().strip()
            norm_key = norm_key.replace('"', '').replace("'", "")
            norm_key = re.sub(r'\s+', ' ', norm_key)

            email_match = re.search(r'<([^>]+)>', cleaned)
            if email_match:
                email = normalize_email(email_match.group(1))
                norm_key = email
            else:
                name_only = norm_key.split('<')[0].strip()
                if len(name_only) > 8:
                    norm_key = name_only[:5] + name_only[-3:]

            if norm_key not in participant_map:
                participant_map[norm_key] = cleaned
            elif len(cleaned) > len(participant_map[norm_key]):
                participant_map[norm_key] = cleaned

        for p in sorted(set(participant_map.values())):
            formatted = format_participant(p, name_registry)
            formatted = formatted.strip('"').strip("'")
            lines.append(f"  - {formatted}")

    lines.append(f"- **Link Confidence**: {conversation.confidence}")

    lines.append("")
    lines.append("## Conversation Thread")
    lines.append("")

    for i, msg in enumerate(conversation.messages, 1):
        lines.append(f"### Message {i}")

        sender = format_participant(msg.sender, name_registry) if msg.sender else "[Unknown Sender]"
        lines.append(f"- **From**: {sender}")

        if msg.recipient:
            recipient = format_participant(msg.recipient, name_registry)
            lines.append(f"- **To**: {recipient}")

        if msg.date:
            lines.append(f"- **Date**: {msg.date.strftime('%B %d, %Y at %I:%M %p')}")
        elif msg.date_str:
            lines.append(f"- **Date**: {msg.date_str}")

        lines.append(f"- **Source**: {msg.source_file}")
        lines.append("")

        if msg.body:
            body = clean_message_body(msg.body)
            if body:
                lines.append(body)

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_standalone_markdown(doc: Document, doc_id: int, name_registry: NameRegistry) -> str:
    """Generate markdown for a standalone (unlinked) document."""
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
            sender = re.sub(r'^To:\s*', '', sender, flags=re.IGNORECASE)
            lines.append(f"- **From**: {sender}")

            if msg.recipient:
                recipient = format_participant(msg.recipient, name_registry)
                lines.append(f"- **To**: {recipient}")

            if msg.date:
                lines.append(f"- **Date**: {msg.date.strftime('%B %d, %Y at %I:%M %p')}")
            elif msg.date_str:
                lines.append(f"- **Date**: {msg.date_str}")

            lines.append("")

            if msg.body:
                lines.append(clean_message_body(msg.body))

            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append(clean_text(doc.text))

    return "\n".join(lines)


def generate_index(conversations: List[Conversation], standalone_count: int) -> str:
    """Generate index.md summarizing all outputs."""
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
