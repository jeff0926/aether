"""
pdf.py - PDF document extractor.
"""

from pathlib import Path
from .base import BaseExtractor


class PDFExtractor(BaseExtractor):
    """Extract content from PDF files."""

    def extract(self) -> dict:
        """
        Extract content from PDF.

        Requires: pdfplumber package
        """
        try:
            import pdfplumber
        except ImportError:
            return {
                "error": "dependency_missing",
                "message": "pdfplumber not installed. Run: pip install pdfplumber",
                "sections": [],
                "tables": [],
                "raw_text": "",
                "pages": []
            }

        path = Path(self.content) if not isinstance(self.content, str) else Path(self.content)

        pages = []
        all_text = []

        try:
            with pdfplumber.open(str(path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""

                    if not text.strip() and i == 0:
                        # Likely scanned PDF
                        return {
                            "error": "ocr_required",
                            "message": f"Page {i+1} has no text layer. PDF may be scanned.",
                            "pages_with_text": i,
                            "sections": [],
                            "tables": [],
                            "raw_text": ""
                        }

                    tables = page.extract_tables() or []
                    pages.append({
                        "page_number": i + 1,
                        "text": text,
                        "tables": [{"rows": t} for t in tables]
                    })
                    all_text.append(text)

        except Exception as e:
            return {
                "error": "extraction_failed",
                "message": str(e),
                "sections": [],
                "tables": [],
                "raw_text": "",
                "pages": []
            }

        raw_text = '\n'.join(all_text)

        # Best-effort section detection from text
        sections = self._detect_sections(raw_text)

        # Flatten tables from all pages
        tables = []
        for page in pages:
            tables.extend(page.get("tables", []))

        return {
            "frontmatter": {},
            "sections": sections,
            "prohibitions_in_frontmatter": [],
            "pages": pages,
            "tables": tables,
            "raw_text": raw_text
        }

    def _detect_sections(self, text: str) -> list[dict]:
        """Best-effort section detection from PDF text."""
        import re

        sections = []
        current = {
            "heading": None,
            "level": 0,
            "content": [],
            "lists": [],
            "tables": []
        }

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Heuristic: short uppercase lines are likely headings
            if len(line) < 60 and line.isupper():
                if current["content"]:
                    current["content"] = '\n'.join(current["content"])
                    sections.append(current)
                current = {
                    "heading": line.title(),
                    "level": 1,
                    "content": [],
                    "lists": [],
                    "tables": []
                }
            # Numbered sections like "1.1 Introduction"
            elif re.match(r'^\d+(\.\d+)*\s+[A-Z]', line):
                if current["content"]:
                    current["content"] = '\n'.join(current["content"])
                    sections.append(current)
                current = {
                    "heading": line,
                    "level": line.count('.') + 1,
                    "content": [],
                    "lists": [],
                    "tables": []
                }
            else:
                current["content"].append(line)

        if current["content"]:
            current["content"] = '\n'.join(current["content"])
            sections.append(current)

        return sections
