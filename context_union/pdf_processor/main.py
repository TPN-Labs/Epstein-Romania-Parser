"""
Main processing orchestration.
"""

import re
from datetime import datetime
from collections import defaultdict

from .config import PDF_DIR, OUTPUT_DIR, DEFAULT_LINK_THRESHOLD
from .models import Conversation, NameRegistry
from .parser import parse_pdf
from .clustering import (
    cluster_documents,
    calculate_link_score,
    deduplicate_messages,
    sort_messages_chronologically,
)
from .output import generate_markdown, generate_standalone_markdown, generate_index


def main():
    """Main processing function."""
    print("=" * 60)
    print("PDF Email Unification Script")
    print("=" * 60)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    clusters = cluster_documents(documents, threshold=DEFAULT_LINK_THRESHOLD)

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

        all_messages = []
        for doc in cluster:
            all_messages.extend(doc.emails)
            conv.participants.update(doc.participants)

        unique_messages = deduplicate_messages(all_messages)
        conv.messages = sort_messages_chronologically(unique_messages)

        subjects = [doc.subject for doc in cluster if doc.subject]
        if subjects:
            cleaned_subjects = [re.sub(r'^(Re:\s*)+', '', s, flags=re.IGNORECASE).strip() for s in subjects]
            conv.subject = max(set(cleaned_subjects), key=cleaned_subjects.count) if cleaned_subjects else subjects[0]

        all_dates = []
        for doc in cluster:
            all_dates.extend(doc.dates)
        for msg in conv.messages:
            if msg.date:
                all_dates.append(msg.date)

        if all_dates:
            naive_dates = []
            for d in all_dates:
                if d:
                    if d.tzinfo:
                        d = d.replace(tzinfo=None)
                    naive_dates.append(d)
            if naive_dates:
                conv.date_range = (min(naive_dates), max(naive_dates))

        if len(cluster) >= 2:
            scores = []
            for j in range(len(cluster)):
                for k in range(j + 1, len(cluster)):
                    score, conf, _ = calculate_link_score(cluster[j], cluster[k])
                    scores.append(score)
            avg_score = sum(scores) / len(scores) if scores else 0
            conv.confidence = "high" if avg_score >= 50 else "probable"

        conversations.append(conv)

    conversations.sort(key=lambda c: c.date_range[0] if c.date_range[0] else datetime.max)

    for i, conv in enumerate(conversations, 1):
        conv.id = i

    print(f"  Built {len(conversations)} conversations with {sum(len(c.messages) for c in conversations)} total messages")
    print()

    # Phase 4: Generate output
    print("Phase 4: Generating markdown reports...")

    for conv in conversations:
        content = generate_markdown(conv, name_registry)
        output_path = OUTPUT_DIR / f"conversation_{conv.id:03d}.md"
        output_path.write_text(content)

    print(f"  Generated {len(conversations)} conversation files")

    standalone_count = 0
    for cluster in single_doc_clusters:
        doc = cluster[0]
        standalone_count += 1
        content = generate_standalone_markdown(doc, standalone_count, name_registry)
        output_path = OUTPUT_DIR / f"standalone_{standalone_count:03d}.md"
        output_path.write_text(content)

    print(f"  Generated {standalone_count} standalone files")

    index_content = generate_index(conversations, standalone_count)
    (OUTPUT_DIR / "index.md").write_text(index_content)
    print("  Generated index.md")

    print()
    print("=" * 60)
    print("Processing complete!")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    # Verification
    print()
    print("Verification: Checking test pairs...")

    test_pairs = [
        ("EFTA02426598.pdf", "EFTA02426626.pdf"),
        ("EFTA01930157.pdf", "EFTA01930421.pdf"),
    ]

    for file1, file2 in test_pairs:
        found = False
        for conv in conversations:
            filenames = [doc.filename for doc in conv.documents]
            if file1 in filenames and file2 in filenames:
                print(f"  OK: {file1} and {file2} are in conversation_{conv.id:03d}.md")
                found = True
                break

        if not found:
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
