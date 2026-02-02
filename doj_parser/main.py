#!/usr/bin/env python3
"""Main entry point for DOJ Epstein Library crawler."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DEFAULT_KEYWORDS, CSV_FILE, OUTPUT_DIR
from crawler import DOJCrawler
from downloader import PDFDownloader
from result_writer import ResultWriter


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Crawl DOJ Epstein Library for specific keywords"
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help=f"Keywords to search for (default: {DEFAULT_KEYWORDS})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome in headless mode",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip PDF downloads (only generate CSV)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CSV_FILE,
        help=f"Output CSV file path (default: {CSV_FILE})",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DOJ Epstein Library Crawler")
    print("=" * 60)
    print(f"Keywords: {args.keywords}")
    print(f"Headless: {args.headless}")
    print(f"Skip downloads: {args.skip_download}")
    print(f"Output: {args.output}")
    print("=" * 60)

    total_results = 0
    downloader = None

    with DOJCrawler(headless=args.headless) as crawler:
        with ResultWriter(args.output) as writer:
            # Navigate and handle initial prompts
            crawler.navigate_to_search()
            crawler.handle_not_a_robot()
            crawler.handle_age_verification()

            # Initialize downloader with crawler for browser-based downloads
            if not args.skip_download:
                downloader = PDFDownloader(crawler=crawler)

            # Process each keyword
            for keyword in args.keywords:
                print(f"\n{'='*40}")
                print(f"Searching for: {keyword}")
                print("=" * 40)

                keyword_count = 0
                for result in crawler.crawl_keyword(keyword):
                    writer.write(result)
                    keyword_count += 1

                    # Download PDF immediately after finding result
                    if downloader:
                        downloader.download(result.pdf_url, result.filename)

                print(f"Found {keyword_count} results for '{keyword}'")
                total_results += keyword_count

    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"Total results: {total_results}")
    print(f"CSV saved to: {args.output}")
    if downloader:
        print(f"Downloads: {downloader.summary()}")
        print(f"PDFs saved to: {OUTPUT_DIR / 'pdfs'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
