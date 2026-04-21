"""
nas.py - Normalized Assertion Schema document builder and validator
Part of the AETHER Stamper Agent pipeline.

NAS documents are the intermediate representation between source
extraction and KG projection.
"""

import re
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# NAS SCHEMA VERSION
# ─────────────────────────────────────────────────────────────────────

NAS_SCHEMA_VERSION = "1.0"
NAS_SCHEMA_URL = f"https://aether.dev/schemas/nas-document/{NAS_SCHEMA_VERSION}"


# ─────────────────────────────────────────────────────────────────────
# SENTENCE SPLITTING
# ─────────────────────────────────────────────────────────────────────

ABBREVIATIONS = {"Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Inc.", "Jr.", "Sr.",
                 "vs.", "etc.", "e.g.", "i.e.", "approx.", "est.", "vol."}


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences, preserving abbreviations.
    Returns list of non-empty sentences with at least 10 chars.
    """
    if not text or not text.strip():
        return []

    # Normalize whitespace
    text = " ".join(text.split())

    # Protect abbreviations
    for abbr in ABBREVIATIONS:
        text = text.replace(abbr, abbr.replace(".", "<<DOT>>"))

    # Split on sentence endings followed by space and capital
    parts = re.split(r'[.!?]+\s+(?=[A-Z])', text)

    sentences = []
    for part in parts:
        part = part.replace("<<DOT>>", ".").strip().rstrip(".!?").strip()
        if len(part) >= 10:
            sentences.append(part)

    return sentences


# ─────────────────────────────────────────────────────────────────────
# ASSERTION ID GENERATION
# ─────────────────────────────────────────────────────────────────────

def make_assertion_id(doc_slug: str, sequence: int) -> str:
    return f"assertion-{doc_slug}-{sequence:03d}"


def doc_to_slug(document: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', document.lower()).strip('-')


# ─────────────────────────────────────────────────────────────────────
# NAS DOCUMENT BUILDER
# ─────────────────────────────────────────────────────────────────────

def build_nas_document(
    assertions: list[dict],
    document: str,
    source_format: str = "unknown",
    char_count: int = 0,
    section_count: int = 0,
    extraction_method: str = "hybrid"
) -> dict:
    """
    Build a complete NAS document from a list of assertions.

    Computes statistics:
    - by_modality: count per modality type
    - by_confidence: high (>=0.90), medium (0.70-0.89), low (<0.70)
    - ambiguous_count: assertions with ambiguity_flag
    """
    # Compute by_modality counts
    by_modality = {}
    for a in assertions:
        m = a.get("modality", "UNKNOWN")
        by_modality[m] = by_modality.get(m, 0) + 1

    # Compute by_confidence counts
    high = 0
    medium = 0
    low = 0
    ambiguous = 0

    for a in assertions:
        conf = a.get("confidence", 0)
        if conf >= 0.90:
            high += 1
        elif conf >= 0.70:
            medium += 1
        else:
            low += 1
        if a.get("ambiguity_flag", False):
            ambiguous += 1

    return {
        "$schema": NAS_SCHEMA_URL,
        "id": f"nas-{doc_to_slug(document)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "source": {
            "document": document,
            "format": source_format,
            "ingested_at": datetime.now().isoformat(),
            "char_count": char_count,
            "section_count": section_count
        },
        "extraction": {
            "method": extraction_method,
            "classifier_version": NAS_SCHEMA_VERSION,
            "total_assertions": len(assertions),
            "by_modality": by_modality,
            "by_confidence": {
                "high_0.90_plus": high,
                "medium_0.70_to_0.89": medium,
                "low_below_0.70": low
            },
            "ambiguous_count": ambiguous
        },
        "assertions": assertions
    }


# ─────────────────────────────────────────────────────────────────────
# NAS DOCUMENT VALIDATION
# ─────────────────────────────────────────────────────────────────────

VALID_MODALITIES = {"PROHIBITION", "OBLIGATION", "RECOMMENDATION", "CONDITIONAL", "DESCRIPTIVE"}
VALID_POLARITIES = {"POSITIVE", "NEGATIVE"}
VALID_STRENGTHS = {"MUST", "SHOULD", "MAY", "UNKNOWN"}


def validate_nas_document(nas_doc: dict) -> dict:
    """
    Validate NAS document against schema rules.

    Returns:
        {
            "valid": bool,
            "errors": list[str],     # Fatal issues
            "warnings": list[str],   # Non-fatal issues
            "assertion_count": int,
            "prohibition_count": int,
            "obligation_count": int
        }
    """
    errors = []
    warnings = []
    assertions = nas_doc.get("assertions", [])

    # Top-level structure
    if not nas_doc.get("$schema"):
        warnings.append("Missing $schema field")
    if not nas_doc.get("id"):
        errors.append("Missing document id")
    if not nas_doc.get("source", {}).get("document"):
        errors.append("Missing source.document")

    # Assertion validation
    for i, a in enumerate(assertions):
        aid = a.get("id", f"assertion-{i}")

        # Required fields
        if not a.get("id"):
            errors.append(f"Assertion {i} missing id")
        if not a.get("text"):
            errors.append(f"Assertion {aid} missing text")
        if not a.get("modality"):
            errors.append(f"Assertion {aid} missing modality")
        if not a.get("source_ref", {}).get("document"):
            errors.append(f"Assertion {aid} missing source_ref.document")

        # Modality validation
        modality = a.get("modality")
        if modality and modality not in VALID_MODALITIES:
            errors.append(f"Assertion {aid} has invalid modality: {modality}")

        # Polarity validation
        polarity = a.get("polarity")
        if polarity and polarity not in VALID_POLARITIES:
            errors.append(f"Assertion {aid} has invalid polarity: {polarity}")

        # Strength validation
        strength = a.get("strength")
        if strength and strength not in VALID_STRENGTHS:
            warnings.append(f"Assertion {aid} has non-standard strength: {strength}")

        # Confidence validation
        confidence = a.get("confidence", 0)
        if confidence < 0 or confidence > 1:
            errors.append(f"Assertion {aid} has invalid confidence: {confidence}")
        if confidence < 0.70:
            warnings.append(f"Assertion {aid} below confidence threshold: {confidence}")

        # Polarity integrity
        if modality == "PROHIBITION" and polarity == "POSITIVE":
            errors.append(f"Assertion {aid}: PROHIBITION cannot have POSITIVE polarity")
        if modality == "OBLIGATION" and polarity == "NEGATIVE":
            errors.append(f"Assertion {aid}: OBLIGATION cannot have NEGATIVE polarity")

    # Coverage checks
    prohibition_count = sum(1 for a in assertions if a.get("modality") == "PROHIBITION")
    obligation_count = sum(1 for a in assertions if a.get("modality") == "OBLIGATION")

    if prohibition_count == 0 and obligation_count == 0:
        warnings.append("No normative assertions found — source may lack explicit rules")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "assertion_count": len(assertions),
        "prohibition_count": prohibition_count,
        "obligation_count": obligation_count
    }


# ─────────────────────────────────────────────────────────────────────
# CANONICALIZATION
# ─────────────────────────────────────────────────────────────────────

def normalize_subject(text: str) -> str:
    """Normalize subject text for duplicate detection."""
    # Lowercase, remove punctuation, collapse whitespace
    norm = re.sub(r'[^\w\s]', '', text.lower())
    norm = ' '.join(norm.split())
    return norm


def text_similarity(a: str, b: str) -> float:
    """
    Simple word overlap similarity.
    Returns value 0.0 to 1.0.
    """
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def canonicalize_assertions(assertions: list[dict]) -> list[dict]:
    """
    Merge semantically equivalent assertions.

    Strategy:
    1. Group by (modality, normalized_subject)
    2. Within group, check action similarity > 0.85
    3. Merge into highest confidence canonical
    4. Combine blacklist_candidates from all duplicates
    """
    if not assertions:
        return []

    # Group by modality
    by_modality = {}
    for a in assertions:
        m = a.get("modality", "UNKNOWN")
        by_modality.setdefault(m, []).append(a)

    canonical = []

    for modality, group in by_modality.items():
        # Find similar pairs within modality group
        merged_ids = set()

        for i, a in enumerate(group):
            if a["id"] in merged_ids:
                continue

            # Find duplicates of this assertion
            duplicates = []
            for j, b in enumerate(group):
                if i != j and b["id"] not in merged_ids:
                    # Check text similarity
                    sim = text_similarity(a.get("text", ""), b.get("text", ""))
                    if sim >= 0.85:
                        duplicates.append(b)
                        merged_ids.add(b["id"])

            # Merge if duplicates found
            if duplicates:
                # Merge blacklist candidates
                all_blacklist = a.get("blacklist_candidates", []).copy()
                dup_ids = []
                for dup in duplicates:
                    all_blacklist.extend(dup.get("blacklist_candidates", []))
                    dup_ids.append(dup["id"])
                    dup["canonical_id"] = a["id"]
                    canonical.append(dup)  # Include dup with canonical_id set

                a["blacklist_candidates"] = list(set(all_blacklist))
                a["duplicates"] = dup_ids

            canonical.append(a)

    return canonical


if __name__ == "__main__":
    # Test split_sentences
    text = "Dr. Smith recommends this. You MUST follow it. This is good."
    sentences = split_sentences(text)
    print(f"Sentences: {sentences}")

    # Test NAS document building
    test_assertions = [
        {
            "id": "assertion-test-001",
            "text": "MUST use Arial font",
            "modality": "OBLIGATION",
            "polarity": "POSITIVE",
            "strength": "MUST",
            "confidence": 0.95,
            "source_ref": {"document": "test.md"},
            "kg_node_type": "Rule",
            "blacklist_candidates": [],
            "ambiguity_flag": False,
        },
        {
            "id": "assertion-test-002",
            "text": "NEVER use percentage widths",
            "modality": "PROHIBITION",
            "polarity": "NEGATIVE",
            "strength": "MUST",
            "confidence": 1.0,
            "source_ref": {"document": "test.md"},
            "kg_node_type": "AntiPattern",
            "blacklist_candidates": ["percentage"],
            "ambiguity_flag": False,
        },
    ]

    nas_doc = build_nas_document(test_assertions, "test.md")
    print(f"\nNAS Document ID: {nas_doc['id']}")
    print(f"Assertions: {nas_doc['extraction']['total_assertions']}")
    print(f"By modality: {nas_doc['extraction']['by_modality']}")

    validation = validate_nas_document(nas_doc)
    print(f"\nValidation: {'PASS' if validation['valid'] else 'FAIL'}")
    if validation['errors']:
        print(f"Errors: {validation['errors']}")
    if validation['warnings']:
        print(f"Warnings: {validation['warnings']}")
