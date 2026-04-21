"""
dsl_parser.py - Deterministic DSL -> NAS assertion parser
Part of the AETHER Stamper Agent pipeline.

Confidence is always 1.0 for deterministic parse.
All output assertions use extraction_method: "deterministic_dsl".
"""

import re
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────
# KEYWORD PATTERNS
# ─────────────────────────────────────────────────────────────────────

PROHIBITION_HARD = re.compile(
    r'\b(MUST\s+NOT|SHALL\s+NOT|NEVER|PROHIBITED|FORBIDDEN|DO\s+NOT|IS\s+NOT\s+ALLOWED|ARE\s+NOT\s+ALLOWED|breaks?\s+in|not\s+supported\s+in)\b',
    re.IGNORECASE
)

PROHIBITION_SOFT = re.compile(
    r'\b(SHOULD\s+NOT|AVOID|NOT\s+RECOMMENDED|DISCOURAGED)\b',
    re.IGNORECASE
)

OBLIGATION_HARD = re.compile(
    r'\b(MUST(?!\s+NOT)|SHALL(?!\s+NOT)|REQUIRED|ALWAYS|MANDATORY)\b',
    re.IGNORECASE
)

OBLIGATION_SOFT = re.compile(
    r'\b(SHOULD(?!\s+NOT)|RECOMMENDED(?!\s+NOT)|BEST\s+PRACTICE)\b',
    re.IGNORECASE
)

OPTIONAL = re.compile(
    r'\b(MAY|CAN|OPTIONAL|ALLOWED)\b',
    re.IGNORECASE
)

CONDITIONAL = re.compile(
    r'\b(IF|WHEN|UNLESS|EXCEPT\s+WHEN|ONLY\s+WHEN)\b',
    re.IGNORECASE
)

PARENTHETICAL = re.compile(r'\(([^)]+)\)')


# ─────────────────────────────────────────────────────────────────────
# DETECTION
# ─────────────────────────────────────────────────────────────────────

def is_dsl_document(text: str) -> bool:
    """
    Returns True if >= 30% of sentences match DSL patterns.
    """
    sentences = [s.strip() for s in re.split(r'[.!\n]+', text) if s.strip()]
    if not sentences:
        return False
    dsl_count = sum(
        1 for s in sentences
        if any(p.search(s) for p in [
            PROHIBITION_HARD, PROHIBITION_SOFT,
            OBLIGATION_HARD, OBLIGATION_SOFT,
            OPTIONAL, CONDITIONAL
        ])
    )
    return (dsl_count / len(sentences)) >= 0.30


def is_dsl_sentence(text: str) -> bool:
    """Check if a single sentence matches DSL patterns."""
    return any(p.search(text) for p in [
        PROHIBITION_HARD, PROHIBITION_SOFT,
        OBLIGATION_HARD, OBLIGATION_SOFT,
        OPTIONAL, CONDITIONAL
    ])


# ─────────────────────────────────────────────────────────────────────
# BLACKLIST EXTRACTION
# ─────────────────────────────────────────────────────────────────────

def extract_blacklist_candidates(text: str) -> list[str]:
    """
    Extract parenthetical terms as blacklist candidates.
    "Use Inter for body text (Inter, Roboto, Arial)" -> ["inter", "roboto", "arial"]
    """
    candidates = []
    for match in PARENTHETICAL.finditer(text):
        terms = [t.strip().lower() for t in match.group(1).split(',')]
        candidates.extend(terms)
    return candidates


# ─────────────────────────────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────

def classify_sentence(text: str) -> dict:
    """
    Classify a single sentence. Returns modality, polarity, strength.
    Priority: PROHIBITION_HARD > PROHIBITION_SOFT > OBLIGATION_HARD
             > OBLIGATION_SOFT > OPTIONAL > CONDITIONAL > DESCRIPTIVE
    """
    if PROHIBITION_HARD.search(text):
        return {"modality": "PROHIBITION", "polarity": "NEGATIVE", "strength": "MUST"}
    if PROHIBITION_SOFT.search(text):
        return {"modality": "PROHIBITION", "polarity": "NEGATIVE", "strength": "SHOULD"}
    if OBLIGATION_HARD.search(text):
        return {"modality": "OBLIGATION", "polarity": "POSITIVE", "strength": "MUST"}
    if OBLIGATION_SOFT.search(text):
        return {"modality": "RECOMMENDATION", "polarity": "POSITIVE", "strength": "SHOULD"}
    if OPTIONAL.search(text):
        return {"modality": "RECOMMENDATION", "polarity": "POSITIVE", "strength": "MAY"}
    if CONDITIONAL.search(text):
        # Determine polarity from content
        if PROHIBITION_HARD.search(text) or "NOT" in text.upper():
            return {"modality": "CONDITIONAL", "polarity": "NEGATIVE", "strength": "MUST"}
        return {"modality": "CONDITIONAL", "polarity": "POSITIVE", "strength": "UNKNOWN"}
    return {"modality": "DESCRIPTIVE", "polarity": "POSITIVE", "strength": "UNKNOWN"}


# ─────────────────────────────────────────────────────────────────────
# CONDITION EXTRACTION
# ─────────────────────────────────────────────────────────────────────

