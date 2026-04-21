"""
classifier.py - 3-Layer Negation & Modality Classifier
Part of the AETHER Stamper Agent pipeline.

Layer 1: Pattern Bank (deterministic, regex) - handles ~70%
Layer 2: Dependency Parser (structural) - handles ~20%
Layer 3: LLM Disambiguation (probabilistic) - handles ~10%
"""

import re
from typing import Optional, Callable
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────
# LAYER 1 — PATTERN BANK
# ─────────────────────────────────────────────────────────────────────

# Prohibition patterns (from spec)
PROHIBITION_PATTERNS = [
    # Hard prohibitions — confidence 1.0
    (r'\b(MUST\s+NOT|SHALL\s+NOT)\b', "PROHIBITION", "MUST", 1.0),
    (r'\b(NEVER|FORBIDDEN|PROHIBITED|DISALLOWED)\b', "PROHIBITION", "MUST", 1.0),
    (r'\b(DO\s+NOT|DON\'T|CANNOT|CAN\'T)\b', "PROHIBITION", "MUST", 0.95),
    (r'\b(IS\s+NOT\s+ALLOWED|ARE\s+NOT\s+ALLOWED)\b', "PROHIBITION", "MUST", 0.95),

    # Soft prohibitions — confidence 0.90
    (r'\b(SHOULD\s+NOT|SHOULDN\'T|AVOID|REFRAIN\s+FROM)\b', "PROHIBITION", "SHOULD", 0.90),
    (r'\b(NOT\s+RECOMMENDED|DISCOURAGED|INADVISABLE)\b', "PROHIBITION", "SHOULD", 0.88),

    # Failure mode signals — confidence 0.92
    (r'\b(BREAKS?\s+(IN|WHEN|ON)|FAILS?\s+(IN|WHEN|ON))\b', "PROHIBITION", "MUST", 0.92),
    (r'\b(NOT\s+SUPPORTED\s+IN|INCOMPATIBLE\s+WITH)\b', "PROHIBITION", "MUST", 0.92),
    (r'\b(CAUSES?\s+(ISSUES?|PROBLEMS?|ERRORS?|BUGS?))\b', "PROHIBITION", "SHOULD", 0.88),
]

# Obligation patterns (from spec)
OBLIGATION_PATTERNS = [
    # Hard obligations — confidence 1.0
    (r'\b(MUST(?!\s+NOT)|SHALL(?!\s+NOT))\b', "OBLIGATION", "MUST", 1.0),
    (r'\b(REQUIRED|MANDATORY|ALWAYS|NECESSARY)\b', "OBLIGATION", "MUST", 0.95),
    (r'\b(IS\s+REQUIRED|ARE\s+REQUIRED|MUST\s+BE\s+SET)\b', "OBLIGATION", "MUST", 0.95),

    # Soft obligations — confidence 0.88
    (r'\b(SHOULD(?!\s+NOT)|RECOMMENDED(?!\s+NOT))\b', "RECOMMENDATION", "SHOULD", 0.88),
    (r'\b(BEST\s+PRACTICE|PREFERRED|IDEALLY)\b', "RECOMMENDATION", "SHOULD", 0.85),
]

# Conditional patterns (from spec)
CONDITIONAL_PATTERNS = [
    (r'\bIF\b.+\bTHEN\b', "CONDITIONAL", "UNKNOWN", 0.95),
    (r'\bWHEN\b.+\b(MUST|SHALL|SHOULD|NEVER)\b', "CONDITIONAL", "UNKNOWN", 0.92),
    (r'\bUNLESS\b', "CONDITIONAL", "UNKNOWN", 0.90),
    (r'\bONLY\s+(WHEN|IF|FOR)\b', "CONDITIONAL", "UNKNOWN", 0.88),
    (r'\b(EXCEPT\s+WHEN|EXCEPT\s+FOR|EXCEPT\s+IN)\b', "CONDITIONAL", "UNKNOWN", 0.88),
]


def _match_patterns(text: str, patterns: list) -> Optional[tuple]:
    """Match text against pattern list. Returns (modality, strength, confidence) or None."""
    for pattern, modality, strength, confidence in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return (modality, strength, confidence)
    return None


