"""
Ingest - Automated document-to-capsule pipeline.
Two modes: ingest_research (deterministic) and ingest_document (LLM-assisted).
"""
import json, re
from pathlib import Path
from datetime import datetime
from aether import generate_id, REQUIRED_SUFFIXES
from stamper import DEFAULT_DEFINITION, DEFAULT_KG, _write_json


def _clean_gemini(text: str) -> str:
    """Remove markdown escaping damage from Gemini output."""
    for esc in ["\\_", "\\[", "\\]", "\\*", "\\#", "\\>", "\\|", "\\(", "\\)"]:
        text = text.replace(esc, esc[1])
    return text

def _fix_json_str(raw: str) -> str:
    """Fix common Gemini JSON damage before parsing."""
    raw = _clean_gemini(raw)
    raw = raw.replace("\\.", ".")              # escaped periods
    raw = raw.replace("\\-", "-")              # escaped hyphens
    raw = re.sub(r'[ \t]+$', '', raw, flags=re.MULTILINE)  # trailing whitespace
    raw = re.sub(r':\s*,', ': [],', raw)       # "key":,  → "key": [],
    raw = re.sub(r':\s*\n\s*}', ': null\n}', raw)  # "key":\n} → "key": null\n}
    raw = re.sub(r',\s*([}\]])', r'\1', raw)    # trailing commas
    # Truncated array opening: "key":"  \n  },  → "key": [\n  {
    # Only apply when followed by object-like content (has "subject" or similar)
    raw = re.sub(r':"\s*\n(\s*}\s*,\s*\n\s*\{)', r': [\n{', raw)
    return raw

def _extract_json_block(text: str) -> dict | list | None:
    """Extract first JSON object or array from text. Handles fenced and bare."""
    # Try fenced ```json ... ``` first
    m = re.search(r'```(?:json|jsonld)?\s*\n(.*?)```', text, re.DOTALL)
    if m:
        raw = m.group(1).strip()
        for fix in [lambda s: s, _fix_json_str]:
            try:
                return json.loads(fix(raw))
            except (json.JSONDecodeError, Exception):
                pass

    # Try bare JSON: find outermost { } or [ ]
    for opener, closer in [('{', '}'), ('[', ']')]:
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    raw = text[start:i + 1]
                    for fix in [lambda s: s, _fix_json_str]:
                        try:
                            return json.loads(fix(raw))
                        except (json.JSONDecodeError, Exception):
                            pass
                    break
    return None

def _split_sections(text: str) -> dict:
    """Split markdown into sections by ## headers or **Bold** standalone lines.
    Code-fence-aware — ignores lines inside ``` blocks."""
    sections = {}
    current_header = "_preamble"
    current_content = []
    in_fence = False

    for line in text.splitlines():
        stripped = line.strip()

        # Track fenced code blocks
        if stripped.startswith("```"):
            in_fence = not in_fence
            current_content.append(line)
            continue

        if in_fence:
            current_content.append(line)
            continue

        # Skip divider-only lines like "## ---"
        if re.match(r'^#{1,3}\s+---\s*$', stripped):
            continue

        # Match ## Header or ### **Bold Header**
        header_match = re.match(r'^#{1,3}\s+\**(.+?)\**\s*$', stripped)
        # Match standalone **Bold Text** (Gemini style)
        if not header_match:
            header_match = re.match(r'^\*\*([^*]+)\*\*\s*$', stripped)

        if header_match:
            if current_content:
                sections[current_header] = "\n".join(current_content).strip()
            current_header = header_match.group(1).strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_header] = "\n".join(current_content).strip()

    return sections

def _extract_all_objects(text: str) -> list:
    """Salvage individual JSON objects from badly damaged JSON. Last resort.
    If an outer object fails to parse, recurse into its contents."""
    objects = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 0
            for j in range(i, len(text)):
                if text[j] == '{': depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        raw = text[i:j + 1]
                        parsed = False
                        for fix in [lambda s: s, _fix_json_str]:
                            try:
                                obj = json.loads(fix(raw))
                                if isinstance(obj, dict) and len(obj) > 2:
                                    objects.append(obj)
                                parsed = True
                                break
                            except (json.JSONDecodeError, Exception):
                                pass
                        if not parsed:
                            # Outer object broken — try inner objects
                            inner = text[i + 1:j]
                            objects.extend(_extract_all_objects(inner))
                        i = j + 1
                        break
            else:
                break
        else:
            i += 1
    return objects

