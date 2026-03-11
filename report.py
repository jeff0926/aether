"""
Report - ASCII-formatted execution report for Aether pipeline runs.
"""

import sys
from datetime import datetime

VERSION = "1.0.0"


def print_report(ctx: dict, aec_result: dict, capsule) -> None:
    """Print comprehensive ASCII execution report to stdout."""
    # Ensure UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    w = 78  # Report width

    # =========================================================================
    # HEADER
    # =========================================================================
    print()
    print("   █████╗ ███████╗████████╗██╗  ██╗███████╗██████╗ ")
    print("  ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔════╝██╔══██╗")
    print("  ███████║█████╗     ██║   ███████║█████╗  ██████╔╝")
    print("  ██╔══██║██╔══╝     ██║   ██╔══██║██╔══╝  ██╔══██╗")
    print("  ██║  ██║███████╗   ██║   ██║  ██║███████╗██║  ██║")
    print("  ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝")
    print("  Adaptive Embodied Thinking Holistic Evolutionary Runtime")
    print()
    print(_box_top(w))
    print(_box_row(f"EXECUTION REPORT", w, center=True))
    print(_box_row(f"v{VERSION}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", w, center=True))
    print(_box_bottom(w))

    # =========================================================================
    # AGENT PROFILE
    # =========================================================================
    print(_section_header("AGENT PROFILE", w))

    manifest = capsule.files.get("manifest", {})
    persona = capsule.files.get("persona", {})
    definition = capsule.files.get("definition", {})
    kb = capsule.files.get("kb", "")
    kg = capsule.files.get("kg", {})

    # KB stats
    kb_chars = len(kb)
    kb_paragraphs = len([p for p in kb.split("\n\n") if p.strip()])

    # KG stats
    kg_nodes = kg.get("@graph", [kg] if "@id" in kg else [])
    kg_node_count = len(kg_nodes)
    kg_triples = sum(len([k for k in n.keys() if not k.startswith("@")]) for n in kg_nodes)
    kg_entities = len([n for n in kg_nodes if n.get("@id", "").startswith("entity:")])

    # Capsule size (estimate from loaded data)
    import json
    capsule_size = kb_chars + len(json.dumps(kg)) + len(json.dumps(manifest))
    capsule_size += len(json.dumps(persona)) + len(json.dumps(definition))

    print(_kv_row("Name", capsule.name, w))
    print(_kv_row("ID", capsule.id, w))
    print(_kv_row("Version", capsule.version, w))
    print(_kv_row("Persona", f"{persona.get('tone', 'neutral')} / {persona.get('style', 'informative')}", w))
    print(_kv_row("AEC Threshold", str(definition.get("review", {}).get("threshold", 0.8)), w))
    print(_kv_row("KB Size", f"{kb_chars:,} chars, {kb_paragraphs} paragraphs", w))
    print(_kv_row("KG Size", f"{kg_node_count} nodes, {kg_triples} triples", w))
    print(_kv_row("Capsule Size", f"{capsule_size:,} bytes (approx)", w))
    print(_box_bottom(w))

    # =========================================================================
    # PIPELINE RESULTS
    # =========================================================================
    print(_section_header("PIPELINE RESULTS", w))

    tel = ctx.get("telemetry", {})
    stages = tel.get("stages", {})
    distilled = ctx.get("distilled", {})
    augmented = ctx.get("augmented", {})

    # Distill
    print(_subsection("Stage 1: DISTILL", w))
    d = stages.get("distill", {})
    print(_kv_row("Time", f"{d.get('time_ms', 0):.2f} ms", w))
    print(_kv_row("Intent", distilled.get("intent", "unknown"), w))
    print(_kv_row("Entities", str(d.get("entities_extracted", 0)), w))
    if distilled.get("entities"):
        print(_kv_row("", ", ".join(distilled["entities"][:5]), w))
    print(_kv_row("Format", distilled.get("format") or "none", w))
    print(_kv_row("Brevity", "yes" if distilled.get("brevity") else "no", w))

    # Augment
    print(_subsection("Stage 2: AUGMENT", w))
    a = stages.get("augment", {})
    print(_kv_row("Time", f"{a.get('time_ms', 0):.2f} ms", w))
    print(_kv_row("KB Matched", f"{a.get('kb_matches', 0)} paragraphs", w))
    print(_kv_row("KG Matched", f"{a.get('kg_matches', 0)} nodes", w))

    # List matched KG node labels
    matched_kg = augmented.get("kg", [])
    if matched_kg:
        labels = [n.get("rdfs:label", n.get("@id", "?")) for n in matched_kg[:5]]
        print(_kv_row("KG Labels", ", ".join(labels), w))

    # Generate
    print(_subsection("Stage 3: GENERATE", w))
    g = stages.get("generate", {})
    print(_kv_row("Time", f"{g.get('time_ms', 0):.2f} ms", w))
    print(_kv_row("Prompt", f"{g.get('prompt_chars', 0):,} chars", w))
    print(_kv_row("Tokens In", str(g.get("tokens_in", 0)), w))
    print(_kv_row("Tokens Out", str(g.get("tokens_out", 0)), w))

    # Cost estimation
    tokens_in = g.get("tokens_in", 0)
    tokens_out = g.get("tokens_out", 0)
    # Estimate using Claude Sonnet rates
    cost = (tokens_in / 1000 * 0.003) + (tokens_out / 1000 * 0.015)
    print(_kv_row("Est. Cost", f"${cost:.6f}", w))

    # Review
    print(_subsection("Stage 4: REVIEW", w))
    r = stages.get("review", {})
    print(_kv_row("Time", f"{r.get('time_ms', 0):.2f} ms", w))
    print(_kv_row("AEC Passed", "yes" if ctx.get("review", {}).get("passed") else "no", w))
    print(_box_bottom(w))

    # =========================================================================
    # AEC VERIFICATION
    # =========================================================================
    print(_section_header("AEC VERIFICATION", w))

    score = aec_result.get("score", 0)
    threshold = aec_result.get("threshold", 0.8)
    passed = aec_result.get("passed", False)
    grounded = aec_result.get("grounded_statements", 0)
    ungrounded = aec_result.get("ungrounded_statements", 0)
    persona_count = aec_result.get("persona_statements", 0)

    # Score bar
    bar_width = 50
    filled = int(score * bar_width)
    thresh_pos = int(threshold * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    print(_kv_row("Score", f"{score:.2f}", w))
    print(f"│  [{bar}] │".ljust(w - 1) + "│")

    # Threshold marker
    marker = " " * (thresh_pos + 3) + "▲ threshold=" + str(threshold)
    print(f"│{marker}".ljust(w - 1) + "│")

    print(_kv_row("Result", "PASS" if passed else "FAIL", w))
    print(_kv_row("Grounded", str(grounded), w))
    print(_kv_row("Ungrounded", str(ungrounded), w))
    print(_kv_row("Persona", str(persona_count), w))

    total_verifiable = grounded + ungrounded
    if total_verifiable > 0:
        persona_ratio = persona_count / (total_verifiable + persona_count)
        print(_kv_row("Persona Ratio", f"{persona_ratio:.1%}", w))

    # Statement details table
    details = aec_result.get("details", [])
    if details:
        print(_subsection("Statement Analysis", w))
        print(f"│  {'#':<3} {'Statement':<40} {'Category':<12} {'Method':<10} │")
        print(f"│  {'─'*3} {'─'*40} {'─'*12} {'─'*10} │")
        for i, d in enumerate(details[:10], 1):
            stmt = d.get("statement", "")[:38]
            cat = d.get("category", "?")[:10]
            method = d.get("method", "-")[:8]
            print(f"│  {i:<3} {stmt:<40} {cat:<12} {method:<10} │")
        if len(details) > 10:
            print(f"│  ... and {len(details) - 10} more statements".ljust(w - 1) + "│")

    # Gaps
    gaps = aec_result.get("gaps", [])
    if gaps:
        print(_subsection("Knowledge Gaps", w))
        for gap in gaps[:5]:
            gap_text = gap.get('text', str(gap)) if isinstance(gap, dict) else str(gap)
            print(f"│    - {gap_text[:70]}".ljust(w - 1) + "│")

    print(_box_bottom(w))

    # =========================================================================
    # TELEMETRY SUMMARY
    # =========================================================================
    print(_section_header("TELEMETRY SUMMARY", w))

    total_ms = tel.get("total_ms", 0)
    llm_ms = stages.get("generate", {}).get("time_ms", 0)
    aether_ms = total_ms - llm_ms

    print(_kv_row("Total Time", f"{total_ms:,.1f} ms", w))
    print(_kv_row("Aether Time", f"{aether_ms:,.1f} ms", w))
    print(_kv_row("LLM Time", f"{llm_ms:,.1f} ms", w))

    if total_ms > 0:
        llm_pct = (llm_ms / total_ms) * 100
        print(_kv_row("LLM %", f"{llm_pct:.1f}%", w))

    print(_kv_row("Tokens In", str(tokens_in), w))
    print(_kv_row("Tokens Out", str(tokens_out), w))
    print(_kv_row("Tokens Total", str(tokens_in + tokens_out), w))
    print(_kv_row("Est. Cost", f"${cost:.6f}", w))
    print(_box_bottom(w))

    # =========================================================================
    # FOOTER
    # =========================================================================
    print(_box_top(w))
    footer = f"AETHER v{VERSION}  |  {capsule.name}  |  {datetime.now().strftime('%Y-%m-%d')}"
    print(_box_row(footer, w, center=True))
    print(_box_bottom(w))
    print()


# =============================================================================
# Box Drawing Helpers
# =============================================================================

def _box_top(w: int) -> str:
    return "╔" + "═" * (w - 2) + "╗"


def _box_bottom(w: int) -> str:
    return "╚" + "═" * (w - 2) + "╝"


def _box_row(text: str, w: int, center: bool = False) -> str:
    inner = w - 4
    if center:
        text = text.center(inner)
    else:
        text = text.ljust(inner)
    return f"║ {text[:inner]} ║"


def _section_header(title: str, w: int) -> str:
    return "╔═══ " + title + " " + "═" * (w - len(title) - 7) + "╗"


def _subsection(title: str, w: int) -> str:
    return "├─── " + title + " " + "─" * (w - len(title) - 7) + "┤"


def _kv_row(key: str, value: str, w: int) -> str:
    if key:
        content = f"  {key}: {value}"
    else:
        content = f"    {value}"
    return f"│{content}".ljust(w - 1) + "│"


if __name__ == "__main__":
    # Test with mock data
    mock_ctx = {
        "input": "What is Aether?",
        "distilled": {"intent": "query", "entities": ["Aether"], "brevity": False, "format": None},
        "augmented": {"kb": ["Test para"], "kg": [{"@id": "test", "rdfs:label": "Test"}]},
        "generated": "Aether is a framework.",
        "review": {"passed": True, "length_ok": True},
        "telemetry": {
            "total_ms": 1234.5,
            "stages": {
                "distill": {"time_ms": 0.5, "entities_extracted": 1},
                "augment": {"time_ms": 1.2, "kb_matches": 1, "kg_matches": 1},
                "generate": {"time_ms": 1230.0, "prompt_chars": 150, "tokens_in": 50, "tokens_out": 100},
                "review": {"time_ms": 0.3},
            }
        }
    }
    mock_aec = {
        "score": 0.85,
        "threshold": 0.8,
        "passed": True,
        "grounded_statements": 2,
        "ungrounded_statements": 0,
        "persona_statements": 1,
        "details": [
            {"statement": "Aether is a framework", "category": "PERSONA", "method": "-"},
        ],
        "gaps": [],
    }

    class MockCapsule:
        id = "test-agent-v1.0.0-abc12345"
        name = "Test Agent"
        version = "1.0.0"
        files = {
            "manifest": {"id": "test-agent-v1.0.0-abc12345", "name": "Test Agent", "version": "1.0.0"},
            "persona": {"tone": "professional", "style": "concise"},
            "definition": {"review": {"threshold": 0.8}},
            "kb": "# Test KB\n\nThis is a test.",
            "kg": {"@graph": [{"@id": "test", "rdfs:label": "Test"}]},
        }

    print_report(mock_ctx, mock_aec, MockCapsule())