def layer1_classify(text: str) -> Optional[dict]:
    """
    Layer 1: Pattern bank classification.
    Returns classification dict or None if no match.
    """
    # Priority order: PROHIBITION > OBLIGATION > CONDITIONAL

    # Check prohibitions first
    result = _match_patterns(text, PROHIBITION_PATTERNS)
    if result:
        return {
            "modality": result[0],
            "polarity": "NEGATIVE",
            "strength": result[1],
            "confidence": result[2],
            "layer": 1,
            "method": "pattern_bank"
        }

    # Check obligations
    result = _match_patterns(text, OBLIGATION_PATTERNS)
    if result:
        return {
            "modality": result[0],
            "polarity": "POSITIVE",
            "strength": result[1],
            "confidence": result[2],
            "layer": 1,
            "method": "pattern_bank"
        }

    # Check conditionals
    result = _match_patterns(text, CONDITIONAL_PATTERNS)
    if result:
        # Determine polarity from content
        has_negation = bool(re.search(r'\b(NOT|NEVER|DON\'T|CANNOT)\b', text, re.I))
        return {
            "modality": result[0],
            "polarity": "NEGATIVE" if has_negation else "POSITIVE",
            "strength": result[1],
            "confidence": result[2],
            "layer": 1,
            "method": "pattern_bank"
        }

    return None


# ─────────────────────────────────────────────────────────────────────
# LAYER 2 — STRUCTURAL ANALYSIS
# ─────────────────────────────────────────────────────────────────────

# Implicit prohibition patterns (no explicit modal keywords)
IMPLICIT_PROHIBITION = [
    (r'\b(breaks?|fails?)\s+(in|when|on|with)\b', 0.92),
    (r'\b(does|do)\s+not\s+(work|render|function)\b', 0.90),
    (r'\b(is|are)\s+not\s+supported\b', 0.92),
    (r'\b(causes?|leads?\s+to)\s+(issues?|problems?|errors?|bugs?|failures?)\b', 0.88),
    (r'\b(will|may)\s+(break|fail|crash)\b', 0.88),
]

# Implicit obligation patterns
IMPLICIT_OBLIGATION = [
    (r'^Always\s+', 0.92),  # "Always X" at sentence start
    (r'\b(critical|essential|crucial|vital)\s+for\b', 0.85),
    (r'\b(ensures?|guarantees?)\s+(that|proper|correct|valid)\b', 0.80),
    (r'\bfor\s+(consistent|reliable|proper)\s+results?\b', 0.78),
]


def layer2_classify(text: str) -> Optional[dict]:
    """
    Layer 2: Structural analysis classification.
    Handles implicit deontic intent without explicit modal keywords.
    """
    # Check implicit prohibitions
    for pattern, confidence in IMPLICIT_PROHIBITION:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "modality": "PROHIBITION",
                "polarity": "NEGATIVE",
                "strength": "MUST",
                "confidence": confidence,
                "layer": 2,
                "method": "structural_analysis"
            }

    # Check implicit obligations
    for pattern, confidence in IMPLICIT_OBLIGATION:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "modality": "OBLIGATION" if confidence >= 0.90 else "RECOMMENDATION",
                "polarity": "POSITIVE",
                "strength": "MUST" if confidence >= 0.90 else "SHOULD",
                "confidence": confidence,
                "layer": 2,
                "method": "structural_analysis"
            }

    # Negation scope resolution
    negation_result = _resolve_negation_scope(text)
    if negation_result:
        return negation_result

    return None


def _resolve_negation_scope(text: str) -> Optional[dict]:
    """
    Resolve negation scope to determine classification.
    "not recommended" -> PROHIBITION (soft)
    "not required when" -> CONDITIONAL
    "not all X" -> DESCRIPTIVE
    """
    text_lower = text.lower()

    # "not recommended/allowed/supported" -> PROHIBITION (soft)
    if re.search(r'\bnot\s+(recommended|advisable|advised)\b', text_lower):
        return {
            "modality": "PROHIBITION",
            "polarity": "NEGATIVE",
            "strength": "SHOULD",
            "confidence": 0.85,
            "layer": 2,
            "method": "negation_scope"
        }

    # "not allowed" -> PROHIBITION (hard)
    if re.search(r'\bnot\s+allowed\b', text_lower):
        return {
            "modality": "PROHIBITION",
            "polarity": "NEGATIVE",
            "strength": "MUST",
            "confidence": 0.92,
            "layer": 2,
            "method": "negation_scope"
        }

    # "not required when/if" -> CONDITIONAL
    if re.search(r'\bnot\s+required\s+(when|if|unless)\b', text_lower):
        return {
            "modality": "CONDITIONAL",
            "polarity": "NEGATIVE",
            "strength": "MUST",
            "confidence": 0.88,
            "layer": 2,
            "method": "negation_scope"
        }

    # "not all/every/necessarily" -> DESCRIPTIVE (quantifier negation)
    if re.search(r'\bnot\s+(all|every|necessarily)\b', text_lower):
        return {
            "modality": "DESCRIPTIVE",
            "polarity": "POSITIVE",
            "strength": "UNKNOWN",
            "confidence": 0.80,
            "layer": 2,
            "method": "negation_scope"
        }

    return None


