"""
KG - Knowledge Graph loader for Aether capsules.
JSON-LD based with core/acquired zone separation.
"""

import json
from pathlib import Path
from datetime import datetime

EMPTY_KG = {
    "@context": {"rdfs": "http://www.w3.org/2000/01/rdf-schema#", "aether": "http://aether.dev/ontology#"},
    "@graph": [],
}


def load_kg(path: str | Path) -> dict:
    """Load kg.jsonld. Returns empty graph if missing."""
    path = Path(path)
    if not path.exists():
        return {"@context": EMPTY_KG["@context"].copy(), "@graph": []}

    with open(path, "r", encoding="utf-8") as f:
        kg = json.load(f)

    # Normalize to @graph format
    if "@graph" not in kg and "@id" in kg:
        kg = {"@context": kg.get("@context", EMPTY_KG["@context"]), "@graph": [kg]}
    elif "@graph" not in kg:
        kg["@graph"] = []
    return kg


def get_nodes(kg: dict) -> list[dict]:
    """Extract all nodes from @graph."""
    if "@graph" in kg:
        return kg["@graph"]
    return [kg] if "@id" in kg else []


def query_nodes(kg: dict, entities: list[str]) -> list[dict]:
    """Find nodes matching any entity name (case-insensitive)."""
    if not entities:
        return []

    entities_lower = [e.lower() for e in entities]
    matches = []

    for node in get_nodes(kg):
        if _node_matches(node, entities_lower):
            matches.append(node)
    return matches


def _node_matches(node: dict, entities_lower: list[str]) -> bool:
    """Check if node matches any entity."""
    # Check @id and common label fields
    for key in ["@id", "rdfs:label", "name", "label", "title"]:
        val = node.get(key, "")
        if isinstance(val, str) and any(e in val.lower() for e in entities_lower):
            return True
    # Search all string values
    return _search_values(node, entities_lower)


def _search_values(obj, entities_lower: list[str]) -> bool:
    """Recursively search for entity matches in string values."""
    if isinstance(obj, str):
        return any(e in obj.lower() for e in entities_lower)
    if isinstance(obj, dict):
        return any(_search_values(v, entities_lower) for k, v in obj.items() if not k.startswith("@"))
    if isinstance(obj, list):
        return any(_search_values(item, entities_lower) for item in obj)
    return False


def add_acquired(kg: dict, triple: dict) -> dict:
    """
    Add acquired knowledge with provenance metadata.
    Triple: {subject, predicate, object, confidence, aec_trigger}
    """
    nodes = kg.setdefault("@graph", [])
    subject = triple.get("subject", "unknown")
    node_id = f"aether:acquired/{subject.replace(' ', '_').lower()}"

    # Find or create node
    existing = next((n for n in nodes if n.get("@id") == node_id), None)

    if existing:
        existing[triple["predicate"]] = triple["object"]
        existing["aether:updated"] = datetime.now().isoformat()
    else:
        nodes.append({
            "@id": node_id,
            "rdfs:label": subject,
            triple["predicate"]: triple["object"],
            "aether:origin": "acquired",
            "aether:confidence": triple.get("confidence", 0.5),
            "aether:acquired_date": datetime.now().isoformat(),
            "aether:aec_trigger": triple.get("aec_trigger", "unknown"),
        })
    return kg


def get_core_nodes(kg: dict) -> list[dict]:
    """Return nodes with origin: 'core' or no origin (original knowledge)."""
    return [n for n in get_nodes(kg) if n.get("aether:origin", "core") == "core"]


def get_acquired_nodes(kg: dict) -> list[dict]:
    """Return nodes with origin: 'acquired' (learned through AEC)."""
    return [n for n in get_nodes(kg) if n.get("aether:origin") == "acquired"]


def save_kg(kg: dict, path: str | Path) -> None:
    """Write KG to file with pretty printing."""
    with open(Path(path), "w", encoding="utf-8") as f:
        json.dump(kg, f, indent=2, ensure_ascii=False)


def stats(kg: dict) -> dict:
    """Return KG statistics."""
    nodes = get_nodes(kg)
    return {
        "total": len(nodes),
        "core": len([n for n in nodes if n.get("aether:origin", "core") == "core"]),
        "acquired": len([n for n in nodes if n.get("aether:origin") == "acquired"]),
    }


if __name__ == "__main__":
    kg = load_kg("examples/test_capsule/kg.jsonld")
    print(f"Loaded: {stats(kg)}")

    matches = query_nodes(kg, ["Aether", "Pipeline"])
    print(f"Query matches: {[m.get('rdfs:label', m.get('@id')) for m in matches]}")

    kg = add_acquired(kg, {
        "subject": "Test Fact",
        "predicate": "rdfs:comment",
        "object": "Learned via AEC",
        "confidence": 0.85,
        "aec_trigger": "test",
    })
    print(f"After acquire: {stats(kg)}")
    print(f"Acquired: {[n['rdfs:label'] for n in get_acquired_nodes(kg)]}")
