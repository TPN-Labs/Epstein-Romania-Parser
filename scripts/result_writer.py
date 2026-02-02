"""Streaming result writer for CSV output and file copying."""

import csv
import shutil
from pathlib import Path

from keyword_search import SearchResult


class StreamingResultWriter:
    """
    Writes results to CSV immediately and copies matched PDF files.

    Ensures data is persisted to disk even if the script is interrupted.
    Implements context manager protocol for safe resource cleanup.
    """

    HEADERS = ["folder", "filename", "page", "keyword", "context"]

    def __init__(self, output_path: Path, files_dir: Path, project_root: Path):
        self.output_path = output_path
        self.files_dir = files_dir
        self.project_root = project_root
        self.count = 0
        self.copied_files: set[str] = set()

        # Create output directories
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        # Open CSV file and write header
        self._file = open(output_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(self.HEADERS)
        self._file.flush()

    def __enter__(self) -> "StreamingResultWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _copy_pdf(self, folder: str, filename: str) -> None:
        """Copy a PDF to output directory if not already copied."""
        file_key = f"{folder}/{filename}"
        if file_key in self.copied_files:
            return

        src = self.project_root / folder / filename
        dst = self.files_dir / f"{folder}_{filename}"

        if src.exists():
            shutil.copy2(src, dst)
            self.copied_files.add(file_key)

    def write(self, results: list[SearchResult]) -> None:
        """Write results to CSV and copy matched PDFs."""
        for r in results:
            self._writer.writerow([r.folder, r.filename, r.page, r.keyword, r.context])
            self._copy_pdf(r.folder, r.filename)
        self._file.flush()
        self.count += len(results)

    def close(self) -> None:
        """Close the CSV file."""
        if not self._file.closed:
            self._file.close()
