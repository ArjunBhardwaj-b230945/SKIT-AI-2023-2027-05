"""
TaxSathi - Document Parsing
Week: 25-09-2026 to 01-10-2026

Purpose:
Clean and normalize parsed Form 16 / Form 26AS text before field detection.
This module does not calculate tax or generate ITR.
"""

import re


def clean_text(text: str) -> str:
    """Normalize parsed document text while preserving useful values."""
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Normalize common whitespace without destroying line structure.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove obvious parser artefacts.
    text = re.sub(r"(?i)\bpage\s+\d+\s+of\s+\d+\b", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)

    return text.strip()


def clean_lines(text: str) -> list[str]:
    """Return non-empty normalized lines."""
    cleaned = clean_text(text)
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


if __name__ == "__main__":
    sample = "Assessment   Year: 2026-27\r\n\r\nSalary   17(1):  750000"
    print(clean_text(sample))
