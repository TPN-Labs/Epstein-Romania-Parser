"""Data models for DOJ crawler."""

from dataclasses import dataclass


@dataclass
class CrawlResult:
    """Represents a single search result from the DOJ Epstein Library."""

    folder: str  # e.g., "DS-11"
    keyword: str  # search term used
    filename: str  # PDF filename
    page: int  # pagination page number
    context: str  # excerpt from result
    pdf_url: str  # full URL for download

    def to_csv_row(self) -> list:
        """Convert to CSV row format."""
        return [self.folder, self.keyword, self.filename, self.page, self.context]

    @staticmethod
    def csv_headers() -> list:
        """Return CSV column headers."""
        return ["folder", "keyword", "filename", "page", "context"]