def extract_condition(text: str) -> Optional[str]:
    """
    Extract conditional clause if present.
    "MUST NOT use X when Y" -> "when Y"
    "IF X THEN MUST Y" -> "X"
    """
    # IF ... THEN pattern
    if_then = re.match(r'IF\s+(.+?)\s+THEN\s+', text, re.IGNORECASE)
    if if_then:
        return if_then.group(1).strip()
    # WHEN pattern
    when = re.search(r'\bWHEN\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if when:
        return f"when {when.group(1).strip()}"
    # UNLESS pattern
    unless = re.search(r'\bUNLESS\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if unless:
        return f"unless {unless.group(1).strip()}"
    return None


# ─────────────────────────────────────────────────────────────────────
# NODE TYPE DERIVATION
# ─────────────────────────────────────────────────────────────────────

MODALITY_TO_NODE_TYPE = {
    ("PROHIBITION", "NEGATIVE"): "AntiPattern",
    ("OBLIGATION", "POSITIVE"): "Rule",
    ("RECOMMENDATION", "POSITIVE"): "Rule",
    ("CONDITIONAL", "NEGATIVE"): "AntiPattern",
    ("CONDITIONAL", "POSITIVE"): "Rule",
    ("DESCRIPTIVE", "POSITIVE"): "Concept",
}


def derive_node_type(modality: str, polarity: str) -> str:
    return MODALITY_TO_NODE_TYPE.get((modality, polarity), "Concept")


# ─────────────────────────────────────────────────────────────────────
# ASSERTION ID GENERATION
# ─────────────────────────────────────────────────────────────────────

def make_assertion_id(doc_slug: str, sequence: int) -> str:
    return f"assertion-{doc_slug}-{sequence:03d}"


def doc_to_slug(document: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', document.lower()).strip('-')


# ─────────────────────────────────────────────────────────────────────
# MAIN PARSER
# ─────────────────────────────────────────────────────────────────────

def parse_dsl(
    text: str,
    document: str,
    section: str = None
) -> list[dict]:
    """
    Parse DSL text into NAS assertions.
    Returns list of assertion dicts conforming to nas-schema-v1.0.

    All assertions have:
    - confidence: 1.0
    - extraction_method: "deterministic_dsl"
    - ambiguity_flag: false
    """
    assertions = []
    doc_slug = doc_to_slug(document)
    lines = text.split('\n')

    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip comment lines
        if line.startswith('#') or line.startswith('//') or line.startswith('--'):
            continue

        # Classify
        classification = classify_sentence(line)
        modality = classification["modality"]

        # Skip pure descriptive lines in DSL mode unless they're definitions
        if modality == "DESCRIPTIVE" and '=' not in line and ':=' not in line:
            continue

        # Extract components
        blacklist = extract_blacklist_candidates(line)
        condition = extract_condition(line)
        node_type = derive_node_type(modality, classification["polarity"])

        # Build assertion
        assertion = {
            "id": make_assertion_id(doc_slug, len(assertions) + 1),
            "text": line,
            "modality": modality,
            "polarity": classification["polarity"],
            "strength": classification["strength"],
            "subject": None,       # NLP subject extraction - Phase 4
            "action": None,        # NLP action extraction - Phase 4
            "condition": condition,
            "context": section,
            "blacklist_candidates": blacklist,
            "kg_node_type": node_type,
            "source_ref": {
                "document": document,
                "section": section,
                "line_start": i + 1,
                "line_end": i + 1
            },
            "confidence": 1.0,
            "ambiguity_flag": False,
            "extraction_method": "deterministic_dsl",
            "canonical_id": None,
            "duplicates": []
        }

        assertions.append(assertion)

    return assertions


# ─────────────────────────────────────────────────────────────────────
# NAS DOCUMENT WRAPPER
# ─────────────────────────────────────────────────────────────────────

def build_nas_document(assertions: list[dict], document: str) -> dict:
    """Wrap assertions in NAS document structure."""
    by_modality = {}
    for a in assertions:
        m = a["modality"]
        by_modality[m] = by_modality.get(m, 0) + 1

    return {
        "$schema": "https://aether.dev/schemas/nas-document/1.0",
        "id": f"nas-{doc_to_slug(document)}-{datetime.now().strftime('%Y%m%d')}",
        "source": {
            "document": document,
            "format": "dsl",
            "ingested_at": datetime.now().isoformat(),
            "char_count": 0,
            "section_count": 0
        },
        "extraction": {
            "method": "deterministic_dsl",
            "classifier_version": "1.0",
            "total_assertions": len(assertions),
            "by_modality": by_modality,
            "by_confidence": {
                "high_0.90_plus": len(assertions),
                "medium_0.70_to_0.89": 0,
                "low_below_0.70": 0
            },
            "ambiguous_count": 0
        },
        "assertions": assertions
    }


if __name__ == "__main__":
    # Quick test
    test_dsl = """
    MUST use Arial as the default font.
    MUST NOT use unicode bullet characters (•, ◦, ▪).
    SHOULD validate the document after creation.
    NEVER insert percentage table widths (WidthType.PERCENTAGE).
    """

    assertions = parse_dsl(test_dsl, "test-rules.dsl")
    print(f"Parsed {len(assertions)} assertions:")
    for a in assertions:
        print(f"  [{a['modality']:12}] {a['strength']:6} -> {a['kg_node_type']:11} | {a['text'][:50]}...")
        if a['blacklist_candidates']:
            print(f"                    blacklist: {a['blacklist_candidates']}")
