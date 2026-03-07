# AETHER File Summaries
## Every file in the project — what it does, key functions, and how it connects

---

## Core Pipeline Files

### aether.py (360 lines) — The Heart
**Purpose:** Capsule class that loads 5 files from a folder and runs the 4-stage pipeline.

**Constants:**
- `REQUIRED_SUFFIXES` — maps file types to naming patterns: manifest, definition, persona, kb, kg

**Classes:**
- `Capsule(path, llm_fn=None)` — loads all 5 files, validates manifest, defaults pipeline config
  - `.id`, `.name`, `.version` — properties from manifest
  - `.run(input_text)` → full pipeline, returns ctx dict with all results + telemetry
  - `.distill(ctx)` — Stage 1: extract intent (query/instruction/comparison/creation/general), entities (capitalized words), keywords (stop-word filtered), format preference, brevity flag
  - `.augment(ctx)` — Stage 2: search KB paragraphs by term overlap, query KG nodes via `kg_query()`, attach persona tone/style
  - `.generate(ctx)` — Stage 3: build prompt with persona + grounding instruction + constraints + KB context + KG node properties, call LLM, handle dict/string response
  - `.review(ctx)` — Stage 4: run AEC verification against augmented KG subgraph, queue failures to education

**Functions:**
- `get_required_files(folder_name)` → dict of expected filenames
- `generate_id(name, version)` → `{slug}-v{version}-{uid8}` using SHA256 of name+version+timestamp
- `validate_folder(path)` → list of missing files

**Imports from:** aec, kg, education
**Imported by:** cli, education (lazy), ingest

---

### aec.py (255 lines) — The Verification Gate
**Purpose:** Deterministic entailment check — extracts verifiable values from LLM output and matches against KG.

