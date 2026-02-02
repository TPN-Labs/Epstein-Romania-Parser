"""OCR processing using Tesseract."""

import pytesseract
from PIL import Image


def extract_text(image: Image.Image, lang: str = "eng") -> str:
    """
    Run Tesseract OCR on a single image.

    Args:
        image: PIL Image to process
        lang: Tesseract language code

    Returns:
        Extracted text from the image
    """
    return pytesseract.image_to_string(image, lang=lang)


def process_pdf_pages(images: list[Image.Image], lang: str = "eng") -> list[str]:
    """
    Extract text from all page images.

    Args:
        images: List of PIL Images (one per page)
        lang: Tesseract language code

    Returns:
        List of text strings, one per page
    """
    texts = []
    for img in images:
        text = extract_text(img, lang)
        texts.append(text)
    return texts
