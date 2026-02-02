# PDF Keyword Parser

Parses PDF files from DS-* folders and searches for keywords using OCR.
Designed for scanned EFTA documents without embedded text layers.

## Folder Structure

```
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
└── README.md
```

## Prerequisites

1. Python 3.10+ installed

2. Install Tesseract OCR (macOS):
   ```bash
   brew install tesseract
   ```

3. Install Python dependencies:
   ```bash
   cd scripts
   pip3 install -r requirements.txt
   ```

## Usage

1. Place PDF files in DS-* folders in the project root

2. Edit keywords in `scripts/config/keywords.txt` (one keyword per line)

3. Run the parser:
   ```bash
   cd scripts
   python3 main.py
   ```

4. Results are saved to `scripts/output/results.csv`

## Output Format

The `results.csv` file contains:

| Column   | Description                          |
|----------|--------------------------------------|
| folder   | Source folder name (e.g., DS-12)     |
| filename | PDF filename                         |
| page     | Page number where keyword was found  |
| keyword  | The matched keyword                  |
| context  | Text surrounding the match           |

## Adding Keywords

Edit `scripts/config/keywords.txt` and add one keyword per line (case-insensitive):

```
romania
romanian
bucharest
```

## Notes

- PDFs are processed using OCR (Tesseract)
- Processing time depends on PDF count and page count
- Progress is displayed during processing
