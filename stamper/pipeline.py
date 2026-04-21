"""
pipeline.py - Universal Extraction Pipeline
Part of the AETHER Stamper Agent.

Single entry point for all source formats.
Returns validated NAS documents ready for KG projection.
"""

import re
from pathlib import Path
from typing import Callable, Optional

from .dsl_parser import parse_dsl, is_dsl_sentence
from .nas import (
    build_nas_document, validate_nas_document, split_sentences,
    canonicalize_assertions, make_assertion_id, doc_to_slug
)
from .classifier import Classifier

from .extractors.markdown import MarkdownExtractor
from .extractors.plaintext import PlainTextExtractor
from .extractors.docx import DocxExtractor
from .extractors.pdf import PDFExtractor
from .extractors.excel import ExcelExtractor
from .extractors.jsonld import JSONLDExtractor
from .extractors.yaml_extractor import YAMLExtractor


# ─────────────────────────────────────────────────────────────────────
# FORMAT REGISTRY
# ─────────────────────────────────────────────────────────────────────

FORMAT_REGISTRY = {
    ".md": MarkdownExtractor,
    ".txt": PlainTextExtractor,
    ".docx": DocxExtractor,
    ".pdf": PDFExtractor,
    ".xlsx": ExcelExtractor,
    ".json": JSONLDExtractor,
    ".jsonld": JSONLDExtractor,
    ".yaml": YAMLExtractor,
    ".yml": YAMLExtractor,
}


# ─────────────────────────────────────────────────────────────────────
# SECTION TO ASSERTIONS
# ─────────────────────────────────────────────────────────────────────

def section_to_assertions(
    section: dict,
    document: str,
    classifier: Classifier,
    assertion_counter: list
) -> list[dict]:
    """
    Convert an extracted section to NAS assertions.
    Routes sentences to DSL parser or classifier based on content.
    """
    assertions = []
    section_name = section.get("heading")
    doc_slug = doc_to_slug(document)

    # Combine content and list items for classification
    sentences = []

    # Split content into sentences
    content = section.get("content", "")
    if isinstance(content, str) and content:
        sentences.extend(split_sentences(content))

    # Each list item is treated as a sentence
    for item in section.get("lists", []):
        if item and len(item.strip()) >= 10:
            sentences.append(item.strip())

    for sentence in sentences:
        if not sentence or len(sentence) < 10:
            continue

        # Generate assertion ID
        assertion_counter[0] += 1
        assertion_id = make_assertion_id(doc_slug, assertion_counter[0])

        # Route to DSL parser if sentence matches DSL pattern exactly
        if is_dsl_sentence(sentence):
            dsl_results = parse_dsl(sentence, document, section_name)
            for result in dsl_results:
                result["id"] = assertion_id
                assertions.append(result)
                assertion_counter[0] += 1
        else:
            # Run classifier pipeline (Layers 1, 2, 3)
            result = classifier.classify(sentence, document, section_name, assertion_id)

            # Include if confidence >= 0.50 (below 0.50 discard)
            if result.get("confidence", 0) >= 0.50:
                assertions.append(result)

    return assertions


# ─────────────────────────────────────────────────────────────────────
# TABLE TO ASSERTIONS
# ─────────────────────────────────────────────────────────────────────

