"""PDF processing and parallel execution."""

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

from pdf_parser import extract_pages_as_images
from ocr_processor import process_pdf_pages
from keyword_search import search_text, SearchResult
from progress import ProgressBar
from result_writer import StreamingResultWriter


class PdfTask(NamedTuple):
    """Represents a PDF processing task."""
    pdf_path: Path
    folder_name: str
    keywords: list[str]


def find_pdfs(folder: Path) -> list[Path]:
    """Find all PDF files in a folder."""
    return sorted(folder.glob("*.pdf"))


def process_pdf(pdf_path: Path, folder_name: str, keywords: list[str]) -> list[SearchResult]:
    """
    Process a single PDF: extract images, OCR, and search for keywords.

    Returns:
        List of SearchResult objects
    """
    results = []

    try:
        images = extract_pages_as_images(str(pdf_path))
        page_texts = process_pdf_pages(images)

        for page_num, text in enumerate(page_texts, start=1):
            matches = search_text(text, keywords)
            for keyword, context in matches:
                results.append(SearchResult(
                    folder=folder_name,
                    filename=pdf_path.name,
                    page=page_num,
                    keyword=keyword,
                    context=context
                ))
    except Exception:
        pass  # Errors collected at task level

    return results


def process_pdf_task(task: PdfTask) -> tuple[list[SearchResult], str | None]:
    """
    Worker function for multiprocessing.

    Returns:
        Tuple of (results, error_message or None)
    """
    try:
        results = process_pdf(task.pdf_path, task.folder_name, task.keywords)
        return results, None
    except Exception as e:
        return [], f"{task.pdf_path.name}: {e}"


def process_folder(
    folder: Path,
    keywords: list[str],
    num_workers: int,
    writer: StreamingResultWriter
) -> tuple[int, int, list[str]]:
    """
    Process all PDFs in a folder using parallel workers.

    Returns:
        Tuple of (match_count, pdf_count, errors)
    """
    pdfs = find_pdfs(folder)
    if not pdfs:
        return 0, 0, []

    match_count = 0
    errors: list[str] = []
    completed = 0
    start_time = time.time()

    tasks = [PdfTask(pdf, folder.name, keywords) for pdf in pdfs]
    progress = ProgressBar(total=len(pdfs), workers=num_workers)

    print(f"\n{folder.name}: Processing {len(pdfs)} PDFs with {num_workers} workers...")

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_pdf_task, t): t for t in tasks}

        for future in as_completed(futures):
            task = futures[future]
            completed += 1

            try:
                results, error = future.result()
                new_matches = None

                if results:
                    writer.write(results)
                    match_count += len(results)
                    new_matches = [(r.keyword, r.context, r.filename) for r in results]

                if error:
                    errors.append(error)

            except Exception as e:
                errors.append(f"{task.pdf_path.name}: {e}")
                new_matches = None

            progress.update(
                current=completed,
                filename=task.pdf_path.name,
                elapsed=time.time() - start_time,
                matches=writer.count,
                new_matches=new_matches
            )

    progress.finish()
    return match_count, len(pdfs), errors
