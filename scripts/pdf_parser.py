"""PDF to image extraction using PyMuPDF."""

import fitz
from PIL import Image
import io


def extract_pages_as_images(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    """
    Extract all pages from a PDF as PIL Images.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for rendering (higher = better OCR, slower)

    Returns:
        List of PIL Image objects, one per page
    """
    images = []
    zoom = dpi / 72  # Default PDF resolution is 72 DPI
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
