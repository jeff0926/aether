"""
yaml_extractor.py - YAML file extractor.
"""

from pathlib import Path
from .base import BaseExtractor


class YAMLExtractor(BaseExtractor):
    """Extract content from YAML files."""

    def extract(self) -> dict:
        """
        Extract content from YAML.

        Converts YAML structure to sections.
        """
        try:
            import yaml
        except ImportError:
            # Fall back to basic parsing
            return self._basic_yaml_parse()

        content = self.content if isinstance(self.content, str) else Path(self.content).read_text(encoding='utf-8')

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return {
                "error": "yaml_parse_error",
                "message": str(e),
                "frontmatter": {},
                "sections": [],
                "tables": [],
                "raw_text": content
            }

        # Convert dict keys to sections
        sections = self._dict_to_sections(data)

        return {
            "frontmatter": data if isinstance(data, dict) else {},
            "sections": sections,
            "prohibitions_in_frontmatter": [],
            "tables": [],
            "raw_text": content
        }

    def _dict_to_sections(self, data, level=1) -> list[dict]:
        """Convert nested dict to section list."""
        sections = []

        if not isinstance(data, dict):
            return sections

        for key, value in data.items():
            if isinstance(value, str):
                sections.append({
                    "heading": str(key),
                    "level": level,
                    "content": value,
                    "lists": [],
                    "tables": []
                })
            elif isinstance(value, list):
                # List items become list content
                sections.append({
                    "heading": str(key),
                    "level": level,
                    "content": "",
                    "lists": [str(item) for item in value if item],
                    "tables": []
                })
            elif isinstance(value, dict):
                # Nested dict becomes subsections
                sections.append({
                    "heading": str(key),
                    "level": level,
                    "content": "",
                    "lists": [],
                    "tables": []
                })
                sections.extend(self._dict_to_sections(value, level + 1))

        return sections

    def _basic_yaml_parse(self) -> dict:
        """Basic YAML parsing without pyyaml."""
        content = self.content if isinstance(self.content, str) else Path(self.content).read_text(encoding='utf-8')

        sections = []
        current_key = None
        current_content = []

        for line in content.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            # Key: value pattern
            if ':' in line and not line.startswith(' '):
                if current_key:
                    sections.append({
                        "heading": current_key,
                        "level": 1,
                        "content": '\n'.join(current_content),
                        "lists": [],
                        "tables": []
                    })
                key, _, value = line.partition(':')
                current_key = key.strip()
                current_content = [value.strip()] if value.strip() else []
            elif current_key:
                current_content.append(stripped)

        if current_key:
            sections.append({
                "heading": current_key,
                "level": 1,
                "content": '\n'.join(current_content),
                "lists": [],
                "tables": []
            })

        return {
            "frontmatter": {},
            "sections": sections,
            "prohibitions_in_frontmatter": [],
            "tables": [],
            "raw_text": content
        }