def _find_section(sections: dict, *keywords) -> str | None:
    """Find first section whose header contains any of the keywords."""
    for header, content in sections.items():
        for kw in keywords:
            if kw in header:
                return content
    return None

def _stamp_capsule(output_path: Path, agent_name: str, version: str,
                   kb: str, kg: dict, persona: dict, definition: dict) -> Path:
    """Create capsule folder with all 5 files."""
    capsule_id = generate_id(agent_name, version)
    capsule_path = output_path / capsule_id
    capsule_path.mkdir(parents=True, exist_ok=True)

    prefix = capsule_id

    # manifest
    _write_json(capsule_path / f"{prefix}-manifest.json", {
        "id": capsule_id, "name": agent_name, "version": version,
        "created": datetime.now().isoformat(),
    })

    # definition — merge with defaults
    merged_def = {**DEFAULT_DEFINITION, **definition}
    if "pipeline" not in merged_def:
        merged_def["pipeline"] = DEFAULT_DEFINITION["pipeline"]
    _write_json(capsule_path / f"{prefix}-definition.json", merged_def)

    # persona
    _write_json(capsule_path / f"{prefix}-persona.json", persona)

    # kb
    (capsule_path / f"{prefix}-kb.md").write_text(kb, encoding="utf-8")

    # kg
    _write_json(capsule_path / f"{prefix}-kg.jsonld", kg)

    return capsule_path


def ingest_research(source_path: str | Path, output_path: str | Path,
                    agent_name: str, version: str = "1.0.0") -> Path:
    """Parse deep research prompt output into a capsule. No LLM needed."""
    source_path = Path(source_path)
    output_path = Path(output_path)

    raw = source_path.read_text(encoding="utf-8")
    cleaned = _clean_gemini(raw)
    sections = _split_sections(cleaned)

    # --- KB: everything before "Knowledge Graph Relationship" header ---
    # Match both ## Header and standalone **Bold** formats
    kg_header_pat = re.search(
        r'^(?:#{1,3}\s+)?\**\s*knowledge\s+graph\s+relationship.*$',
        cleaned, re.MULTILINE | re.IGNORECASE,
    )
    # Also check for ## --- divider before the KG section
    if not kg_header_pat:
        kg_header_pat = re.search(
            r'^##\s+---\s*\n+\**\s*knowledge\s+graph\s+relationship',
            cleaned, re.MULTILINE | re.IGNORECASE,
        )
    if kg_header_pat:
        kb = cleaned[:kg_header_pat.start()].strip()
    else:
        kb = cleaned

    # --- KG: JSON block in the Knowledge Graph section ---
    kg_section = _find_section(sections, "knowledge graph relationship", "knowledge graph")
    kg = DEFAULT_KG.copy()
    if kg_section:
        kg_data = _extract_json_block(kg_section)
        if isinstance(kg_data, dict):
            if "@graph" in kg_data:
                kg = kg_data
            elif "knowledge_graph_triples" in kg_data and isinstance(kg_data["knowledge_graph_triples"], list):
                kg = {**DEFAULT_KG, "@graph": kg_data["knowledge_graph_triples"]}
                if "entity_registry" in kg_data:
                    kg["entity_registry"] = kg_data["entity_registry"]
            else:
                kg = {**DEFAULT_KG, "@graph": [kg_data]}
        elif isinstance(kg_data, list):
            kg = {**DEFAULT_KG, "@graph": kg_data}
        # Fallback: if JSON is too damaged or graph has no real objects, salvage
        graph = kg.get("@graph", [])
        if not graph or not any(isinstance(n, dict) for n in graph):
            salvaged = _extract_all_objects(kg_section)
            if salvaged:
                kg["@graph"] = salvaged

    # --- Persona: JSON block in Structured Persona Meta-data section ---
    persona_section = _find_section(sections, "structured persona meta-data",
                                    "structured persona metadata", "persona meta")
    persona = {"tone": "neutral", "style": "informative", "constraints": []}
    if persona_section:
        persona_data = _extract_json_block(persona_section)
        if isinstance(persona_data, dict):
            persona = persona_data

    # --- Definition: JSON block in Agent Definition section ---
    def_section = _find_section(sections, "agent definition")
    definition = {}
    if def_section:
        def_data = _extract_json_block(def_section)
        if not isinstance(def_data, dict):
            # JSON too damaged — pre-fix the section then retry
            def_data = _extract_json_block(_fix_json_str(def_section))
        if isinstance(def_data, dict):
            definition = def_data.get("agent_definition", def_data)

    return _stamp_capsule(output_path, agent_name, version, kb, kg, persona, definition)


