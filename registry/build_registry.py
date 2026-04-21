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


# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN-SPECIFIC TOPICS AND DESCRIPTIONS
# These override auto-generated topics for precise routing
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_TOPICS = {
    "docx": ["docx", "word", "word-document", "document.create",
             "report", "status-report", "project-report", "docx-file"],
    "pptx": ["pptx", "powerpoint", "presentation", "slides",
             "deck", "slide-deck", "presentation.create"],
    "pdf": ["pdf", "pdf-file", "pdf.create", "portable-document"],
    "xlsx": ["xlsx", "excel", "spreadsheet", "worksheet",
             "excel-file", "spreadsheet.create"],
    "frontend-design": ["css", "design", "frontend", "typography",
                        "ui", "ux", "design-system", "color", "layout",
                        "component", "stylesheet"],
    "jefferson": ["jefferson", "thomas-jefferson", "history",
                  "american-history", "founding-fathers",
                  "declaration-of-independence", "louisiana-purchase",
                  "president", "monticello"],
    "ceo-engine": ["strategy", "ceo", "executive", "business-strategy",
                   "market", "leadership", "go-to-market",
                   "competitive-analysis", "board"],
    "sap-cap": ["sap", "cap", "cds", "odata", "btp",
                "sap-cap", "cloud-application-programming",
                "abap", "fiori", "s4hana"],
    "skill-creator": ["skill.create", "skill-builder", "skill-creator",
                      "aether-skill", "new-skill", "build-skill"],
    "claude-api": ["claude-api", "anthropic-api", "api-integration",
                   "claude-integration", "api-key", "sdk"],
    "algorithmic-art": ["generative-art", "algorithmic", "procedural",
                        "creative-coding", "art-generation"],
    "canvas-design": ["canvas", "html-canvas", "2d-graphics", "drawing"],
    "doc-coauthoring": ["coauthoring", "collaboration", "document-editing",
                        "track-changes", "comments"],
    "buffett": ["investment", "buffett", "value-investing", "stocks",
                "portfolio", "warren-buffett"],
    "orchestrator": ["orchestrate", "route", "coordinate", "multi-agent"],
    "aether-validator": ["validate", "aec", "capsule.validate", "verification"],
}

DOMAIN_DESCRIPTIONS = {
    "docx": "Creates professional Word (.docx) documents with correct heading styles, tables, and formatting. Use for ANY request to create a Word document, report, memo, or .docx file.",
    "pptx": "Creates PowerPoint presentations (.pptx). Use for ANY request to create slides, a deck, or a presentation.",
    "pdf": "Creates and manipulates PDF files. Use for ANY request involving PDF creation or editing.",
    "xlsx": "Creates Excel spreadsheets (.xlsx). Use for ANY request to create a spreadsheet, worksheet, or Excel file.",
    "frontend-design": "Frontend design and CSS expert. Use for design system questions, typography, CSS patterns, and UI guidance.",
    "jefferson": "Expert scholar on Thomas Jefferson. Use for questions about Jefferson, his presidency, the Declaration of Independence, or early American history.",
    "ceo-engine": "CEO-level strategic advisor. Use for business strategy, market positioning, and executive decisions. Does NOT handle technical architecture or HR.",
    "sap-cap": "SAP CAP development expert. Use for SAP Cloud Application Programming model, CDS, OData, and BTP questions.",
    "skill-creator": "Creates new AETHER skills and capsules. Use ONLY for requests to build, create, or define new agent skills. Do NOT use for document, presentation, or content creation.",
    "claude-api": "Expert on Claude API and Anthropic SDK. Use for questions about integrating Claude, API usage, and SDK setup.",
    "buffett": "Investment advisor specializing in Warren Buffett's value investing principles. Use for investment strategy and stock analysis.",
    "orchestrator": "Routes queries to appropriate domain agents. Meta-level coordination. Never answers directly.",
    "aether-validator": "Validates AETHER capsule structure and AEC verification results. Use for capsule quality checks.",
}


def get_domain_key(name: str) -> str | None:
    """Get the matching domain key for a capsule name."""
    name_lower = name.lower()
    for key in DOMAIN_TOPICS:
        if key in name_lower:
            return key
    return None


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

    # Check explicit domain mappings first (order matters!)
    # Skill-creator is NOT document-creation
    if "skill-creator" in name_lower:
        return "skill-development"
    if "claude-api" in name_lower:
        return "api-integration"
    if "orchestrator" in name_lower:
        return "orchestration"
    if "doc-coauthoring" in name_lower:
        return "collaboration"
    if "algorithmic-art" in name_lower or "canvas-design" in name_lower:
        return "generative-art"

    # Document domains (must check name specifically, not just labels)
    if "docx" in name_lower:
        return "document-creation"
    if "pptx" in name_lower:
        return "presentation"
    if "xlsx" in name_lower:
        return "spreadsheet"
    if "pdf" in name_lower:
        return "pdf-processing"

    # Design domains
    if "frontend" in name_lower or ("design" in name_lower and "css" in labels_text):
        return "frontend-design"

    # History/knowledge domains
    if "jefferson" in name_lower:
        return "american-history"
    if "buffett" in name_lower:
        return "investment"
    if "scholar" in name_lower:
        return "knowledge"

    # Technical domains
    if "sap" in name_lower or "cap" in name_lower:
        return "sap-development"

    # Business domains
    if "ceo" in name_lower or "ceo-engine" in name_lower:
        return "executive-strategy"

    # Validation
    if "validator" in name_lower or "aether-validator" in name_lower:
        return "validation"

    return "general"


