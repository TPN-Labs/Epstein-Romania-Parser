"""Streaming CSV writer for crawl results."""

import csv
from pathlib import Path
from typing import TextIO

from models import CrawlResult


class ResultWriter:
    """Streaming CSV writer with immediate flush to disk."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self._file: TextIO | None = None
        self._writer: csv.writer | None = None
        self._count = 0

    def __enter__(self) -> "ResultWriter":
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filepath, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(CrawlResult.csv_headers())
        self._file.flush()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def write(self, result: CrawlResult) -> None:
        """Write a single result to CSV and flush immediately."""
        if self._writer is None:
            raise RuntimeError("Writer not initialized. Use with context manager.")
        self._writer.writerow(result.to_csv_row())
        self._file.flush()
        self._count += 1

    @property
    def count(self) -> int:
        """Return number of results written."""
        return self._count
