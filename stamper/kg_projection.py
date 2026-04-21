"""
kg_projection.py - NAS to Knowledge Graph Projection
Part of the AETHER Stamper Agent pipeline.

Converts validated NAS assertions into JSON-LD KG nodes.
"""

import re
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# KG CONTEXT
# ─────────────────────────────────────────────────────────────────────

DEFAULT_CONTEXT = {
    "@vocab": "https://aether.dev/kg#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "aether": "https://aether.dev/kg#",
    "skill": "https://aether.dev/skill#",
    "requires": {
        "@id": "aether:requires",
        "@type": "@id"
    },
    "teaches": {
        "@id": "aether:teaches",
        "@type": "@id"
    }
}


# ─────────────────────────────────────────────────────────────────────
# NODE TYPE MAPPING
# ─────────────────────────────────────────────────────────────────────

NODE_TYPE_PREFIXES = {
    "Rule": "rule:",
    "AntiPattern": "antipattern:",
    "Technique": "technique:",
    "Concept": "concept:",
    "Tool": "tool:",
    "Trait": "trait:",
}


def make_node_id(node_type: str, label: str) -> str:
    """Generate node @id from type and label."""
    prefix = NODE_TYPE_PREFIXES.get(node_type, "aether:")
    # Slugify label
    slug = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')
    return f"{prefix}{slug}"


# ─────────────────────────────────────────────────────────────────────
# ASSERTION TO NODE CONVERSION
# ─────────────────────────────────────────────────────────────────────

def assertion_to_node(assertion: dict) -> dict:
    """
    Convert a single NAS assertion to a KG node.

    Mapping:
    - text -> rdfs:label
    - modality/polarity -> @type
    - blacklist_candidates -> for AntiPatterns
    - source_ref -> aether:source
    - confidence -> aether:confidence
    """
    node_type = assertion.get("kg_node_type", "Concept")
    text = assertion.get("text", "")

    # Generate label from text (truncate if needed)
    label = text[:100] + "..." if len(text) > 100 else text

    # Build node
    node = {
        "@id": make_node_id(node_type, text[:50]),
        "@type": f"skill:{node_type}",
        "rdfs:label": label,
        "aether:origin": "core",
        "aether:source": assertion.get("source_ref", {}).get("document", "unknown"),
        "aether:confidence": assertion.get("confidence", 1.0),
        "aether:extraction_method": assertion.get("extraction_method", "unknown"),
    }

    # Add modality-specific properties
    if node_type == "AntiPattern":
        # Include blacklist terms in label for AEC matching
        blacklist = assertion.get("blacklist_candidates", [])
        if blacklist:
            # Append blacklist terms to label for detection
            terms_str = ", ".join(blacklist)
            node["rdfs:label"] = f"{label} ({terms_str})"
            node["aether:blacklist"] = blacklist

    if node_type == "Rule":
        node["aether:strength"] = assertion.get("strength", "SHOULD")

    # Add section context
    section = assertion.get("context") or assertion.get("source_ref", {}).get("section")
    if section:
        node["aether:section"] = section

    return node


# ─────────────────────────────────────────────────────────────────────
# NAS TO KG CONVERSION
# ─────────────────────────────────────────────────────────────────────

def nas_to_kg(nas_doc: dict) -> dict:
    """
    Convert NAS document to JSON-LD knowledge graph.

    Returns KG with @context and @graph containing all nodes.
    """
    assertions = nas_doc.get("assertions", [])

    # Handle direct imports (JSON-LD pass-through)
    if nas_doc.get("direct_import"):
        return {
            "@context": nas_doc.get("context", DEFAULT_CONTEXT),
            "@graph": nas_doc.get("nodes", [])
        }

    # Convert assertions to nodes
    nodes = []
    seen_ids = set()

    for assertion in assertions:
        # Skip duplicates (those with canonical_id set)
        if assertion.get("canonical_id"):
            continue

        # Skip low confidence assertions
        if assertion.get("confidence", 0) < 0.70:
            continue

        # Skip pure descriptive assertions
        if assertion.get("modality") == "DESCRIPTIVE":
            continue

        node = assertion_to_node(assertion)

        # Deduplicate by @id
        if node["@id"] not in seen_ids:
            seen_ids.add(node["@id"])
            nodes.append(node)

    return {
        "@context": DEFAULT_CONTEXT,
        "@graph": nodes
    }


