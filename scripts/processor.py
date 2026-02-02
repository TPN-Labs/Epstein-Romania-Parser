"""PDF processing and parallel execution."""

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

from pdf_parser import extract_text_direct, extract_pages_as_images
from ocr_processor import process_pdf_pages
from keyword_search import search_text, SearchResult
from progress import ProgressBar
from result_writer import StreamingResultWriter


# Global variable for worker processes - initialized once per worker
_worker_keywords: list[str] = []


def _init_worker(keywords: list[str]) -> None:
    """Initialize worker process with shared keywords."""
    global _worker_keywords
    _worker_keywords = keywords


class PdfTask(NamedTuple):
    """Represents a PDF processing task."""
    pdf_path: Path
    folder_name: str


def find_pdfs(folder: Path) -> list[Path]:
    """Find all PDF files in a folder."""
    return sorted(folder.glob("*.pdf"))


def process_pdf(pdf_path: Path, folder_name: str, keywords: list[str]) -> list[SearchResult]:
    """
    Process a single PDF: extract text (fast) or OCR (slow fallback).

    Returns:
        List of SearchResult objects
    """
    results = []

    try:
        # Fast path: try direct text extraction first
        page_texts = extract_text_direct(str(pdf_path))

        # Slow path: fall back to OCR only if needed
        if page_texts is None:
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
    Uses globally initialized keywords to avoid serialization overhead.

    Returns:
        Tuple of (results, error_message or None)
    """
    try:
        results = process_pdf(task.pdf_path, task.folder_name, _worker_keywords)
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

    tasks = [PdfTask(pdf, folder.name) for pdf in pdfs]
    progress = ProgressBar(total=len(pdfs), workers=num_workers)

    print(f"\n{folder.name}: Processing {len(pdfs)} PDFs with {num_workers} workers...")

    # Use initializer to pass keywords once per worker process (not per task)
    with ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=_init_worker,
        initargs=(keywords,)
    ) as executor:
        # Submit tasks in chunks to reduce memory pressure
        futures_map: dict = {}
        task_iter = iter(tasks)
        batch_size = num_workers * 4  # Keep workers fed without overwhelming memory

        # Initial batch submission
        for task in [next(task_iter, None) for _ in range(batch_size)]:
            if task is not None:
                future = executor.submit(process_pdf_task, task)
                futures_map[future] = task

        while futures_map:
            # Wait for any future to complete
            done_futures = []
            for future in as_completed(futures_map):
                done_futures.append(future)
                break  # Process one at a time to submit new tasks

            for future in done_futures:
                task = futures_map.pop(future)
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

                # Submit next task to keep workers busy
                next_task = next(task_iter, None)
                if next_task is not None:
                    new_future = executor.submit(process_pdf_task, next_task)
                    futures_map[new_future] = next_task

    progress.finish()
    return match_count, len(pdfs), errors
