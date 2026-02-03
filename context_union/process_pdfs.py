#!/usr/bin/env python3
"""
PDF Email Unification Script
Processes PDF files containing emails, identifies related/linked files,
and produces consolidated markdown reports.

This is the entry point. All logic has been refactored into the pdf_processor package.
"""

from pdf_processor import main

if __name__ == "__main__":
    main()