# ─────────────────────────────────────────────────────────────────────
# LAYER 3 — LLM DISAMBIGUATION
# ─────────────────────────────────────────────────────────────────────

LAYER3_PROMPT_TEMPLATE = """Classify this sentence from a technical specification document.

Sentence: "{sentence}"

Choose exactly one classification:
1. PROHIBITION — the sentence forbids, warns against, or says something breaks/fails
2. OBLIGATION — the sentence requires, mandates, or says something must be done
3. RECOMMENDATION — the sentence suggests or advises without requiring
4. CONDITIONAL — the sentence states a rule that applies only under certain conditions
5. DESCRIPTIVE — the sentence describes without prescribing behavior

Respond with JSON only:
{{
  "classification": "PROHIBITION|OBLIGATION|RECOMMENDATION|CONDITIONAL|DESCRIPTIVE",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence explaining why"
}}"""


def layer3_classify(text: str, llm_fn: Callable) -> Optional[dict]:
    """
    Layer 3: LLM disambiguation for ambiguous sentences.
    Returns classification or None on failure.
    """
    import json

    prompt = LAYER3_PROMPT_TEMPLATE.format(sentence=text[:500])  # Limit sentence length

    try:
        result = llm_fn(prompt, max_tokens=200)

        # Handle dict or string response
        response_text = result.get("text", str(result)) if isinstance(result, dict) else str(result)

        # Parse JSON from response
        # Find JSON object in response
        json_match = re.search(r'\{[^{}]+\}', response_text, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group())
        classification = data.get("classification", "DESCRIPTIVE")
        confidence = float(data.get("confidence", 0.70))
        reasoning = data.get("reasoning", "")

        # Map classification to modality/polarity
        if classification == "PROHIBITION":
            polarity = "NEGATIVE"
            strength = "MUST"
        elif classification == "OBLIGATION":
            polarity = "POSITIVE"
            strength = "MUST"
        elif classification == "RECOMMENDATION":
            polarity = "POSITIVE"
            strength = "SHOULD"
        elif classification == "CONDITIONAL":
            # Check reasoning for polarity hint
            polarity = "NEGATIVE" if "not" in reasoning.lower() else "POSITIVE"
            strength = "UNKNOWN"
        else:  # DESCRIPTIVE
            polarity = "POSITIVE"
            strength = "UNKNOWN"

        return {
            "modality": classification,
            "polarity": polarity,
            "strength": strength,
            "confidence": confidence,
            "layer": 3,
            "method": "llm_disambiguation",
            "reasoning": reasoning
        }

    except (json.JSONDecodeError, KeyError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────
# BLACKLIST EXTRACTION
# ─────────────────────────────────────────────────────────────────────

PARENTHETICAL = re.compile(r'\(([^)]+)\)')
CODE_PATTERN = re.compile(r'`([^`]+)`')
QUOTED_PATTERN = re.compile(r'"([^"]+)"')


def extract_blacklist_candidates(text: str) -> list[str]:
    """
    Extract potential blacklist terms from text.
    Sources: parentheticals, code blocks, quoted strings.
    """
    candidates = []

    # Parenthetical terms
    for match in PARENTHETICAL.finditer(text):
        terms = [t.strip().lower() for t in match.group(1).split(',')]
        candidates.extend(terms)

    # Code terms (backticks)
    for match in CODE_PATTERN.finditer(text):
        term = match.group(1).strip().lower()
        if len(term) > 2:
            candidates.append(term)

    # Quoted terms
    for match in QUOTED_PATTERN.finditer(text):
        term = match.group(1).strip().lower()
        if len(term) > 2:
            candidates.append(term)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


# ─────────────────────────────────────────────────────────────────────
# NODE TYPE DERIVATION
# ─────────────────────────────────────────────────────────────────────

def derive_node_type(modality: str, polarity: str) -> str:
    """Map (modality, polarity) to KG node type."""
    mapping = {
        ("PROHIBITION", "NEGATIVE"): "AntiPattern",
        ("OBLIGATION", "POSITIVE"): "Rule",
        ("RECOMMENDATION", "POSITIVE"): "Rule",
        ("CONDITIONAL", "NEGATIVE"): "AntiPattern",
        ("CONDITIONAL", "POSITIVE"): "Rule",
        ("DESCRIPTIVE", "POSITIVE"): "Concept",
        ("DESCRIPTIVE", "NEGATIVE"): "Concept",
    }
    return mapping.get((modality, polarity), "Concept")


# ─────────────────────────────────────────────────────────────────────
# MAIN CLASSIFIER CLASS
# ─────────────────────────────────────────────────────────────────────

class Classifier:
    """
    Three-layer negation and modality classifier.

    Layer 1: Pattern bank (~70% of sentences)
    Layer 2: Structural analysis (~20%)
    Layer 3: LLM disambiguation (~10%)
    """

    def __init__(self, llm_fn: Callable = None):
        """
        Initialize classifier.

        Args:
            llm_fn: Optional LLM function for Layer 3.
                   If None, Layer 3 is skipped.
        """
        self.llm_fn = llm_fn
        self.stats = {
            "layer1_hits": 0,
            "layer2_hits": 0,
            "layer3_hits": 0,
            "unclassified": 0
        }

    def classify(
        self,
        text: str,
        document: str,
        section: str = None,
        assertion_id: str = None
    ) -> dict:
        """
        Classify a sentence through all three layers.

        Returns NAS assertion dict with:
        - modality, polarity, strength, confidence
        - kg_node_type, blacklist_candidates
        - layer (1, 2, or 3), method
        - ambiguity_flag if confidence < 0.70
        """
        # Layer 1: Pattern bank
        result = layer1_classify(text)
        if result:
            self.stats["layer1_hits"] += 1
            return self._build_assertion(text, result, document, section, assertion_id)

        # Layer 2: Structural analysis
        result = layer2_classify(text)
        if result:
            self.stats["layer2_hits"] += 1
            return self._build_assertion(text, result, document, section, assertion_id)

        # Layer 3: LLM disambiguation (if available)
        if self.llm_fn:
            result = layer3_classify(text, self.llm_fn)
            if result:
                self.stats["layer3_hits"] += 1
                return self._build_assertion(text, result, document, section, assertion_id)

        # No classification - return as DESCRIPTIVE
        self.stats["unclassified"] += 1
        return self._build_assertion(
            text,
            {
                "modality": "DESCRIPTIVE",
                "polarity": "POSITIVE",
                "strength": "UNKNOWN",
                "confidence": 0.50,
                "layer": 0,
                "method": "no_match"
            },
            document,
            section,
            assertion_id
        )

    def _build_assertion(
        self,
        text: str,
        result: dict,
        document: str,
        section: str,
        assertion_id: str
    ) -> dict:
        """Build NAS assertion from classification result."""
        modality = result["modality"]
        polarity = result["polarity"]
        confidence = result["confidence"]

        return {
            "id": assertion_id or f"assertion-{hash(text) % 100000:05d}",
            "text": text,
            "modality": modality,
            "polarity": polarity,
            "strength": result["strength"],
            "subject": None,
            "action": None,
            "condition": None,
            "context": section,
            "blacklist_candidates": extract_blacklist_candidates(text) if modality == "PROHIBITION" else [],
            "kg_node_type": derive_node_type(modality, polarity),
            "source_ref": {
                "document": document,
                "section": section,
                "line_start": None,
                "line_end": None
            },
            "confidence": confidence,
            "ambiguity_flag": confidence < 0.70,
            "extraction_method": f"classifier_{result['method']}",
            "layer": result.get("layer", 0),
            "canonical_id": None,
            "duplicates": []
        }

    def get_stats(self) -> dict:
        """Return classification statistics."""
        total = sum(self.stats.values())
        return {
            **self.stats,
            "total": total,
            "layer1_pct": round(self.stats["layer1_hits"] / total * 100, 1) if total else 0,
            "layer2_pct": round(self.stats["layer2_hits"] / total * 100, 1) if total else 0,
            "layer3_pct": round(self.stats["layer3_hits"] / total * 100, 1) if total else 0,
        }


if __name__ == "__main__":
    # Test Layer 1
    print("=== Layer 1 Tests ===")
    layer1_tests = [
        "MUST use Arial as default font",
        "MUST NOT use percentage widths",
        "NEVER insert unicode bullets",
        "SHOULD validate after generation",
        "Avoid using system fonts",
    ]

    classifier = Classifier()
    for test in layer1_tests:
        result = classifier.classify(test, "test.md")
        print(f"  [{result['modality']:12}] {result['strength']:6} conf={result['confidence']:.2f} | {test}")

    # Test Layer 2
    print("\n=== Layer 2 Tests ===")
    layer2_tests = [
        "WidthType.PERCENTAGE breaks in Google Docs",
        "This approach is not supported in Safari",
        "Using Inter fails to render correctly",
        "A consistent font ensures readability",
    ]

    for test in layer2_tests:
        result = classifier.classify(test, "test.md")
        print(f"  [{result['modality']:12}] {result['strength']:6} conf={result['confidence']:.2f} | {test}")

    print(f"\n=== Stats ===")
    print(classifier.get_stats())
