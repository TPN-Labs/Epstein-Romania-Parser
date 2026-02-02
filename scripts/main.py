#!/usr/bin/env python3
"""Main entry point for PDF keyword parsing."""

import argparse
import csv
import sys
import time
from multiprocessing import cpu_count
from pathlib import Path

from keyword_search import load_keywords
from processor import process_folder
from progress import format_time
from result_writer import StreamingResultWriter


DEFAULT_WORKERS = max(1, cpu_count() - 2)


def find_ds_folders(base_path: Path) -> list[Path]:
    """Find all DS-* folders in the base directory."""
    folders = sorted(base_path.glob("DS-*"))
    return [f for f in folders if f.is_dir()]


def print_summary(
    total_time: float,
    ds_folders: list[Path],
    total_pdfs: int,
    total_matches: int,
    files_copied: int,
    output_path: Path,
    files_dir: Path,
    errors: list[str]
) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total time:        {format_time(total_time)}")
    print(f"Folders processed: {len(ds_folders)}")
    print(f"PDFs processed:    {total_pdfs}")
    print(f"Processing speed:  {total_pdfs / total_time:.1f} files/sec")
    print(f"Matches found:     {total_matches}")
    print(f"PDFs copied:       {files_copied}")
    print(f"Results saved to:  {output_path}")
    print(f"Files copied to:   {files_dir}")

    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")


def print_breakdown(output_path: Path) -> None:
    """Print match breakdown by keyword and folder."""
    keyword_counts: dict[str, int] = {}
    folder_counts: dict[str, int] = {}

    with open(output_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            keyword_counts[row["keyword"]] = keyword_counts.get(row["keyword"], 0) + 1
            folder_counts[row["folder"]] = folder_counts.get(row["folder"], 0) + 1

    print("\nMatches by keyword:")
    for keyword, count in sorted(keyword_counts.items()):
        print(f"  {keyword}: {count}")

    print("\nMatches by folder:")
    for folder, count in sorted(folder_counts.items()):
        print(f"  {folder}: {count}")


def main(num_workers: int = DEFAULT_WORKERS) -> None:
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    keywords_path = script_dir / "config" / "keywords.txt"
    output_path = script_dir / "output" / "results.csv"
    files_dir = script_dir / "output" / "files"

    # Load keywords
    if not keywords_path.exists():
        print(f"Error: Keywords file not found: {keywords_path}", file=sys.stderr)
        sys.exit(1)

    keywords = load_keywords(keywords_path)
    print(f"Loaded {len(keywords)} keywords: {', '.join(keywords)}")

    # Find folders
    ds_folders = find_ds_folders(project_root)
    if not ds_folders:
        print("No DS-* folders found in project directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(ds_folders)} folder(s): {', '.join(f.name for f in ds_folders)}")
    print(f"Using {num_workers} parallel workers (CPUs available: {cpu_count()})")
    print(f"Results: {output_path} | Files: {files_dir}")

    # Process
    total_matches = 0
    total_pdfs = 0
    all_errors: list[str] = []
    start_time = time.time()

    with StreamingResultWriter(output_path, files_dir, project_root) as writer:
        for folder in ds_folders:
            matches, pdfs, errors = process_folder(folder, keywords, num_workers, writer)
            total_matches += matches
            total_pdfs += pdfs
            all_errors.extend(errors)

        files_copied = len(writer.copied_files)

    total_time = time.time() - start_time

    print_summary(
        total_time, ds_folders, total_pdfs, total_matches,
        files_copied, output_path, files_dir, all_errors
    )

    if total_matches > 0:
        print_breakdown(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF keyword parser with parallel processing")
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel workers (default: {DEFAULT_WORKERS})"
    )
    main(num_workers=parser.parse_args().workers)
