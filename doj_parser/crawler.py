"""Core Selenium crawler for DOJ Epstein Library."""

import re
import time
from typing import Generator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager

from config import SEARCH_URL, SELECTORS, TIMEOUTS, DELAYS
from models import CrawlResult


class DOJCrawler:
    """Selenium-based crawler for DOJ Epstein Library search page."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self._pdf_queue: list[tuple[str, str, str]] = []  # (url, folder, filename)

    def __enter__(self) -> "DOJCrawler":
        self._init_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _init_driver(self):
        """Initialize Chrome WebDriver."""
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(TIMEOUTS["page_load"])

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def navigate_to_search(self):
        """Navigate to the search page."""
        print(f"Navigating to {SEARCH_URL}...")
        self.driver.get(SEARCH_URL)

    def handle_not_a_robot(self) -> bool:
        """Handle the 'I am not a robot' button if present."""
        try:
            print("Checking for 'I am not a robot' button...")
            wait = WebDriverWait(self.driver, 5)
            button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTORS["not_a_robot"]))
            )
            button.click()
            print("Clicked 'I am not a robot' button.")
            time.sleep(3)  # Wait for page to reload after clicking
            return True
        except TimeoutException:
            print("No 'I am not a robot' button found.")
        return False

    def handle_age_verification(self) -> bool:
        """Handle the age verification popup if present."""
        try:
            print("Waiting for age verification...")
            wait = WebDriverWait(self.driver, TIMEOUTS["age_verify_wait"])
            yes_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTORS["age_verify_yes"]))
            )
            yes_button.click()
            print("Age verification confirmed.")
            time.sleep(1)  # Brief pause after clicking
            return True
        except TimeoutException:
            print("No age verification popup found or already verified.")
            return False

    def search(self, keyword: str):
        """Execute a search for the given keyword."""
        print(f"Searching for: {keyword}")

        # Scroll to top of page first
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

        wait = WebDriverWait(self.driver, TIMEOUTS["element_wait"])

        # Find and clear the search input
        search_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["search_input"]))
        )
        search_input.clear()
        search_input.send_keys(keyword)

        # Click search button using JavaScript to avoid interception issues
        search_button = self.driver.find_element(By.CSS_SELECTOR, SELECTORS["search_button"])
        self.driver.execute_script("arguments[0].click();", search_button)

        # Wait for results to load
        time.sleep(DELAYS["page_navigation"])
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["results_container"]))
        )

    def get_total_results(self) -> tuple[int, int]:
        """Parse pagination label to get total results and pages.

        Returns (total_results, total_pages).
        """
        try:
            label = self.driver.find_element(
                By.CSS_SELECTOR, SELECTORS["pagination_label"]
            ).text
            # Parse "Showing X to Y of Z Results."
            match = re.search(r"of\s+(\d+)\s+Results", label)
            if match:
                total = int(match.group(1))
                # Calculate total pages (assuming 10 results per page based on typical pagination)
                # Parse current range to determine page size
                range_match = re.search(r"Showing\s+(\d+)\s+to\s+(\d+)", label)
                if range_match:
                    start, end = int(range_match.group(1)), int(range_match.group(2))
                    page_size = end - start + 1
                    total_pages = (total + page_size - 1) // page_size
                    return total, total_pages
                return total, (total + 9) // 10  # Default to 10 per page
        except NoSuchElementException:
            pass
        return 0, 0

    def _parse_result_item(self, item, keyword: str, page: int) -> CrawlResult | None:
        """Parse a single result item element."""
        try:
            # Find the link element
            link = item.find_element(By.CSS_SELECTOR, SELECTORS["result_link"])
            pdf_url = link.get_attribute("href")
            filename = link.text.strip()

            # Parse folder from heading text (e.g., "EFTA02726187.pdf - DataSet 11")
            heading = item.find_element(By.CSS_SELECTOR, "h3").text
            folder_match = re.search(r"DataSet\s+(\d+)", heading)
            folder = f"DS-{folder_match.group(1)}" if folder_match else "Unknown"

            # Get excerpt/context
            try:
                excerpt = item.find_element(
                    By.CSS_SELECTOR, SELECTORS["result_excerpt"]
                ).text.strip()
            except NoSuchElementException:
                excerpt = ""

            return CrawlResult(
                folder=folder,
                keyword=keyword,
                filename=filename,
                page=page,
                context=excerpt,
                pdf_url=pdf_url,
            )
        except (NoSuchElementException, StaleElementReferenceException) as e:
            print(f"  Error parsing result item: {e}")
            return None

    def extract_results(self, keyword: str, page: int) -> list[CrawlResult]:
        """Extract all results from the current page."""
        results = []
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, SELECTORS["result_item"])
            for item in items:
                result = self._parse_result_item(item, keyword, page)
                if result:
                    results.append(result)
        except Exception as e:
            print(f"  Error extracting results: {e}")
        return results

    def _click_next_page(self) -> bool:
        """Click the Next page link. Returns True if successful."""
        try:
            next_link = self.driver.find_element(By.CSS_SELECTOR, SELECTORS["next_page"])
            if next_link.is_displayed():
                # Scroll to the pagination area first
                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_link)
                time.sleep(0.3)
                # Click using JavaScript to avoid interception
                self.driver.execute_script("arguments[0].click();", next_link)
                return True
        except NoSuchElementException:
            pass
        return False

    def _has_next_page(self) -> bool:
        """Check if there's a next page link."""
        try:
            next_link = self.driver.find_element(By.CSS_SELECTOR, SELECTORS["next_page"])
            return next_link.is_displayed()
        except NoSuchElementException:
            return False

    def crawl_keyword(self, keyword: str) -> Generator[CrawlResult, None, None]:
        """Crawl all results for a keyword, yielding each result."""
        self.search(keyword)

        total_results, total_pages = self.get_total_results()
        print(f"Found {total_results} total results across ~{total_pages} pages")

        if total_results == 0:
            return

        seen_filenames = set()
        page = 1

        while True:
            print(f"  Processing page {page}...")

            # Wait for results to be present
            time.sleep(0.5)

            # Extract results from current page
            results = self.extract_results(keyword, page)
            for result in results:
                if result.filename not in seen_filenames:
                    seen_filenames.add(result.filename)
                    self._pdf_queue.append((result.pdf_url, result.folder, result.filename))
                    yield result

            print(f"    Found {len(results)} results on page {page} ({len(seen_filenames)} total)")

            # Check if there's a next page
            if not self._has_next_page():
                print(f"  No more pages. Finished at page {page}.")
                break

            # Click next page
            if not self._click_next_page():
                print(f"  Failed to click next page. Stopping at page {page}.")
                break

            # Wait for new page to load
            time.sleep(DELAYS["page_navigation"])
            page += 1

    def get_pdf_queue(self) -> list[tuple[str, str, str]]:
        """Return the queued PDFs for download."""
        return self._pdf_queue

    def clear_pdf_queue(self):
        """Clear the PDF download queue."""
        self._pdf_queue = []