**Key concept:** Statements are categorized as GROUNDED (values match KG), UNGROUNDED (values don't match), or PERSONA (no verifiable values). Score = grounded/(grounded+ungrounded). Persona excluded.

**Functions:**
- `split_statements(response)` → list of sentences (>10 chars). Protects abbreviations (Mr., Dr., etc.), splits on `.!?` followed by capital letter
- `_extract_values(text)` → list of (original, normalized, type) tuples:
  - Magnitude numbers: "$25 million" → 25000000 (million/billion/trillion/thousand)
  - Plain numbers: integers, decimals, comma-grouped
  - Percentages: N%, N percent, N pct
  - Dates: years (1700-2099), full dates (Month Day, Year → ISO format)
  - Names: capitalized word sequences (skips pronouns/articles)
- `_flatten_kg(kg_nodes)` → flattens nested KG dicts into {key: [values]} for searching
- `_match_in_kg(value, value_type, kg_flat, tolerance=0.01)` → (bool, key). String match (case-insensitive, partial). Numeric match with 1% tolerance.
- `deterministic_gate(statement, kg_nodes)` → {matched, entity, method, values_found, matches}
- `verify(response, kg_nodes, threshold=0.8)` → full AEC result dict with score, passed, statement breakdowns, gaps

**Default threshold:** 0.8
**Imported by:** aether, education (lazy), cli

---

### kg.py (219 lines) — Knowledge Graph Manager
**Purpose:** JSON-LD loader with 5 knowledge origin types and CRUD operations.

**Constants:**
- `ORIGIN_TYPES = ["core", "acquired", "updated", "deprecated", "provenance"]`
- `EMPTY_KG` — template with @context (rdfs + aether namespace) and empty @graph

**Functions:**
- `load_kg(path)` → dict. Normalizes to @graph format. Returns empty graph if missing.
- `get_nodes(kg)` → list of all nodes from @graph
- `query_nodes(kg, entities)` → nodes matching any entity (case-insensitive, searches @id, rdfs:label, name, label, title, and recursively all string values)
- `add_knowledge(kg, triple, origin="acquired")` → adds/updates node with provenance metadata (confidence, acquired_date, aec_trigger)
- `add_acquired(kg, triple)` → convenience wrapper for origin="acquired"
- `mark_deprecated(kg, node_id, reason)` → sets origin to "deprecated" with date and reason
- `mark_updated(kg, node_id, updates)` → merges updates and sets origin to "updated"
- `get_nodes_by_origin(kg, origin)` → filtered node list
- `get_core_nodes(kg)`, `get_acquired_nodes(kg)`, `get_deprecated_nodes(kg)` → convenience wrappers
- `save_kg(kg, path)` → write with pretty printing
- `stats(kg)` → counts by origin type

**Imported by:** aether, cli, education (lazy), ingest

---

## Support Files

### education.py (370 lines) — Self-Improvement Loop
**Purpose:** Captures AEC failures and runs research → validate → integrate cycle.

**Queue file:** `education-queue.json` inside each capsule folder
**Valid statuses:** pending → researching → validated/failed → integrated

**Queue Functions:**
- `queue_failure(capsule_path, query, response, aec_result)` → creates record with SHA256-based ID, saves to queue
- `get_queue(capsule_path)` → all records
- `get_pending(capsule_path)` → records with status "pending"
- `get_oldest_pending(capsule_path)` → oldest pending record (sorted by timestamp)
- `update_status(capsule_path, record_id, status, metadata=None)` → update record
- `queue_stats(capsule_path)` → counts by status

**Education Functions:**
- `_parse_json_response(text)` → strips markdown fences, finds JSON array
- `_build_research_prompt(gaps)` → asks LLM for structured S-P-O triples for ungrounded statements
- `educate(capsule_path, record_id, llm_fn)` → the full loop:
  1. Load failure record, verify pending, set to researching
  2. Extract gap statements
  3. Call LLM for structured triples (subject/predicate/object/object_type)
  4. Validate research through AEC (threshold 0.5)
  5. Integrate validated triples into KG as "acquired" origin
  6. Re-evaluate original response against updated KG
  7. Set status to integrated or failed

**Circular import:** Uses lazy imports for aether, kg, aec inside educate()
**Imported by:** aether, cli

---

### ingest.py (326 lines) — Document-to-Capsule Pipeline
**Purpose:** Two modes for converting documents into capsules.

**Gemini Cleanup:**
- `_clean_gemini(text)` → removes backslash escaping damage (\_  \[  \]  \*  \#  \>  \|  \(  \))
- `_fix_json_str(raw)` → fixes escaped periods, hyphens, trailing whitespace, empty values, trailing commas, truncated arrays

**Parsing:**
- `_extract_json_block(text)` → finds first JSON object/array from fenced or bare JSON. Tries raw then _fix_json_str.
- `_split_sections(text)` → splits markdown by ## headers or **Bold** lines. **Code-fence-aware** — ignores lines inside ``` blocks. Skips `## ---` divider lines.
- `_extract_all_objects(text)` → recursive JSON salvage from badly damaged output. Last resort. Finds individual `{}` objects, tries to parse each.
- `_find_section(sections, *keywords)` → first section whose header contains any keyword

**Capsule Creation:**
- `_stamp_capsule(output_path, agent_name, version, kb, kg, persona, definition)` → creates folder with all 5 files using generate_id()

**Mode 1 — Deterministic:**
- `ingest_research(source_path, output_path, agent_name, version)` → parses deep research markdown:
  - Everything before "Knowledge Graph Relationship" header → kb.md
  - JSON in KG section → kg.jsonld (handles @graph, knowledge_graph_triples, bare arrays)
  - JSON in "Structured Persona Meta-data" section → persona.json
  - JSON in "Agent Definition" section → definition.json
  - Falls back to _extract_all_objects() if JSON is too damaged

**Mode 2 — LLM-Assisted:**
- `ingest_document(source_path, output_path, agent_name, agent_type, version, llm_fn)` → three LLM calls:
  - KG extraction prompt → kg.jsonld
  - Persona suggestion prompt → persona.json
  - Definition generation prompt → definition.json
  - Falls back to stubs if llm_fn is None or parsing fails

**Imported by:** cli

---

### llm.py (153 lines) — LLM Wrapper
**Purpose:** Simple call-and-return wrapper for Anthropic/OpenAI/stub providers.

**Functions:**
- `_load_env()` — runs at import time, reads `.env` file from project root into os.environ. Manual parsing (no python-dotenv).
- `estimate_cost(model, tokens_in, tokens_out)` → USD cost estimate
- `call_llm(prompt, provider, model, api_key, max_tokens)` → dict with text, tokens_in, tokens_out, model, cost. Never raises — returns error text on failure.
- `_call_anthropic(prompt, model, api_key, max_tokens)` → uses anthropic SDK
- `_call_openai(prompt, model, api_key, max_tokens)` → uses openai SDK
- `make_llm_fn(provider, model, api_key)` → returns callable matching Capsule's llm_fn interface

**Constants:**
- `DEFAULT_MODELS` — anthropic: claude-sonnet-4-20250514, openai: gpt-4o
- `COST_PER_1K_TOKENS` — rates for claude-sonnet-4, claude-3.5-sonnet, claude-3-opus, claude-3-haiku, gpt-4o, gpt-4o-mini, gpt-4-turbo

**Imported by:** cli

---

### stamper.py (170 lines) — Capsule Factory
**Purpose:** Creates and validates capsule folders.

**Defaults:**
- `DEFAULT_DEFINITION` — all 4 pipeline stages enabled, threshold 0.8
- `DEFAULT_PERSONA` — neutral tone, informative style, no constraints
- `DEFAULT_KB` — placeholder markdown
- `DEFAULT_KG` — empty graph with rdfs+aether context

**Functions:**
- `_write_json(path, data)` → write with indent=2, ensure_ascii=False
- `stamp_empty(name, path, version)` → creates folder with all 5 default files
- `stamp_from_source(name, source_path, output_path, version)` → stamps then overwrites: .md→kb, .jsonld→kg, .json→kg or definition
- `validate_capsule(path)` → checks all files exist and parse correctly, validates manifest has id+version
- `restamp(path, new_version)` → copies capsule to new folder with new version, tracks lineage in manifest (previous_id, previous_version, restamped timestamp)

**Imported by:** cli, ingest

---

### habitat.py (134 lines) — Capsule Registry
**Purpose:** In-memory registry with topic-based message routing.

**Class: Habitat**
- `register(capsule_id, metadata)` — stores id, name, domain_boundaries, scent_subscriptions
- `unregister(capsule_id)` — remove from registry
- `list_capsules()` → all registered capsules with metadata
- `get(capsule_id)` → single capsule metadata
- `route(topic, payload=None)` → list of capsule IDs subscribed to topic. Supports exact match and wildcard prefix (e.g., "market.*" matches "market.analysis")
- `broadcast(topic, payload)` → publishes to all subscribed capsules, logs delivery, trims log at 1000 entries
- `detect_gaps(topic)` → True if no capsule handles this topic
- `get_log(limit=50)` → recent message log
- `stats()` → capsule count, log entries, all topics

**Not currently wired into the pipeline** — designed for multi-capsule orchestration (Phase 3+)
**Imported by:** nobody currently (standalone)

---

### report.py (298 lines) — ASCII Execution Report
**Purpose:** Pretty-prints pipeline results with box-drawing characters.

**Function:**
- `print_report(ctx, aec_result, capsule)` — prints full report with sections:
  - ASCII art header (AETHER banner)
  - Agent Profile (name, ID, version, persona, thresholds, KB/KG sizes)
  - Pipeline Results (4 stages with timing and metrics)
  - AEC Verification (score bar, grounded/ungrounded/persona counts, statement analysis table, knowledge gaps)
  - Telemetry Summary (total/aether/LLM time split, token counts, cost)
  - Footer

**Box Drawing Helpers:** `_box_top`, `_box_bottom`, `_box_row`, `_section_header`, `_subsection`, `_kv_row`
**Windows UTF-8:** Reconfigures stdout encoding on win32

**Imported by:** cli (lazy import with --report full)

---

### cli.py (322 lines) — Command-Line Interface
**Purpose:** argparse entry point for all operations.

**Commands:**
| Command | Function | Description |
|---------|----------|-------------|
| `stamp <name>` | `cmd_stamp` | Create new capsule (empty or from source) |
| `run <capsule> <query>` | `cmd_run` | Run 4-stage pipeline, print AEC results + telemetry |
| `validate <capsule>` | `cmd_validate` | Check capsule has all required files |
| `info <capsule>` | `cmd_info` | Print manifest, KG stats, file sizes |
| `queue <capsule>` | `cmd_queue` | Show education queue stats and pending items |
| `educate <capsule>` | `cmd_educate` | Run self-education on oldest pending failure |
| `verify <text> --reference <kg>` | `cmd_verify` | Standalone AEC verification |
| `ingest-research <source> <name>` | `cmd_ingest_research` | Deterministic deep research → capsule |
| `ingest <source> <name>` | `cmd_ingest` | LLM-assisted document → capsule |

**Options:** --provider (stub/anthropic/openai), --model, --output, --version, --report full, --record-id, --type, --threshold

**Imports from:** aether, stamper, llm, kg, education, ingest, report (lazy)

---

## Test Files

### tests/test_aec_standalone.py (198 lines)
**Purpose:** 10 standalone AEC tests (no pytest, plain asserts).

| Test | What It Verifies |
|------|-----------------|
| 1. Perfect grounding | All values match KG → score 1.0, passed |
| 2. Complete failure | All values contradict KG → score 0.0, failed |
| 3. Mixed grounding | Some match, some don't → 0 < score < 1 |
| 4. All persona | No verifiable values → score 1.0 (all-persona pass) |
| 5. Numeric tolerance | 72.5 vs 72 (within 1%) → grounded |
| 6. Date normalization | "March 15, 1944" matches "1944-03-15" |
| 7. Empty response | → score 0.0, failed |
| 8. Empty KG | Values exist but no KG → all persona (can't verify) |
| 9. Large KG single match | 20 nodes, response mentions one → grounded, passed |
| 10. Formatted numbers | $3,500,000 matches 3500000 |

---

## Example Capsules

### examples/test-agent-v1.0.0-24f8476e
Minimal test capsule. Small KB about Aether framework. 2 KG nodes. Used for framework testing.
Education queue: 1 record (integrated, stub response).

### examples/jefferson
Thomas Jefferson scholar. 204-line KB covering biography, philosophy, presidency, legacy.
779-line KG with detailed nodes (birth, education, presidency, writings, Louisiana Purchase).
Education queue: 1 record (integrated, Louisiana Purchase query → 17 triples learned).

### examples/scholar-buffett
Warren Buffett investment scholar. 172-line KB covering investment philosophy, Berkshire Hathaway, key acquisitions.
703-line KG + 14 acquired nodes from education. Education queue: 8 records (2 integrated, 2 failed, 4 pending).
Most exercised capsule — See's Candies query ran ~8 times with score trajectory from 0.091 to 1.0.

### examples/domain-agent-builder
Agent construction patterns from Anthropic's "Learn Claude Code" tutorial. DSL-based KB (114-line .dsl file with 12 progressive rules s01-s12). Also has .md version for augment stage.
19 core KG nodes (12 rules + 7 concepts). 3 acquired nodes from education.
Persona: instructional, procedural, constraints enforce rule citation and dependency order.

### examples/aether-validator-v1.0.0-d5a16071
Validation-only agent — generate stage DISABLED, threshold 1.0. AEC-as-a-service.
Has its own README explaining the concept.

### examples/domain-sap-cap-v1.0.0-f23f10ee
SAP CAP domain expert. Created via ingest pipeline from 1,386-line research document.
197-line KB, 197-line KG (26 nodes covering CDS modeling, service layers, BTP deployment, ECC migration dates).
First capsule created entirely by the ingest pipeline.

---

## Prompt Templates (prompts/)

### deep-research-v3.1.md (396 lines)
Master template for generating capsule-ready research. 4 agent types (Scholar, Subject, Entity, Domain).
Includes system prompt, precision requirements for AEC compatibility, required report sections per agent type, KG relationship extraction format (S-P-O triples in JSON-LD), persona metadata format, agent definition format, citation requirements.
**This is the prompt that generates the raw material for `ingest_research()`.**

### scholar-jefferson-v3.md (279 lines)
Ready-to-paste prompt for Thomas Jefferson scholar agent. Pre-filled deep-research template.

### scholar-buffett-v3.md (267 lines)
Ready-to-paste prompt for Warren Buffett scholar agent. Pre-filled deep-research template.

### project-summary.md (27 lines)
Utility prompt for analyzing any codebase and producing PROJECT_SUMMARY.md.

---

## Other Files

### AETHER_MEMORY_PHASE_0-2_2026-03-05.md (392 lines)
Phase 0-2 memory document. Comprehensive project context written for session continuity. Covers architecture, pipeline, AEC, KG origins, education loop, CLI commands, key functions, file dependencies, testing, design principles.

### input/SAP CAP Domain Expert Agent Definition.md (1,386 lines)
Source research document for the SAP CAP capsule. Covers CDS modeling, service handlers, BTP deployment, ECC migration timeline, maintenance conditions.

### input/domain-sap-cap-research.md (1,386 lines)
Copy of above used as ingest source.

---

## Dependency Graph

```
cli.py
├── aether.py (Capsule, validate_folder, get_required_files)
│   ├── aec.py (verify)
│   ├── kg.py (query_nodes)
│   └── education.py (queue_failure)
│       ├── [lazy] aether.py (get_required_files)
│       ├── [lazy] kg.py (load_kg, add_knowledge, save_kg, get_nodes)
│       └── [lazy] aec.py (verify)
├── stamper.py (stamp_empty, stamp_from_source, validate_capsule)
│   └── aether.py (generate_id, get_required_files, REQUIRED_SUFFIXES)
├── llm.py (make_llm_fn)
├── kg.py (load_kg, stats)
├── education.py (queue_stats, get_pending, get_oldest_pending, educate)
├── ingest.py (ingest_research, ingest_document)
│   ├── aether.py (generate_id, REQUIRED_SUFFIXES)
│   └── stamper.py (DEFAULT_DEFINITION, DEFAULT_KG, _write_json)
└── [lazy] report.py (print_report)

habitat.py — standalone, not wired into pipeline yet
```

## Line Count Summary

| File | Lines | Category |
|------|-------|----------|
| aether.py | 360 | Core |
| aec.py | 255 | Core |
| kg.py | 219 | Core |
| education.py | 370 | Support |
| ingest.py | 326 | Support |
| cli.py | 322 | Interface |
| report.py | 298 | Interface |
| stamper.py | 170 | Support |
| llm.py | 153 | Support |
| habitat.py | 134 | Core |
| **Total** | **2,607** | |
| tests/test_aec_standalone.py | 198 | Test |
| **Grand Total** | **2,805** | |
