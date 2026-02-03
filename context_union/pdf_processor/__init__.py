"""
PDF Email Unification Package
Processes PDF files containing emails, identifies related/linked files,
and produces consolidated markdown reports.
"""

from .config import PDF_DIR, OUTPUT_DIR, CACHE_FILE
from .models import EmailMessage, Document, Conversation, NameRegistry
from .parser import parse_pdf, parse_email_thread
from .clustering import cluster_documents, calculate_link_score
from .output import generate_markdown, generate_standalone_markdown, generate_index
from .main import main

__all__ = [
    'PDF_DIR',
    'OUTPUT_DIR',
    'CACHE_FILE',
    'EmailMessage',
    'Document',
    'Conversation',
    'NameRegistry',
    'parse_pdf',
    'parse_email_thread',
    'cluster_documents',
    'calculate_link_score',
    'generate_markdown',
    'generate_standalone_markdown',
    'generate_index',
    'main',
]
