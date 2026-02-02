#!/usr/bin/env python3
"""Main entry point for PDF keyword parsing."""

import csv
import sys
from pathlib import Path

from pdf_parser import extract_pages_as_images
from ocr_processor import process_pdf_pages
from keyword_search import load_keywords, search_text, SearchResult


def find_ds_folders(base_path: Path) -> list[Path]:
    """Find all DS-* folders in the base directory."""
    folders = sorted(base_path.glob("DS-*"))
    return [f for f in folders if f.is_dir()]


def find_pdfs(folder: Path) -> list[Path]:
    """Find all PDF files in a folder."""
    return sorted(folder.glob("*.pdf"))


def process_pdf(
    pdf_path: Path,
    folder_name: str,
    keywords: list[str]
) -> list[SearchResult]:
    """
    Process a single PDF: extract images, OCR, and search for keywords.

    Args:
        pdf_path: Path to the PDF file
        folder_name: Name of the containing folder
        keywords: Keywords to search for

    Returns:
        List of SearchResult objects
    """
    results = []

    try:
        # Extract pages as images
        images = extract_pages_as_images(str(pdf_path))

        # Run OCR on all pages
        page_texts = process_pdf_pages(images)

        # Search each page for keywords
        for page_num, text in enumerate(page_texts, start=1):
            matches = search_text(text, keywords)
            for keyword, context in matches:
                results.append(SearchResult(
                    folder=folder_name,
                    filename=pdf_path.name,
                    page=page_num,
                    keyword=keyword,
                    context=context
                ))

    except Exception as e:
        print(f"  Error processing {pdf_path.name}: {e}", file=sys.stderr)

    return results


def save_results(results: list[SearchResult], output_path: Path) -> None:
    """Save results to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["folder", "filename", "page", "keyword", "context"])
        for r in results:
            writer.writerow([r.folder, r.filename, r.page, r.keyword, r.context])


def print_progress(current: int, total: int, filename: str, width: int = 40) -> None:
    """Print a progress bar."""
    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    # Truncate filename if too long
    display_name = filename[:30] + "..." if len(filename) > 30 else filename
    print(f"\r  [{bar}] {current}/{total} - {display_name:<35}", end="", flush=True)


def main() -> None:
    """Main entry point."""
    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent  # Where DS-* folders are

    # Config and output are inside scripts folder
    keywords_path = script_dir / "config" / "keywords.txt"
    output_path = script_dir / "output" / "results.csv"

    # Load keywords
    if not keywords_path.exists():
        print(f"Error: Keywords file not found: {keywords_path}", file=sys.stderr)
        sys.exit(1)

    keywords = load_keywords(keywords_path)
    print(f"Loaded {len(keywords)} keywords: {', '.join(keywords)}")

    # Find DS-* folders in project root
    ds_folders = find_ds_folders(project_root)
    if not ds_folders:
        print("No DS-* folders found in project directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(ds_folders)} folder(s): {', '.join(f.name for f in ds_folders)}")

    # Process all PDFs
    all_results: list[SearchResult] = []
    total_pdfs = 0
    total_pages = 0

    for folder in ds_folders:
        pdfs = find_pdfs(folder)
        if not pdfs:
            print(f"\n{folder.name}: No PDF files found")
            continue

        print(f"\n{folder.name}: Processing {len(pdfs)} PDF files...")

        for i, pdf_path in enumerate(pdfs, start=1):
            print_progress(i, len(pdfs), pdf_path.name)
            results = process_pdf(pdf_path, folder.name, keywords)
            all_results.extend(results)
            total_pdfs += 1

        print()  # New line after progress bar

    # Save results
    save_results(all_results, output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Folders processed: {len(ds_folders)}")
    print(f"PDFs processed:    {total_pdfs}")
    print(f"Matches found:     {len(all_results)}")
    print(f"Results saved to:  {output_path}")

    # Breakdown by keyword
    if all_results:
        print("\nMatches by keyword:")
        keyword_counts = {}
        for r in all_results:
            keyword_counts[r.keyword] = keyword_counts.get(r.keyword, 0) + 1
        for keyword, count in sorted(keyword_counts.items()):
            print(f"  {keyword}: {count}")

        print("\nMatches by folder:")
        folder_counts = {}
        for r in all_results:
            folder_counts[r.folder] = folder_counts.get(r.folder, 0) + 1
        for folder, count in sorted(folder_counts.items()):
            print(f"  {folder}: {count}")


if __name__ == "__main__":
    main()
