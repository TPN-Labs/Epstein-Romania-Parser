"""
Configuration settings for PDF processing.
"""

from pathlib import Path

# Base directory (parent of this package)
BASE_DIR = Path(__file__).resolve().parent.parent

# Directories - relative to project root
PDF_DIR = BASE_DIR / "pdfs"
OUTPUT_DIR = BASE_DIR / "output_report"
CACHE_FILE = BASE_DIR / ".pdf_cache.json"

# Clustering thresholds
DEFAULT_LINK_THRESHOLD = 30.0
MAX_CLUSTER_SIZE = 15

# Junk text patterns to remove from extracted PDF text
JUNK_PATTERNS = [
    # Confidentiality disclaimers (with optional quote markers like "> ")
    r'(?:^>?\s*\*{5,}\s*\n)?(?:^>?\s*)?The information contained in this communication is[\s\S]*?(?:including all attachments|all copies thereof)[\s\S]*?(?:attachments\.?|thereof[,.])',
    r'(?:^>?\s*)?The information contained in this communication[\s\S]*?destroy this communication[\s\S]*?attachments\.?',
    r'\*{10,}[\s\S]*?The information contained in this communication is[\s\S]*?all rights reserved[\s\S]*?\*{5,}',
    r'\*{10,}[\s\S]*?confidential[\s\S]*?attachments[\s\S]*?\*{5,}',
    r'Unauthorized use,?\s*disc[\s\S]*?prohibited',
    r'copyright\s*-?\s*all rights reserved',
    # Quoted confidentiality footers (lines starting with >)
    r'(?:^>\s*)+\*{5,}[\s\S]*?(?:^>\s*)+attachments\.?',
    r'(?:^>\s*w{5,}\*{5,}[\s\S]*?)(?=\n(?!>)|$)',
    # Sent from devices
    r'Sent from my iP(?:hone|od|ad)',
    r'Sent from Samsung Mobile',
    r'Sent from my BlackBerry',
    r'Sent from (?:a )?Samsung (?:device|Galaxy)',
    r'Sent from Samaung Malib',  # OCR typo
    r'Sent Irma Sainting.*',  # OCR artifact
    r'Sag from Si mmg Mat',  # OCR artifact
    # EFTA reference numbers at page bottoms
    r'EFTA_R\d+_\d+',
    r'EFTA\d{8,}(?:\s|$)',
    # XML/plist artifacts
    r'<\?xml[\s\S]*?\?>',
    r'<!DOCTYPE[\s\S]*?>',
    # Multiple asterisks
    r'\*{5,}',
    # Extra whitespace normalization
    r'\n{3,}',
]

# Common email addresses to ignore when calculating link scores
# (too common to be meaningful for linking)
COMMON_EMAILS_TO_IGNORE = {
    'jeevacation@gmail.com',
    'jee@his.com',
    'je@his.com',
}