def detect_topics(name: str, domain: str, kg_labels: list) -> list:
    """Generate topic subscriptions from name, domain, and KG."""
    # First check if we have explicit topics for this capsule type
    domain_key = get_domain_key(name)
    if domain_key and domain_key in DOMAIN_TOPICS:
        return DOMAIN_TOPICS[domain_key][:10]

    # Fall back to auto-generated topics
    topics = set()
    name_lower = name.lower()

    # Add domain as topic
    topics.add(domain.replace("-", "."))

    # Extract keywords from name (exclude common words)
    skip_words = {"v1", "v2", "agent", "skill", "the", "and", "for",
                  "creator", "builder", "maker", "helper"}
    words = re.findall(r'[a-z]+', name_lower)
    for word in words:
        if word not in skip_words and len(word) > 2:
            topics.add(word)

    # Domain-specific fallback topics (more conservative)
    if "document" in domain and "docx" in name_lower:
        topics.update(["document.create", "docx", "word", "report"])
    if "presentation" in domain:
        topics.update(["presentation.create", "pptx", "slides"])
    if "spreadsheet" in domain:
        topics.update(["spreadsheet.create", "xlsx", "excel"])
    if "pdf" in domain:
        topics.update(["pdf", "pdf.create"])
    if "frontend" in domain or "design" in domain:
        topics.update(["design", "css", "frontend", "ui"])
    if "history" in domain:
        topics.update(["history", "research", "facts"])
    if "strategy" in domain or "executive" in domain:
        topics.update(["strategy", "business", "executive"])
    if "sap" in domain:
        topics.update(["sap", "cap", "cds", "odata", "btp"])
    if "validation" in domain:
        topics.update(["validate", "verify", "capsule.validate"])

    # If no specific topics, use general
    if len(topics) <= 1:
        topics.add("general")

    return sorted(list(topics))[:10]


def detect_capabilities(agent_type: str, domain: str) -> list:
    """Detect capabilities based on agent type and domain."""
    base = {
        "skill": ["create", "generate", "format"],
        "scholar": ["explain", "research", "answer"],
        "role": ["advise", "strategize", "evaluate"],       # Business roles
        "domain": ["advise", "review", "generate"],
        "logic": ["evaluate", "enforce", "decide"],         # Rules/DSL
        "validator": ["validate", "verify", "report"],
        "guardrail": ["block", "filter", "enforce"],        # Safety/policy
        "orchestrator": ["route", "coordinate", "delegate"],
        "executive": ["advise", "strategize", "evaluate"],  # Legacy alias for role
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
    # First check if we have an explicit description
    domain_key = get_domain_key(name)
    if domain_key and domain_key in DOMAIN_DESCRIPTIONS:
        return DOMAIN_DESCRIPTIONS[domain_key]

    # Fall back to auto-generated description
    clean_name = re.sub(r'-v\d.*', '', name).replace('-', ' ').title()
    domain_desc = domain.replace("-", " ").title()

    if agent_type == "skill":
        return f"{clean_name} — creates and formats {domain_desc} artifacts. Use for {domain_desc.lower()} tasks."
    elif agent_type == "scholar":
        return f"{clean_name} — expert knowledge on {domain_desc}. Use for research and factual questions."
    elif agent_type == "role":
        return f"{clean_name} — operates as a business role for {domain_desc}. Use for strategic decisions."
    elif agent_type == "executive":  # Legacy alias
        return f"{clean_name} — strategic advisor for {domain_desc}. Use for business decisions."
    elif agent_type == "domain":
        return f"{clean_name} — technical expert in {domain_desc}. Use for domain-specific questions."
    elif agent_type == "logic":
        return f"{clean_name} — enforces rules and decisions for {domain_desc}. Use for rule-based evaluations."
    elif agent_type == "validator":
        return f"{clean_name} — validates and verifies {domain_desc}. Use for quality checks."
    elif agent_type == "guardrail":
        return f"{clean_name} — enforces policy and catches violations for {domain_desc}. Use for safety checks."
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
        "agentType": manifest.get("agentType"),  # Source of truth from manifest
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

    # Use agentType from manifest (source of truth), fallback to detection
    agent_type = data.get("agentType")
    if not agent_type:
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