# ─────────────────────────────────────────────────────────────────────
# KG VERIFICATION
# ─────────────────────────────────────────────────────────────────────

def verify_antipatterns(kg: dict) -> dict:
    """
    Verify that all AntiPattern nodes have proper blacklist terms.

    Returns verification result with issues found.
    """
    nodes = kg.get("@graph", [])
    issues = []
    antipattern_count = 0

    for node in nodes:
        node_type = node.get("@type", "")
        if "AntiPattern" in node_type:
            antipattern_count += 1
            label = node.get("rdfs:label", "")
            blacklist = node.get("aether:blacklist", [])

            # Check if label contains terms for AEC blacklist extraction
            if not blacklist and "(" not in label:
                issues.append({
                    "node_id": node.get("@id"),
                    "issue": "missing_blacklist_terms",
                    "message": f"AntiPattern '{label[:50]}' has no blacklist terms in label or aether:blacklist"
                })

    return {
        "valid": len(issues) == 0,
        "antipattern_count": antipattern_count,
        "issues": issues
    }


# ─────────────────────────────────────────────────────────────────────
# KG STATISTICS
# ─────────────────────────────────────────────────────────────────────

def kg_stats(kg: dict) -> dict:
    """Compute statistics for a knowledge graph."""
    nodes = kg.get("@graph", [])

    by_type = {}
    for node in nodes:
        node_type = node.get("@type", "unknown")
        # Extract type name from URI
        if ":" in str(node_type):
            node_type = str(node_type).split(":")[-1]
        by_type[node_type] = by_type.get(node_type, 0) + 1

    return {
        "total_nodes": len(nodes),
        "by_type": by_type
    }


# ─────────────────────────────────────────────────────────────────────
# KG MERGE
# ─────────────────────────────────────────────────────────────────────

def merge_kg(base_kg: dict, new_kg: dict) -> dict:
    """
    Merge new KG nodes into base KG.
    Preserves existing nodes, adds new ones, updates duplicates.
    """
    base_nodes = {node.get("@id"): node for node in base_kg.get("@graph", [])}
    new_nodes = new_kg.get("@graph", [])

    for node in new_nodes:
        node_id = node.get("@id")
        if node_id in base_nodes:
            # Update existing node (merge properties)
            existing = base_nodes[node_id]
            for key, value in node.items():
                if key not in existing or key != "@id":
                    existing[key] = value
            existing["aether:updated"] = datetime.now().isoformat()
        else:
            # Add new node
            base_nodes[node_id] = node

    # Merge contexts
    base_context = base_kg.get("@context", {})
    new_context = new_kg.get("@context", {})
    merged_context = {**DEFAULT_CONTEXT, **base_context, **new_context}

    return {
        "@context": merged_context,
        "@graph": list(base_nodes.values())
    }


if __name__ == "__main__":
    # Test conversion
    test_assertions = [
        {
            "id": "assertion-test-001",
            "text": "MUST use Arial as the default font",
            "modality": "OBLIGATION",
            "polarity": "POSITIVE",
            "strength": "MUST",
            "kg_node_type": "Rule",
            "confidence": 0.95,
            "source_ref": {"document": "test.md", "section": "Fonts"},
            "extraction_method": "deterministic_dsl",
            "blacklist_candidates": [],
        },
        {
            "id": "assertion-test-002",
            "text": "NEVER use percentage table widths",
            "modality": "PROHIBITION",
            "polarity": "NEGATIVE",
            "strength": "MUST",
            "kg_node_type": "AntiPattern",
            "confidence": 1.0,
            "source_ref": {"document": "test.md", "section": "Tables"},
            "extraction_method": "deterministic_dsl",
            "blacklist_candidates": ["percentage", "widthtype.percentage"],
        },
    ]

    nas_doc = {
        "assertions": test_assertions,
        "extraction": {"total_assertions": 2}
    }

    kg = nas_to_kg(nas_doc)
    print(f"Generated KG with {len(kg['@graph'])} nodes:")
    for node in kg["@graph"]:
        print(f"  {node['@type']:20} {node['@id']}")
        print(f"    label: {node['rdfs:label'][:60]}...")

    print(f"\nStats: {kg_stats(kg)}")
    print(f"AntiPattern verification: {verify_antipatterns(kg)}")
