PDF Keyword Parser
==================

Parses PDF files from DS-* folders and searches for keywords using OCR.
Designed for scanned EFTA documents without embedded text layers.


FOLDER STRUCTURE
----------------

EpParser/
├── DS-8/                   # PDF folders (add as needed)
├── DS-9/
├── DS-10/
├── DS-11/
├── DS-12/                  # Currently available
├── scripts/
│   ├── main.py             # Entry point
│   ├── pdf_parser.py       # PDF to image extraction
│   ├── ocr_processor.py    # Tesseract OCR processing
│   ├── keyword_search.py   # Keyword matching
│   ├── requirements.txt    # Python dependencies
│   ├── config/
│   │   └── keywords.txt    # Keywords to search (one per line)
│   └── output/
│       └── results.csv     # Search results (generated)
└── README.txt


PREREQUISITES
-------------

1. Python 3.10+ installed

2. Install Tesseract OCR (macOS):
   brew install tesseract

3. Install Python dependencies:
   cd scripts
   pip3 install -r requirements.txt


USAGE
-----

1. Place PDF files in DS-* folders in the project root

2. Edit keywords in scripts/config/keywords.txt (one keyword per line)

3. Run the parser:
   cd scripts
   python3 main.py

4. Results are saved to scripts/output/results.csv


OUTPUT FORMAT
-------------

The results.csv file contains:
- folder:   Source folder name (e.g., DS-12)
- filename: PDF filename
- page:     Page number where keyword was found
- keyword:  The matched keyword
- context:  Text surrounding the match


ADDING KEYWORDS
---------------

Edit scripts/config/keywords.txt
Add one keyword per line (case-insensitive):

  romania
  romanian
  bucharest


NOTES
-----

- PDFs are processed using OCR (Tesseract)
- Processing time depends on PDF count and page count
- Progress is displayed during processing
