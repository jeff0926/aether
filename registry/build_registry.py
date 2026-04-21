"""
build_registry.py - Auto-generate agent registry KG from capsules in examples/

Scans all valid capsules and creates CapsuleAgent nodes with:
- capsuleId, domain, topics, agentType, capability
- kgNodes, antiPatternCount, ruleCount
- description auto-generated from capsule name and content
"""

import json
import re
from pathlib import Path
from datetime import datetime


def detect_agent_type(name: str, domain: str) -> str:
    """Detect agent type from name and domain."""
    name_lower = name.lower()

    if "orchestrator" in name_lower or "router" in name_lower:
        return "orchestrator"
    if "validator" in name_lower or "verify" in name_lower:
        return "validator"
    if "scholar" in name_lower or "expert" in name_lower:
        return "scholar"
    if "ceo" in name_lower or "executive" in name_lower or "strategy" in name_lower:
        return "executive"
    if "domain" in name_lower or "sap" in name_lower:
        return "domain"

    # Default to skill for task-oriented agents
    return "skill"


def detect_domain(name: str, kg_labels: list) -> str:
    """Detect primary domain from name and KG labels."""
    name_lower = name.lower()
    labels_text = " ".join(kg_labels).lower()

    # Document domains
    if "docx" in name_lower or "word" in name_lower or "document" in labels_text:
        return "document-creation"
    if "pptx" in name_lower or "powerpoint" in name_lower or "presentation" in labels_text:
        return "presentation"
    if "xlsx" in name_lower or "excel" in name_lower or "spreadsheet" in labels_text:
        return "spreadsheet"
    if "pdf" in name_lower:
        return "pdf-processing"

    # Design domains
    if "frontend" in name_lower or "css" in name_lower or "design" in name_lower:
        return "frontend-design"
    if "ui" in name_lower or "ux" in name_lower:
        return "ui-design"

    # History/knowledge domains
    if "jefferson" in name_lower or "history" in name_lower:
        return "american-history"
    if "scholar" in name_lower:
        return "knowledge"
    if "buffett" in name_lower or "investment" in name_lower:
        return "investment"

    # Technical domains
    if "sap" in name_lower or "cap" in name_lower:
        return "sap-development"
    if "python" in name_lower:
        return "python-development"
    if "sql" in name_lower or "database" in name_lower:
        return "database"

    # Business domains
    if "ceo" in name_lower or "executive" in name_lower:
        return "executive-strategy"

    # Validation
    if "validator" in name_lower or "aether" in name_lower:
        return "validation"

    return "general"


def detect_topics(name: str, domain: str, kg_labels: list) -> list:
    """Generate topic subscriptions from name, domain, and KG."""
    topics = set()
    name_lower = name.lower()

    # Add domain as topic
    topics.add(domain.replace("-", "."))

    # Extract keywords from name
    words = re.findall(r'[a-z]+', name_lower)
    for word in words:
        if word not in ["v1", "v2", "agent", "skill", "the", "and", "for"]:
            if len(word) > 2:
                topics.add(word)

    # Domain-specific topics
    if "document" in domain:
        topics.update(["document.create", "docx", "word", "report"])
    if "presentation" in domain:
        topics.update(["presentation.create", "pptx", "slides"])
    if "frontend" in domain or "design" in domain:
        topics.update(["design", "css", "frontend", "ui"])
    if "history" in domain:
        topics.update(["history", "research", "facts"])
    if "strategy" in domain or "executive" in domain:
        topics.update(["strategy", "business", "executive", "leadership"])
    if "sap" in domain:
        topics.update(["sap", "cap", "cds", "odata", "btp"])
    if "validation" in domain:
        topics.update(["validate", "verify", "capsule.validate"])

    return sorted(list(topics))[:8]  # Limit to 8 topics


def detect_capabilities(agent_type: str, domain: str) -> list:
    """Detect capabilities based on agent type and domain."""
    base = {
        "skill": ["create", "generate", "format"],
        "scholar": ["explain", "research", "answer"],
        "executive": ["advise", "strategize", "evaluate"],
        "domain": ["advise", "review", "generate"],
        "validator": ["validate", "verify", "report"],
        "orchestrator": ["route", "coordinate", "delegate"],
    }

    caps = base.get(agent_type, ["assist"])

    # Add domain-specific
    if "document" in domain or "presentation" in domain:
        caps.append("structure")
    if "design" in domain:
        caps = ["design", "advise", "review"]

    return caps[:4]