def table_to_assertions(
    table: dict,
    document: str,
    section: str,
    classifier: Classifier,
    assertion_counter: list
) -> list[dict]:
    """Convert a table to NAS assertions."""
    assertions = []
    rows = table.get("rows", [])
    headers = table.get("header_row", [])
    doc_slug = doc_to_slug(document)

    if not rows:
        return assertions

    # Detect rule and constraint columns
    rule_col_idx = 0
    constraint_col_idx = None

    rule_keywords = ["rule", "description", "requirement", "constraint"]
    constraint_keywords = ["must", "shall", "should", "type", "strength"]

    for i, header in enumerate(headers):
        header_lower = header.lower()
        if any(k in header_lower for k in rule_keywords):
            rule_col_idx = i
        if any(k in header_lower for k in constraint_keywords):
            constraint_col_idx = i

    for row_idx, row in enumerate(rows):
        if row_idx == 0 and table.get("has_header"):
            continue  # Skip header row

        # Handle both list and dict rows
        if isinstance(row, dict):
            rule_text = list(row.values())[rule_col_idx] if row else ""
        else:
            rule_text = row[rule_col_idx] if len(row) > rule_col_idx else ""

        if not rule_text or len(str(rule_text)) < 5:
            continue

        rule_text = str(rule_text)

        # Generate assertion ID
        assertion_counter[0] += 1
        assertion_id = make_assertion_id(doc_slug, assertion_counter[0])

        # Get constraint if explicit column exists
        constraint_text = ""
        if constraint_col_idx is not None:
            if isinstance(row, dict):
                constraint_text = list(row.values())[constraint_col_idx] if len(row) > constraint_col_idx else ""
            else:
                constraint_text = row[constraint_col_idx] if len(row) > constraint_col_idx else ""

        if constraint_text:
            # Direct mapping from constraint column
            constraint_upper = str(constraint_text).upper().strip()
            if "MUST NOT" in constraint_upper:
                modality, polarity, strength = "PROHIBITION", "NEGATIVE", "MUST"
            elif "MUST" in constraint_upper:
                modality, polarity, strength = "OBLIGATION", "POSITIVE", "MUST"
            elif "SHOULD NOT" in constraint_upper:
                modality, polarity, strength = "PROHIBITION", "NEGATIVE", "SHOULD"
            elif "SHOULD" in constraint_upper:
                modality, polarity, strength = "RECOMMENDATION", "POSITIVE", "SHOULD"
            else:
                # Fall back to classifier
                result = classifier.classify(rule_text, document, section, assertion_id)
                if result.get("confidence", 0) >= 0.50:
                    assertions.append(result)
                continue

            assertions.append({
                "id": assertion_id,
                "text": rule_text,
                "modality": modality,
                "polarity": polarity,
                "strength": strength,
                "subject": None,
                "action": None,
                "condition": None,
                "context": section,
                "blacklist_candidates": [],
                "kg_node_type": "AntiPattern" if polarity == "NEGATIVE" else "Rule",
                "source_ref": {
                    "document": document,
                    "section": section,
                    "line_start": row_idx,
                    "line_end": row_idx
                },
                "confidence": 0.95,
                "ambiguity_flag": False,
                "extraction_method": "table_constraint_column",
                "canonical_id": None,
                "duplicates": []
            })
        else:
            # Run classifier on rule text
            result = classifier.classify(rule_text, document, section, assertion_id)
            if result.get("confidence", 0) >= 0.50:
                assertions.append(result)

    return assertions


# ─────────────────────────────────────────────────────────────────────
# FRONTMATTER ROUTING CONSTRAINTS
# ─────────────────────────────────────────────────────────────────────

def extract_routing_prohibitions(
    prohibitions: list[str],
    document: str,
    assertion_counter: list
) -> list[dict]:
    """
    Convert frontmatter routing prohibitions to NAS assertions.
    """
    assertions = []
    doc_slug = doc_to_slug(document)

    for prohibited_use in prohibitions:
        assertion_counter[0] += 1
        assertions.append({
            "id": make_assertion_id(doc_slug, assertion_counter[0]),
            "text": f"Do NOT use for {prohibited_use}",
            "modality": "PROHIBITION",
            "polarity": "NEGATIVE",
            "strength": "MUST",
            "subject": "skill usage",
            "action": f"use for {prohibited_use}",
            "condition": None,
            "context": "frontmatter routing constraint",
            "blacklist_candidates": [],
            "kg_node_type": "AntiPattern",
            "source_ref": {
                "document": document,
                "section": "frontmatter.description",
                "line_start": None,
                "line_end": None
            },
            "confidence": 0.95,
            "ambiguity_flag": False,
            "extraction_method": "frontmatter_pattern",
            "canonical_id": None,
            "duplicates": []
        })

    return assertions


# ─────────────────────────────────────────────────────────────────────
# UNIVERSAL EXTRACTOR
# ─────────────────────────────────────────────────────────────────────

