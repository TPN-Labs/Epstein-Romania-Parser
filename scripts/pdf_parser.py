"""PDF text extraction using PyMuPDF with OCR fallback."""

import fitz
from PIL import Image
import io


def extract_text_direct(pdf_path: str) -> list[str] | None:
    """
    Extract embedded text directly from PDF (fast path).

    Returns:
        List of text strings per page, or None if PDF needs OCR
    """
    texts = []
    total_chars = 0

    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text()
            texts.append(text)
            total_chars += len(text.strip())

    # If we got meaningful text, return it
    # Threshold: at least 50 chars per page on average indicates real text
    if total_chars > len(texts) * 50:
        return texts

    return None  # Needs OCR


def extract_pages_as_images(pdf_path: str, dpi: int = 150) -> list[Image.Image]:
    """
    Extract all pages from a PDF as PIL Images (for OCR fallback).

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for rendering (150 is good balance of speed/quality)

    Returns:
        List of PIL Image objects, one per page
    """
    images = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)

    return images


def get_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    with fitz.open(pdf_path) as doc:
        return len(doc)
