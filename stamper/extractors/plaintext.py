"""
plaintext.py - Plain text file extractor.
"""

import re
from .base import BaseExtractor


class PlainTextExtractor(BaseExtractor):
    """Extract content from plain text files."""

    def extract(self) -> dict:
        """
        Extract content from plain text.

        Splits on blank lines to create pseudo-sections.
        """
        content = self.content if isinstance(self.content, str) else self.content.read_text(encoding='utf-8')

        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        sections = []
        for i, para in enumerate(paragraphs):
            # First line might be a title
            lines = para.split('\n')
            first_line = lines[0].strip()

            # Check if first line looks like a heading (short, possibly caps)
            is_heading = len(first_line) < 80 and not first_line.endswith('.')

            if is_heading and len(lines) > 1:
                sections.append({
                    "heading": first_line,
                    "level": 1,
                    "content": '\n'.join(lines[1:]).strip(),
                    "code_blocks": [],
                    "lists": [],
                    "tables": []
                })
            else:
                sections.append({
                    "heading": None,
                    "level": 0,
                    "content": para,
                    "code_blocks": [],
                    "lists": [],
                    "tables": []
                })

        return {
            "frontmatter": {},
            "sections": sections,
            "prohibitions_in_frontmatter": [],
            "raw_text": content,
            "tables": []
        }
