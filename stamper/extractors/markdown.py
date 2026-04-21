"""
markdown.py - Markdown file extractor.
Handles .md files including SKILL.md and CLAUDE.md formats.
"""

import re
from typing import Optional
from .base import BaseExtractor


class MarkdownExtractor(BaseExtractor):
    """Extract structured content from Markdown files."""

    def extract(self) -> dict:
        """
        Extract content from Markdown.

        Special handling:
        - YAML frontmatter extraction
        - Section splitting on ## headers
        - Code block extraction (separate from normative content)
        - List item extraction
        """
        content = self.content if isinstance(self.content, str) else self.content.read_text(encoding='utf-8')

        # Extract YAML frontmatter
        frontmatter = {}
        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if fm_match:
            frontmatter = self._parse_yaml_frontmatter(fm_match.group(1))
            content = content[fm_match.end():]

        # Extract sections
        sections = self._extract_sections(content)

        # Check frontmatter for routing prohibitions
        prohibitions_in_frontmatter = []
        desc = frontmatter.get("description", "")
        if "Do NOT use" in desc or "not for" in desc.lower():
            prohibitions_in_frontmatter = self._extract_routing_prohibitions(desc)

        # Build raw text (markdown stripped)
        raw_text = re.sub(r'#{1,6}\s+|```[\s\S]*?```|\[.*?\]\(.*?\)', '', content)

        return {
            "frontmatter": frontmatter,
            "sections": sections,
            "prohibitions_in_frontmatter": prohibitions_in_frontmatter,
            "raw_text": raw_text.strip(),
            "tables": [],  # Markdown tables extracted within sections
        }

    def _parse_yaml_frontmatter(self, yaml_text: str) -> dict:
        """Parse YAML frontmatter into dict."""
        result = {}
        for line in yaml_text.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                result[key] = value
        return result

    def _extract_sections(self, content: str) -> list[dict]:
        """Split content into sections by headers."""
        sections = []
        current = {
            "heading": None,
            "level": 0,
            "content": [],
            "code_blocks": [],
            "lists": [],
            "tables": []
        }
        in_code_block = False
        code_block_content = []

        for line in content.split('\n'):
            # Code block detection
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of code block
                    current["code_blocks"].append('\n'.join(code_block_content))
                    code_block_content = []
                in_code_block = not in_code_block
                continue

            if in_code_block:
                code_block_content.append(line)
                continue

            # Heading detection
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                # Save previous section
                if current["heading"] or current["content"]:
                    sections.append(self._finalize_section(current))
                level = len(heading_match.group(1))
                current = {
                    "heading": heading_match.group(2).strip(),
                    "level": level,
                    "content": [],
                    "code_blocks": [],
                    "lists": [],
                    "tables": []
                }
                continue

            # List item detection
            list_match = re.match(r'^[-*+]\s+(.+)$', line)
            if list_match:
                current["lists"].append(list_match.group(1).strip())
                continue

            # Numbered list detection
            numbered_match = re.match(r'^\d+[.)]\s+(.+)$', line)
            if numbered_match:
                current["lists"].append(numbered_match.group(1).strip())
                continue

            # Regular content
            if line.strip():
                current["content"].append(line.strip())

        # Save final section
        if current["heading"] or current["content"]:
            sections.append(self._finalize_section(current))

        return sections

    def _finalize_section(self, section: dict) -> dict:
        """Finalize section by joining content."""
        section["content"] = '\n'.join(section["content"])
        return section

    def _extract_routing_prohibitions(self, description: str) -> list[str]:
        """Extract routing prohibitions from frontmatter description."""
        prohibitions = []
        patterns = [
            r'Do NOT use (?:for|when|to)\s+(.+?)(?:\.|,|$)',
            r'Not for\s+(.+?)(?:\.|,|$)',
            r'Do not use (?:for|when|to)\s+(.+?)(?:\.|,|$)',
            r'Avoid using (?:for|when)\s+(.+?)(?:\.|,|$)',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, description, re.IGNORECASE):
                prohibitions.append(match.group(1).strip())

        return prohibitions
