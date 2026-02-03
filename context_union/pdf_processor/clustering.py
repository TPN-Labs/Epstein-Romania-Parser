"""
Document clustering and link scoring.
"""

import re
from typing import List, Tuple
from collections import defaultdict
from datetime import datetime

from rapidfuzz import fuzz

from .models import Document, EmailMessage
from .config import COMMON_EMAILS_TO_IGNORE, MAX_CLUSTER_SIZE
from .text_utils import parse_date


def calculate_link_score(doc1: Document, doc2: Document) -> Tuple[float, str, str]:
    """Calculate how likely two documents are part of the same conversation thread."""
    score = 0.0
    reasons = []

    # Quoted text matching
    if doc1.text and doc2.text:
        def clean_for_matching(text):
            text = re.sub(r'The information contained in this communication[\s\S]*?all attachments\.?', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\*{5,}[\s\S]*?\*{5,}', '', text)
            text = re.sub(r'EFTA\w*\d+', '', text)
            text = re.sub(r'Sent from my \w+', '', text, flags=re.IGNORECASE)
            text = re.sub(r'^(To|From|Sent|Subject|Date):.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
            return text

        clean1 = clean_for_matching(doc1.text)
        clean2 = clean_for_matching(doc2.text)

        matched = False
        for i in range(0, len(clean1) - 100, 50):
            chunk = clean1[i:i+100]
            if len(chunk.strip()) < 80:
                continue
            alpha_count = sum(1 for c in chunk if c.isalpha())
            if alpha_count < 40:
                continue
            if chunk in clean2:
                score += 60
                reasons.append("quoted text match")
                matched = True
                break

        if not matched:
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

    # Same subject line
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

    # Close EFTA numbers
    efta1 = re.search(r'EFTA(\d+)', doc1.filename)
    efta2 = re.search(r'EFTA(\d+)', doc2.filename)
    efta_close = False
    if efta1 and efta2:
        diff = abs(int(efta1.group(1)) - int(efta2.group(1)))
        if diff < 50:
            efta_close = True
            score += 10
            reasons.append("very close EFTA numbers")

    # Same date
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
        score += 5

    # Overlapping email addresses
    email1_filtered = doc1.email_addresses - COMMON_EMAILS_TO_IGNORE
    email2_filtered = doc2.email_addresses - COMMON_EMAILS_TO_IGNORE
    common_emails = email1_filtered & email2_filtered

    if len(common_emails) >= 2:
        score += 20
        reasons.append(f"{len(common_emails)} shared emails")
    elif len(common_emails) == 1 and same_date:
        score += 10
        reasons.append("1 shared email + same date")

    confidence = "high" if score >= 70 else "probable" if score >= 40 else "low"
    return score, confidence, "; ".join(reasons) if reasons else "no link"


def cluster_documents(documents: List[Document], threshold: float = 40.0) -> List[List[Document]]:
    """Cluster related documents together into conversation threads."""
    n = len(documents)

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

    # Union-find with size limits
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

        size_px = get_cluster_size(px)
        size_py = get_cluster_size(py)

        if size_px + size_py > MAX_CLUSTER_SIZE and score < 70:
            return

        if rank[px] < rank[py]:
            parent[px] = py
        elif rank[px] > rank[py]:
            parent[py] = px
        else:
            parent[py] = px
            rank[px] += 1

    # Sort links by score (highest first)
    all_links = []
    for i in range(n):
        for j, score, conf, reason in links[i]:
            if i < j:
                all_links.append((score, i, j, conf, reason))

    all_links.sort(reverse=True)

    for score, i, j, conf, reason in all_links:
        union(i, j, score)

    # Group by cluster
    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(documents[i])

    return list(clusters.values())


def deduplicate_messages(messages: List[EmailMessage]) -> List[EmailMessage]:
    """Remove duplicate messages that appear in multiple quoted threads."""
    if not messages:
        return []

    unique = []
    seen_sigs = set()

    for msg in messages:
        if not msg.body:
            continue

        body_clean = msg.body.strip()
        body_clean = re.sub(r'^>.*$', '', body_clean, flags=re.MULTILINE)
        body_clean = re.sub(r'On\s+[\w,\s]+\d{4}.*?wrote:', '', body_clean, flags=re.IGNORECASE | re.DOTALL)
        body_clean = re.sub(r'^Subject\s*Re:?\s*', '', body_clean, flags=re.MULTILINE | re.IGNORECASE)
        body_clean = re.sub(r'\s+', ' ', body_clean).strip().lower()

        if len(body_clean) < 100:
            body_sig = body_clean
        else:
            body_sig = body_clean[:100]

        if not body_sig:
            continue

        if body_sig in seen_sigs:
            continue

        is_duplicate = False
        for existing_sig in list(seen_sigs):
            if len(body_sig) > 20 and len(existing_sig) > 20:
                if body_sig in existing_sig or existing_sig in body_sig:
                    is_duplicate = True
                    break

        if not is_duplicate:
            seen_sigs.add(body_sig)
            unique.append(msg)

    return unique


def sort_messages_chronologically(messages: List[EmailMessage]) -> List[EmailMessage]:
    """Sort messages by date, oldest first."""
    def get_sort_key(msg):
        dt = None
        if msg.date:
            dt = msg.date
        elif msg.date_str:
            dt = parse_date(msg.date_str)

        if dt:
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt

        return datetime.max

    return sorted(messages, key=get_sort_key)
