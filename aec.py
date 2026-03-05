"""
AEC - Aether Entailment Check
Deterministic verification gate for response validation against KG subgraph.
"""

import re
import json

DEFAULT_THRESHOLD = 0.8


def split_statements(response: str) -> list[str]:
    """Split response into sentences. Simple regex, no NLP."""
    if not response or not response.strip():
        return []

    text = " ".join(response.split())

    # Protect abbreviations
    for abbr in ["Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Inc.", "Jr.", "Sr.", "vs.", "etc.", "e.g.", "i.e."]:
        text = text.replace(abbr, abbr.replace(".", "<<DOT>>"))

    # Split on sentence endings followed by capital letter
    parts = re.split(r'[.!?]+\s+(?=[A-Z])', text)

    statements = []
    for part in parts:
        part = part.replace("<<DOT>>", ".").strip().rstrip(".!?").strip()
        if len(part) > 10:
            statements.append(part)
    return statements


def _extract_values(text: str) -> list[tuple[str, any, str]]:
    """Extract verifiable values: (original, normalized, type)."""
    values = []

    # Numbers (integers and decimals)
    for m in re.finditer(r'\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b', text):
        try:
            values.append((m.group(1), float(m.group(1).replace(",", "")), "number"))
        except ValueError:
            pass

    # Percentages
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:%|percent|pct)\b', text, re.I):
        try:
            values.append((m.group(0), float(m.group(1)), "percentage"))
        except ValueError:
            pass

    # Years (1700-2099)
    for m in re.finditer(r'\b(1[7-9]\d{2}|20\d{2})\b', text):
        values.append((m.group(0), m.group(0), "date"))

    # Full dates: Month Day, Year
    months = "January|February|March|April|May|June|July|August|September|October|November|December"
    for m in re.finditer(rf'({months})\s+(\d{{1,2}}),?\s+(1[7-9]\d{{2}}|20\d{{2}})', text):
        month_map = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                     "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
        month_num = month_map[m.group(1).lower()]
        normalized = f"{m.group(3)}-{month_num:02d}-{int(m.group(2)):02d}"
        values.append((m.group(0), normalized, "date"))

    # Capitalized names (skip common words)
    skip = {"The", "This", "That", "These", "Those", "It", "He", "She", "They", "We", "You", "I"}
    for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text):
        name = m.group(1)
        if name not in skip:
            values.append((name, name, "name"))

    return values


def _flatten_kg(kg_nodes: list[dict]) -> dict[str, list]:
    """Flatten KG nodes into {key: [values]} for searching."""
    result = {}

    def extract(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.startswith("@"):
                    if k == "@id":
                        result.setdefault("id", []).append(str(v))
                else:
                    extract(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for item in obj:
                extract(item, prefix)
        else:
            result.setdefault(prefix, []).append(obj)

    for node in kg_nodes:
        extract(node)
    return result


def _match_in_kg(value, value_type: str, kg_flat: dict, tolerance: float = 0.01) -> tuple[bool, str | None]:
    """Check if value exists in flattened KG. Returns (matched, key)."""
    for key, kg_vals in kg_flat.items():
        for kv in kg_vals:
            # String match (case-insensitive, partial for names)
            if isinstance(value, str) and isinstance(kv, str):
                if value.lower() == kv.lower() or value.lower() in kv.lower() or kv.lower() in value.lower():
                    return True, key

            # Numeric match with tolerance
            if isinstance(value, (int, float)):
                kv_num = kv
                if isinstance(kv, str):
                    try:
                        kv_num = float(kv.replace(",", ""))
                    except (ValueError, AttributeError):
                        continue
                if isinstance(kv_num, (int, float)):
                    if abs(value - kv_num) <= abs(kv_num * tolerance) + 0.001:
                        return True, key

    return False, None


def deterministic_gate(statement: str, kg_nodes: list[dict]) -> dict:
    """
    Deterministic verification: extract values from statement, match against KG.
    Returns {matched: bool, entity: str|None, method: str, values_found: int}.
    """
    if not statement or not kg_nodes:
        return {"matched": False, "entity": None, "method": "no_input", "values_found": 0}

    values = _extract_values(statement)
    if not values:
        return {"matched": False, "entity": None, "method": "no_values", "values_found": 0}

    kg_flat = _flatten_kg(kg_nodes)
    matches = []

    for original, normalized, vtype in values:
        matched, key = _match_in_kg(normalized, vtype, kg_flat)
        if matched:
            matches.append((vtype, original, key))

    if matches:
        return {
            "matched": True,
            "entity": matches[0][1],
            "method": f"deterministic_{matches[0][0]}",
            "values_found": len(values),
            "matches": len(matches),
        }
    return {
        "matched": False,
        "entity": None,
        "method": "deterministic_unmatched",
        "values_found": len(values),
        "matches": 0,
    }


def verify(response: str, kg_nodes: list[dict], threshold: float = DEFAULT_THRESHOLD) -> dict:
    """
    Verify response against KG subgraph.
    Returns {score, threshold, passed, total_statements, grounded_statements, statements, gaps}.
    """
    statements = split_statements(response)

    if not statements:
        return {
            "score": 0.0, "threshold": threshold, "passed": False,
            "total_statements": 0, "grounded_statements": 0,
            "statements": [], "gaps": [{"text": response[:100], "reason": "no_statements"}],
        }

    results, gaps = [], []
    grounded = 0

    for stmt in statements:
        gate = deterministic_gate(stmt, kg_nodes)
        results.append({"text": stmt, "grounded": gate["matched"], "method": gate["method"]})
        if gate["matched"]:
            grounded += 1
        elif gate.get("values_found", 0) > 0:
            gaps.append({"text": stmt, "reason": "values_not_in_kg"})

    score = grounded / len(statements)
    return {
        "score": round(score, 3),
        "threshold": threshold,
        "passed": score >= threshold,
        "total_statements": len(statements),
        "grounded_statements": grounded,
        "statements": results,
        "gaps": gaps,
    }


if __name__ == "__main__":
    test_response = """
    Thomas Jefferson was born on April 13, 1743 in Virginia.
    He served as the 3rd President of the United States.
    Jefferson authored the Declaration of Independence in 1776.
    """
    test_kg = [
        {"@id": "person:jefferson", "rdfs:label": "Thomas Jefferson", "birth_year": 1743, "birth_date": "1743-04-13", "role": "3rd President"},
        {"@id": "doc:declaration", "rdfs:label": "Declaration of Independence", "year": 1776, "author": "Thomas Jefferson"},
    ]

    result = verify(test_response, test_kg)
    print(f"Score: {result['score']} (threshold: {result['threshold']})")
    print(f"Passed: {result['passed']}")
    print(f"Grounded: {result['grounded_statements']}/{result['total_statements']}")
    for s in result["statements"]:
        print(f"  [{'OK' if s['grounded'] else 'FAIL'}] {s['text'][:60]}...")
