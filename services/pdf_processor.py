"""
PDF Processing Service using PyMuPDF (fitz).
- Downloads remote PDFs with streaming and timeouts.
- Accepts manual file uploads.
- Extracts text page-by-page preserving 1-indexed page numbers.
- Handles scanned/image PDFs with explicit OCR limitation notices.
- Detects section headings and chunks text into 700-1000 char windows with overlap.
- Emits rich metadata: paper_id, paper_title, page_number, section, chunk_id.
"""

import os
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import requests

from config import PAPERS_DIR, CHUNK_SIZE, CHUNK_OVERLAP


SECTION_PATTERNS = [
    r"^(?:[0-9ivxIVX]+\.?\s+)?abstract\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?introduction\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?background\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?related\s+work\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?methodology\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?method\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?system\s+design\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?architecture\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?experiments?\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?experimental\s+setup\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?results?\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?discussion\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?limitations?\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?conclusion\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?future\s+work\b",
    r"^(?:[0-9ivxIVX]+\.?\s+)?references\b",
]


def download_paper_pdf(pdf_url: str, paper_id: str) -> Tuple[bool, str]:
    """
    Download a PDF file from a direct URL into the storage/papers directory.
    Returns (success: bool, local_path_or_error: str).
    """
    if not pdf_url:
        return False, "No PDF URL provided for this paper."

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*"
    }

    try:
        clean_paper_id = re.sub(r"[^\w\-]", "_", paper_id)
        local_filename = f"{clean_paper_id}.pdf"
        target_path = PAPERS_DIR / local_filename

        response = requests.get(pdf_url, headers=headers, stream=True, timeout=25)
        if response.status_code != 200:
            return False, f"Failed to download PDF: HTTP Status {response.status_code}"

        # Check content type if available
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" in content_type and "pdf" not in content_type:
            return False, "Target URL returned an HTML landing page rather than direct PDF binary."

        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Validate that the downloaded file is a non-empty PDF
        if target_path.stat().st_size < 1024:
            target_path.unlink(missing_ok=True)
            return False, "Downloaded file is suspiciously small or empty."

        return True, str(target_path)

    except requests.exceptions.Timeout:
        return False, "Connection timed out while downloading the PDF."
    except Exception as e:
        return False, f"Download failed: {str(e)}"


def save_uploaded_pdf(uploaded_file_bytes: bytes, paper_id: str, original_filename: str) -> str:
    """Save user-uploaded PDF bytes to local paper storage."""
    clean_paper_id = re.sub(r"[^\w\-]", "_", paper_id)
    local_filename = f"{clean_paper_id}_manual.pdf"
    target_path = PAPERS_DIR / local_filename

    with open(target_path, "wb") as f:
        f.write(uploaded_file_bytes)

    return str(target_path)


def detect_section_title(line: str) -> Optional[str]:
    """Check if a line matches standard academic section headings."""
    clean_line = line.strip().lower()
    if len(clean_line) > 60:
        return None

    for pattern in SECTION_PATTERNS:
        if re.search(pattern, clean_line):
            # Clean heading for clean metadata
            heading = re.sub(r"^(?:[0-9IVX]+\.?\s+)?", "", line.strip(), flags=re.IGNORECASE).strip()
            return heading.title()
    return None


def extract_and_chunk_pdf(
    pdf_path: str,
    paper_id: str,
    paper_title: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP
) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
    """
    Extracts text per page from PDF using PyMuPDF (fitz) and segments into chunks.
    
    Returns:
        chunks: List of chunk dictionaries with metadata
        page_count: Total pages processed
        error_message: Error string if scanned/unreadable or None
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return [], 0, "PyMuPDF (fitz) is not installed."

    if not os.path.exists(pdf_path):
        return [], 0, f"PDF file not found at: {pdf_path}"

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return [], 0, f"Failed to open PDF document: {str(e)}"

    total_pages = len(doc)
    if total_pages == 0:
        doc.close()
        return [], 0, "PDF document contains 0 pages."

    pages_text: List[Tuple[int, str]] = []
    total_char_count = 0

    for page_idx in range(total_pages):
        page = doc.load_page(page_idx)
        text = page.get_text("text")
        cleaned = text.strip()
        pages_text.append((page_idx + 1, cleaned))
        total_char_count += len(cleaned)

    doc.close()

    # Scanned PDF check: if document contains virtually no selectable text
    if total_char_count < 250 or (total_pages > 2 and total_char_count / total_pages < 50):
        return [], total_pages, (
            "OCR LIMITATION: The PDF appears to be a scanned image or lacks selectable text layers. "
            "Please provide an electronically generated PDF with selectable text."
        )

    # Chunking process preserving page number and active section
    chunks: List[Dict[str, Any]] = []
    current_section = "Introduction"

    for page_num, text in pages_text:
        lines = text.split("\n")
        page_paragraphs: List[str] = []
        current_para = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if current_para:
                    page_paragraphs.append(" ".join(current_para))
                    current_para = []
                continue

            sec = detect_section_title(line_str)
            if sec:
                if current_para:
                    page_paragraphs.append(" ".join(current_para))
                    current_para = []
                current_section = sec

            current_para.append(line_str)

        if current_para:
            page_paragraphs.append(" ".join(current_para))

        # Merge and window paragraphs into chunks of chunk_size
        full_page_text = " ".join(page_paragraphs)
        if not full_page_text:
            continue

        start = 0
        text_len = len(full_page_text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # If not at the end of text, find nearest sentence end or space
            if end < text_len:
                cut_idx = full_page_text.rfind(". ", start + int(chunk_size * 0.7), end)
                if cut_idx != -1:
                    end = cut_idx + 1
                else:
                    space_idx = full_page_text.rfind(" ", start + int(chunk_size * 0.8), end)
                    if space_idx != -1:
                        end = space_idx

            chunk_text = full_page_text[start:end].strip()
            if len(chunk_text) >= 100:
                chunk_id = f"{paper_id}_p{page_num}_c{len(chunks) + 1}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "paper_id": paper_id,
                    "paper_title": paper_title,
                    "page_number": page_num,
                    "section": current_section,
                    "content": chunk_text,
                    "char_length": len(chunk_text)
                })

            if end >= text_len:
                break
            start = max(start + 1, end - chunk_overlap)

    return chunks, total_pages, None
