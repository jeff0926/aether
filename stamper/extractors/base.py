"""
base.py - Base extractor class for all format extractors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union


class BaseExtractor(ABC):
    """Base class for all format-specific extractors."""

    def __init__(self, content: Union[str, Path], document: str):
        """
        Initialize extractor.

        Args:
            content: File content (string) or path to file
            document: Document name for source references
        """
        self.content = content
        self.document = document

    @abstractmethod
    def extract(self) -> dict:
        """
        Extract structured content from the source.

        Returns dict with:
        - sections: list of {heading, level, content, lists, tables}
        - tables: list of table dicts (if applicable)
        - raw_text: full text content
        - frontmatter: dict of metadata (if applicable)
        """
        pass

    def get_format(self) -> str:
        """Return format identifier for this extractor."""
        return self.__class__.__name__.replace("Extractor", "").lower()