def generate_description(name: str, domain: str, agent_type: str, kg_labels: list) -> str:
    """Generate a one-sentence description."""
    # Clean name
    clean_name = re.sub(r'-v\d.*', '', name).replace('-', ' ').title()

    domain_desc = domain.replace("-", " ").title()

    if agent_type == "skill":
        return f"{clean_name} — creates and formats {domain_desc} artifacts. Use for {domain_desc.lower()} tasks."
    elif agent_type == "scholar":
        return f"{clean_name} — expert knowledge on {domain_desc}. Use for research and factual questions."
    elif agent_type == "executive":
        return f"{clean_name} — strategic advisor for {domain_desc}. Use for business decisions."
    elif agent_type == "domain":
        return f"{clean_name} — technical expert in {domain_desc}. Use for domain-specific questions."
    elif agent_type == "validator":
        return f"{clean_name} — validates and verifies {domain_desc}. Use for quality checks."
    elif agent_type == "orchestrator":
        return f"{clean_name} — routes queries to appropriate agents. Meta-level coordination."

    return f"{clean_name} — {domain_desc} agent."


def load_capsule_data(capsule_path: Path) -> dict | None:
    """Load capsule data from folder."""
    folder_name = capsule_path.name

    # Find manifest
    manifest_files = list(capsule_path.glob("*-manifest.json"))
    if not manifest_files:
        return None

    try:
        manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    except:
        return None

    # Find KG
    kg_files = list(capsule_path.glob("*-kg.jsonld"))
    kg_nodes = []
    kg_labels = []
    antipattern_count = 0
    rule_count = 0

    if kg_files:
        try:
            kg = json.loads(kg_files[0].read_text(encoding="utf-8"))
            kg_nodes = kg.get("@graph", [])
            for node in kg_nodes:
                label = node.get("rdfs:label", "")
                if label:
                    kg_labels.append(label)
                node_type = node.get("@type", "")
                if "AntiPattern" in node_type:
                    antipattern_count += 1
                elif "Rule" in node_type:
                    rule_count += 1
        except:
            pass

    return {
        "id": manifest.get("id", folder_name),
        "name": manifest.get("name", folder_name),
        "version": manifest.get("version", "1.0.0"),
        "folder_name": folder_name,
        "kg_node_count": len(kg_nodes),
        "kg_labels": kg_labels,
        "antipattern_count": antipattern_count,
        "rule_count": rule_count,
    }


def build_capsule_agent_node(data: dict) -> dict:
    """Build a CapsuleAgent node from capsule data."""
    name = data["name"]
    domain = detect_domain(name, data["kg_labels"])
    agent_type = detect_agent_type(name, domain)
    topics = detect_topics(name, domain, data["kg_labels"])
    capabilities = detect_capabilities(agent_type, domain)
    description = generate_description(name, domain, agent_type, data["kg_labels"])

    node = {
        "@id": f"capsule:{data['folder_name']}",
        "@type": "aether:CapsuleAgent",
        "rdfs:label": name,
        "aether:capsuleId": data["folder_name"],
        "aether:version": data["version"],
        "aether:domain": domain,
        "aether:description": description,
        "aether:topics": topics,
        "aether:agentType": agent_type,
        "aether:capability": capabilities,
        "aether:kgNodes": data["kg_node_count"],
    }

    # Add counts if available
    if data["antipattern_count"] > 0:
        node["aether:antiPatternCount"] = data["antipattern_count"]
    if data["rule_count"] > 0:
        node["aether:ruleCount"] = data["rule_count"]

    return node


def build_registry(examples_dir: Path, output_path: Path) -> int:
    """Build the complete registry KG."""
    nodes = []

    for item in sorted(examples_dir.iterdir()):
        if not item.is_dir():
            continue

        data = load_capsule_data(item)
        if not data:
            continue

        node = build_capsule_agent_node(data)
        nodes.append(node)

    # Build registry document
    registry = {
        "@context": {
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "aether": "http://aether.dev/ontology#",
            "schema": "http://schema.org/"
        },
        "@id": "aether:agent-registry",
        "rdfs:label": "AETHER Agent Registry",
        "aether:version": "1.0.0",
        "aether:generated": datetime.now().isoformat(),
        "aether:capsuleCount": len(nodes),
        "@graph": nodes
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    return len(nodes)


def main():
    """CLI entry point."""
    import sys

    repo_root = Path(__file__).parent.parent
    examples_dir = repo_root / "examples"
    output_path = repo_root / "registry" / "agent-registry.jsonld"

    if not examples_dir.exists():
        print(f"ERROR: Examples directory not found: {examples_dir}")
        sys.exit(1)

    count = build_registry(examples_dir, output_path)
    print(f"Registry built: {count} capsules registered")
    print(f"Output: {output_path}")

    # Print summary by type
    registry = json.loads(output_path.read_text(encoding="utf-8"))
    by_type = {}
    for node in registry["@graph"]:
        agent_type = node.get("aether:agentType", "unknown")
        by_type[agent_type] = by_type.get(agent_type, 0) + 1

    print(f"\nBy type: {by_type}")


if __name__ == "__main__":
    main()
