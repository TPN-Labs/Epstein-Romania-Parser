#!/usr/bin/env python3
"""Main entry point for PDF keyword parsing with multithreading support."""

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from typing import NamedTuple

from pdf_parser import extract_pages_as_images
from ocr_processor import process_pdf_pages
from keyword_search import load_keywords, search_text, SearchResult


# Default number of workers - use CPU count, leaving 1-2 cores free for system
DEFAULT_WORKERS = max(1, cpu_count() - 2)


class PdfTask(NamedTuple):
    """Represents a PDF processing task."""
    pdf_path: Path
    folder_name: str
    keywords: list[str]


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
        # Silently collect errors - will be reported in summary
        pass

    return results


def process_pdf_task(task: PdfTask) -> tuple[list[SearchResult], str | None]:
    """
    Worker function for processing a PDF in a separate process.

    Args:
        task: PdfTask containing path, folder name, and keywords

    Returns:
        Tuple of (results list, error message or None)
    """
    try:
        results = process_pdf(task.pdf_path, task.folder_name, task.keywords)
        return results, None
    except Exception as e:
        return [], f"{task.pdf_path.name}: {e}"


def save_results(results: list[SearchResult], output_path: Path) -> None:
    """Save results to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["folder", "filename", "page", "keyword", "context"])
        for r in results:
            writer.writerow([r.folder, r.filename, r.page, r.keyword, r.context])


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def print_progress(
    current: int,
    total: int,
    filename: str,
    elapsed: float,
    matches: int,
    width: int = 30,
    workers: int = 1
) -> None:
    """Print a detailed progress bar with stats."""
    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)

    # Calculate speed and ETA
    speed = current / elapsed if elapsed > 0 else 0
    remaining = total - current
    eta = remaining / speed if speed > 0 else 0

    # Truncate filename if too long
    display_name = filename[:20] + "..." if len(filename) > 20 else filename

    # Build progress line
    progress_line = (
        f"\r  [{bar}] {current}/{total} ({percent*100:.0f}%) | "
        f"{speed:.1f} files/sec | "
        f"ETA: {format_time(eta)} | "
        f"Matches: {matches} | "
        f"Workers: {workers} | "
        f"{display_name:<23}"
    )

    print(progress_line, end="", flush=True)


def process_folder_parallel(
    folder: Path,
    keywords: list[str],
    num_workers: int
) -> tuple[list[SearchResult], int, list[str]]:
    """
    Process all PDFs in a folder using parallel workers.

    Args:
        folder: Path to folder containing PDFs
        keywords: Keywords to search for
        num_workers: Number of parallel workers

    Returns:
        Tuple of (results, pdf_count, errors)
    """
    pdfs = find_pdfs(folder)
    if not pdfs:
        return [], 0, []

    all_results: list[SearchResult] = []
    errors: list[str] = []
    completed = 0
    folder_start = time.time()

    # Create tasks for all PDFs
    tasks = [PdfTask(pdf, folder.name, keywords) for pdf in pdfs]

    print(f"\n{folder.name}: Processing {len(pdfs)} PDF files with {num_workers} workers...")

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(process_pdf_task, task): task
            for task in tasks
        }

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            completed += 1

            try:
                results, error = future.result()
                all_results.extend(results)
                if error:
                    errors.append(error)
            except Exception as e:
                errors.append(f"{task.pdf_path.name}: {e}")

            # Update progress
            elapsed = time.time() - folder_start
            print_progress(
                completed, len(pdfs), task.pdf_path.name,
                elapsed, len(all_results), workers=num_workers
            )

    print()  # New line after progress bar
    return all_results, len(pdfs), errors


def main(num_workers: int | None = None) -> None:
    """
    Main entry point.

    Args:
        num_workers: Number of parallel workers (default: CPU count - 2)
    """
    if num_workers is None:
        num_workers = DEFAULT_WORKERS

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
    print(f"Using {num_workers} parallel workers (CPUs available: {cpu_count()})")

    # Process all PDFs in parallel
    all_results: list[SearchResult] = []
    total_pdfs = 0
    all_errors: list[str] = []
    global_start = time.time()

    for folder in ds_folders:
        results, pdf_count, errors = process_folder_parallel(folder, keywords, num_workers)
        all_results.extend(results)
        total_pdfs += pdf_count
        all_errors.extend(errors)

    total_time = time.time() - global_start

    # Save results
    save_results(all_results, output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total time:        {format_time(total_time)}")
    print(f"Folders processed: {len(ds_folders)}")
    print(f"PDFs processed:    {total_pdfs}")
    print(f"Processing speed:  {total_pdfs / total_time:.1f} files/sec")
    print(f"Matches found:     {len(all_results)}")
    print(f"Results saved to:  {output_path}")

    # Report errors if any
    if all_errors:
        print(f"\nErrors encountered: {len(all_errors)}")
        if len(all_errors) <= 10:
            for err in all_errors:
                print(f"  - {err}")
        else:
            for err in all_errors[:5]:
                print(f"  - {err}")
            print(f"  ... and {len(all_errors) - 5} more errors")

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
    import argparse

    parser = argparse.ArgumentParser(
        description="PDF keyword parser with parallel processing"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel workers (default: {DEFAULT_WORKERS})"
    )
    args = parser.parse_args()

    main(num_workers=args.workers)
