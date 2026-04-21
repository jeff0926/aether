"""
jsonld.py - JSON-LD knowledge graph extractor.
Direct import path - bypasses NAS pipeline.
"""

import json
from pathlib import Path
from .base import BaseExtractor


class JSONLDExtractor(BaseExtractor):
    """Extract nodes from JSON-LD files for direct KG import."""

    def extract(self) -> dict:
        """
        Extract content from JSON-LD.

        JSON-LD files are imported directly into the KG
        without NAS conversion.
        """
        if isinstance(self.content, (str, Path)):
            path = Path(self.content)
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                return {
                    "error": "json_parse_error",
                    "message": str(e),
                    "direct_import": False,
                    "nodes": [],
                    "context": {}
                }
        else:
            # Already parsed dict
            data = self.content

        nodes = data.get("@graph", [])
        if not nodes and "@id" in data:
            # Single node document
            nodes = [data]

        return {
            "direct_import": True,
            "nodes": nodes,
            "context": data.get("@context", {}),
            "node_count": len(nodes),
            "frontmatter": {},
            "sections": [],
            "prohibitions_in_frontmatter": [],
            "tables": [],
            "raw_text": ""
        }
