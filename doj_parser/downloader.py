"""PDF download handler."""

import time
from pathlib import Path

import requests

from config import DELAYS, MAX_RETRIES, PDFS_DIR


class PDFDownloader:
    """Downloads PDFs with rate limiting and retry logic."""

    def __init__(self, output_dir: Path = PDFS_DIR):
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0

    def download(self, url: str, filename: str) -> bool:
        """Download a PDF file with retry logic.

        Returns True if downloaded, False if skipped or failed.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.output_dir / filename

        if filepath.exists():
            self.skipped += 1
            return False

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                filepath.write_bytes(response.content)
                self.downloaded += 1
                time.sleep(DELAYS["pdf_download"])
                return True

            except requests.RequestException as e:
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