class UniversalExtractor:
    """
    Single entry point for all source formats.
    Returns validated NAS documents ready for KG projection.
    """

    def __init__(self, llm_fn: Callable = None):
        """
        Initialize extractor.

        Args:
            llm_fn: Optional LLM function for Layer 3 classification.
        """
        self.classifier = Classifier(llm_fn=llm_fn)
        self.format_registry = FORMAT_REGISTRY

    def extract(self, path: str | Path) -> dict:
        """
        Main entry point. Accepts any supported file path.
        Returns validated NAS document or error dict.
        """
        path = Path(path)
        document = path.name

        # Detect format
        ext = path.suffix.lower()
        extractor_class = self.format_registry.get(ext)

        if not extractor_class:
            return self._error(
                "unsupported_format",
                f"Format {ext} not in FORMAT_REGISTRY. Supported: {list(self.format_registry.keys())}"
            )

        # Read content
        try:
            if ext in ('.md', '.txt', '.yaml', '.yml'):
                content = path.read_text(encoding='utf-8')
            else:
                content = path  # Binary formats pass path to extractor
        except Exception as e:
            return self._error("read_failed", str(e))

        # Extract content
        try:
            extractor = extractor_class(content, document)
            extracted = extractor.extract()
        except Exception as e:
            return self._error("extraction_failed", str(e))

        # Handle errors from extractor
        if extracted.get("error"):
            return self._error(extracted["error"], extracted.get("message", ""))

        # Handle direct imports (JSON-LD)
        if extracted.get("direct_import"):
            return self._wrap_direct_import(extracted, document)

        # Run full pipeline
        return self._run_pipeline(extracted, document, ext)

    def _run_pipeline(self, extracted: dict, document: str, ext: str) -> dict:
        """Run the full extraction pipeline."""
        assertions = []
        assertion_counter = [0]  # Mutable counter

        # 1. Frontmatter routing constraints (SKILL.md)
        frontmatter_prohibitions = extracted.get("prohibitions_in_frontmatter", [])
        if frontmatter_prohibitions:
            assertions.extend(
                extract_routing_prohibitions(frontmatter_prohibitions, document, assertion_counter)
            )

        # 2. Section-by-section extraction
        for section in extracted.get("sections", []):
            assertions.extend(
                section_to_assertions(section, document, self.classifier, assertion_counter)
            )

        # 3. Table extraction
        for table in extracted.get("tables", []):
            section_name = table.get("section", "table")
            assertions.extend(
                table_to_assertions(table, document, section_name, self.classifier, assertion_counter)
            )

        # 4. Canonicalization
        assertions = canonicalize_assertions(assertions)

        # 5. Build and validate NAS document
        char_count = len(extracted.get("raw_text", ""))
        section_count = len(extracted.get("sections", []))

        nas_doc = build_nas_document(
            assertions,
            document,
            source_format=ext.lstrip('.'),
            char_count=char_count,
            section_count=section_count,
            extraction_method="hybrid"
        )

        validation = validate_nas_document(nas_doc)

        if not validation["valid"]:
            nas_doc["validation_errors"] = validation["errors"]
        if validation["warnings"]:
            nas_doc["validation_warnings"] = validation["warnings"]

        nas_doc["validation"] = validation

        return nas_doc

    def _wrap_direct_import(self, extracted: dict, document: str) -> dict:
        """Wrap JSON-LD direct import in NAS document structure."""
        return {
            "$schema": "https://aether.dev/schemas/nas-document/1.0",
            "id": f"nas-{doc_to_slug(document)}-direct",
            "source": {
                "document": document,
                "format": "jsonld",
                "ingested_at": None,
                "char_count": 0,
                "section_count": 0
            },
            "extraction": {
                "method": "direct_import",
                "classifier_version": None,
                "total_assertions": 0,
                "by_modality": {},
                "by_confidence": {},
                "ambiguous_count": 0
            },
            "assertions": [],
            "direct_import": True,
            "nodes": extracted.get("nodes", []),
            "context": extracted.get("context", {}),
            "node_count": extracted.get("node_count", 0),
            "validation": {"valid": True, "errors": [], "warnings": []}
        }

    def _error(self, code: str, message: str) -> dict:
        """Return error dict."""
        return {
            "status": "error",
            "error_code": code,
            "message": message,
            "assertions": [],
            "validation": {"valid": False, "errors": [message], "warnings": []}
        }

    def get_stats(self) -> dict:
        """Return classification statistics."""
        return self.classifier.get_stats()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m stamper.pipeline <source_file>")
        sys.exit(1)

    path = sys.argv[1]
    extractor = UniversalExtractor()
    result = extractor.extract(path)

    if result.get("status") == "error":
        print(f"Error: {result['error_code']}: {result['message']}")
        sys.exit(1)

    print(f"NAS Document: {result['id']}")
    print(f"Source: {result['source']['document']}")
    print(f"Assertions: {result['extraction']['total_assertions']}")
    print(f"By modality: {result['extraction']['by_modality']}")
    print(f"Validation: {'PASS' if result['validation']['valid'] else 'FAIL'}")

    if result.get("direct_import"):
        print(f"Direct import: {result['node_count']} nodes")

    print(f"\nClassifier stats: {extractor.get_stats()}")
