"""Configuration constants for DOJ crawler."""

from pathlib import Path

# Base URL
SEARCH_URL = "https://www.justice.gov/epstein/search"

# CSS Selectors
SELECTORS = {
    "not_a_robot": "input.usa-button[value='I am not a robot']",  # "I am not a robot" button
    "age_verify_yes": "#age-button-yes",
    "search_input": "#searchInput",
    "search_button": "#searchButton",
    "results_container": "#results",
    "result_item": ".result-item",
    "result_link": "h3 a",
    "result_excerpt": "p.result-excerpt",
    "pagination": "#pagination",
    "pagination_label": "#paginationLabel",
    "next_page": "#next-link a",
    "page_link": "#pagination a[aria-label='Page {}']",
}

# Timeouts (seconds)
TIMEOUTS = {
    "page_load": 30,
    "element_wait": 10,
    "age_verify_wait": 15,
}

# Rate limiting (seconds)
DELAYS = {
    "page_navigation": 1.0,
    "pdf_download": 0.5,
    "retry_base": 2.0,
}

# Retry settings
MAX_RETRIES = 3

# Default keywords
DEFAULT_KEYWORDS = ["Timisoara", "Iasi", "Cluj", "Craiova", "Bucharest", "Bucuresti", "Romania", "Romanian"]

# Output paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
CSV_FILE = OUTPUT_DIR / "doj_search_results.csv"
PDFS_DIR = OUTPUT_DIR / "pdfs"