_KG_PROMPT = (
    "Extract entities and relationships from this document as JSON-LD. "
    "Return a JSON object with \"@context\" and \"@graph\" array. "
    "Each node needs @id, @type, rdfs:label, and relevant properties. "
    "Return ONLY valid JSON.\n\nDocument:\n{doc}")

_PERSONA_PROMPT = (
    "Based on this document's subject and tone, suggest a persona for an AI agent. "
    "Return JSON with keys: persona_name, tone, style, interaction_style_traits "
    "(object of trait: bool), persona_keywords (array), persona_description (string). "
    "Return ONLY valid JSON.\n\nDocument:\n{doc}")

_DEFINITION_PROMPT = (
    "Based on this document, define an AI agent. Return JSON with keys: agent_type, "
    "agent_name, primary_function, domain_boundaries (object with authoritative and "
    "out_of_scope arrays), suggested_aec_gates (array). "
    "Return ONLY valid JSON.\n\nDocument:\n{doc}")

_STUB_KG = {"@context": {"rdfs": "http://www.w3.org/2000/01/rdf-schema#",
             "aether": "http://aether.dev/ontology#"}, "@graph": []}
_STUB_PERSONA = {"persona_name": "Document Agent", "tone": "neutral",
    "style": "informative", "interaction_style_traits": {"analytical": True},
    "persona_keywords": ["informative", "factual"],
    "persona_description": "An agent based on the provided document."}
_STUB_DEFINITION = {"agent_type": "scholar", "agent_name": "Document Agent",
    "primary_function": "Knowledge source based on ingested document.",
    "domain_boundaries": {"authoritative": [], "out_of_scope": []},
    "suggested_aec_gates": ["entity_matching"]}

def _llm_extract(llm_fn, prompt_template: str, doc: str, fallback: dict) -> dict:
    """Call LLM, parse JSON response, return fallback on failure."""
    prompt = prompt_template.format(doc=doc[:8000])  # Cap context size
    try:
        result = llm_fn(prompt)
        text = result.get("text", result) if isinstance(result, dict) else result
        data = _extract_json_block(str(text))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return fallback

def ingest_document(source_path: str | Path, output_path: str | Path,
                    agent_name: str, agent_type: str = "scholar",
                    version: str = "1.0.0", llm_fn=None) -> Path:
    """Ingest any markdown file into a capsule using LLM extraction."""
    source_path = Path(source_path)
    output_path = Path(output_path)

    doc = source_path.read_text(encoding="utf-8")
    kb = _clean_gemini(doc)

    if llm_fn is None:
        # Stub mode — use defaults
        kg = _STUB_KG
        persona = {**_STUB_PERSONA, "persona_name": f"{agent_name} Agent"}
        definition = {**_STUB_DEFINITION, "agent_type": agent_type,
                      "agent_name": agent_name}
    else:
        kg = _llm_extract(llm_fn, _KG_PROMPT, doc, _STUB_KG)
        persona = _llm_extract(llm_fn, _PERSONA_PROMPT, doc, _STUB_PERSONA)
        definition = _llm_extract(llm_fn, _DEFINITION_PROMPT, doc, _STUB_DEFINITION)

    return _stamp_capsule(output_path, agent_name, version, kb, kg, persona, definition)


if __name__ == "__main__":
    print("ingest.py loaded — ingest_research, ingest_document")
