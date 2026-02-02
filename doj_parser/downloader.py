"""PDF download handler."""

import time
from pathlib import Path

from config import DELAYS, MAX_RETRIES, PDFS_DIR


class PDFDownloader:
    """Downloads PDFs using the browser's authenticated session."""

    def __init__(self, output_dir: Path = PDFS_DIR, crawler=None):
        self.output_dir = output_dir
        self.crawler = crawler
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0

    def set_crawler(self, crawler):
        """Set the crawler to use for browser-based downloads."""
        self.crawler = crawler

    def download(self, url: str, filename: str) -> bool:
        """Download a PDF file using the browser session.

        Returns True if downloaded, False if skipped or failed.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.output_dir / filename

        if filepath.exists():
            self.skipped += 1
            return False

        if not self.crawler:
            print(f"  Error: No crawler set for downloading {filename}")
            self.failed += 1
            return False

        for attempt in range(MAX_RETRIES):
            try:
                if self.crawler.download_pdf(url, filepath):
                    self.downloaded += 1
                    time.sleep(DELAYS["pdf_download"])
                    return True
                else:
                    if attempt < MAX_RETRIES - 1:
                        wait_time = DELAYS["retry_base"] * (2 ** attempt)
                        print(f"  Retry {attempt + 1}/{MAX_RETRIES} for {filename}")
                        time.sleep(wait_time)
                    else:
                        self.failed += 1
                        return False
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = DELAYS["retry_base"] * (2 ** attempt)
                    print(f"  Retry {attempt + 1}/{MAX_RETRIES} for {filename}: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"  Failed to download {filename}: {e}")
                    self.failed += 1
                    return False

        return False

    def summary(self) -> str:
        """Return download summary."""
        return f"Downloaded: {self.downloaded}, Skipped: {self.skipped}, Failed: {self.failed}"
