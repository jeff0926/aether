# AETHER Session History — Complete Prompt Archive

## Session 1 (7ab5d0c8) — 2026-03-06
### Theme: Core pipeline testing, CLI, domain-agent-builder capsule

**PROMPT 1**: Test Buffett capsule with real API
```
Read AETHER_MEMORY_PHASE_0-2_2026-03-05.md and confirm you understand the project context. Then run:
echo $ANTHROPIC_API_KEY | head -c 10
Then run:
python cli.py run examples/scholar-buffett "How much did Berkshire pay for See's Candies?" --provider anthropic
```
Result: Pipeline ran. Anthropic SDK installed mid-session. AEC passed but queued education failures.

**PROMPT 2**: Educate Buffett capsule
```
python cli.py educate examples/scholar-buffett --provider anthropic
```
Result: Education loop integrated 3 triples, score improved from 0.444 to 1.0.

**PROMPT 3**: Re-test Buffett with two queries
```
python cli.py run examples/scholar-buffett "How much did Berkshire pay for See's Candies?" --provider anthropic
python cli.py run examples/scholar-buffett "What is Berkshire Hathaway's compound annual growth rate?" --provider anthropic
```
Result: See's Candies AEC 0.625 (improved but still failing). CAGR query ran.

**PROMPT 4**: Build CLI + .env loading (TWO TASKS)
```
TASK 1: Add .env loading to llm.py
  - _load_env() function, manual .env parsing, no python-dotenv
  - Create .gitignore (.env, __pycache__/, *.pyc)

TASK 2: Build cli.py. ~100 lines. argparse subcommands.
  Commands: stamp, run, validate, info
  Imports from aether, stamper, llm, kg, aec
```
Result: Both already implemented from prior work. Confirmed working.

**PROMPT 5-8**: Build domain-agent-builder capsule (sent 3x, was cut off first time)
```
Create examples/domain-agent-builder/ — a Domain Expert with DSL-based KB
Encodes Anthropic's "Learn Claude Code" 12-session tutorial as structured rules

Files created:
1. domain-agent-builder-manifest.json (Domain Expert, v1.0.0)
2. domain-agent-builder-kb.dsl — 12 progressive rules:
   s01: "One loop & Bash is all you need" (REQUIRES nothing)
   s02: "Adding a tool means adding one handler" (REQUIRES s01)
   s03: "An agent without a plan drifts" (REQUIRES s01)
   s04: "Break big tasks down; each subtask gets a clean context" (REQUIRES s01, s03)
   s05: "Load knowledge when you need it, not upfront" (REQUIRES s01, s02)
   s06: "Context will fill up; you need a way to make room" (REQUIRES s01, s05)
   s07: "Break big goals into small tasks, order them, persist to disk" (REQUIRES s03, s04)
   s08: "Run slow operations in the background; the agent keeps thinking" (REQUIRES s01, s02)
   s09: "When the task is too big for one, delegate to teammates" (REQUIRES s04, s07)
   s10: "Teammates need shared communication rules" (REQUIRES s09)
   s11: "Teammates scan the board and claim tasks themselves" (REQUIRES s09, s10)
   s12: "Each works in its own directory, no interference" (REQUIRES s11)
3. domain-agent-builder-definition.json (pipeline config, domain boundaries, AEC gates)
4. domain-agent-builder-persona.json (instructional, procedural, dependency-aware)
5. domain-agent-builder-kg.jsonld (19 nodes: 12 Rule + 7 Concept, with dependency edges)
Also created domain-agent-builder-kb.md (markdown version for augment stage)
```
Result: Capsule created with 6 files. Validation passed. 19 core KG nodes.

**PROMPT 10-12**: Test domain-agent-builder with real queries
```
python cli.py run examples/domain-agent-builder "How do I add background execution to my agent?" --provider anthropic
python cli.py run examples/domain-agent-builder "What do I need before I can delegate tasks to teammates?" --provider anthropic
```
Result: Background execution scored 0.5 initially (model ignored DSL rules). Delegation scored 0.889 then 1.0.

**PROMPT 13**: Add persona constraints injection to generate()
```
In aether.py generate(), add constraints from persona.json to prompt:
    constraints = self.files["persona"].get("constraints", [])
    if constraints:
        parts.append("\nCONSTRAINTS:")
        for c in constraints: parts.append(f"- {c}")
```
Result: Constraints appeared in prompt but model still ignored them (0.5). Constraints too terse.

**PROMPT 14**: Two generate() fixes — expand constraints + enrich KG display
```
FIX 1: Expand constraint slugs into natural language:
    expanded = c.replace("-", " ").strip()
    parts.append(f"- {expanded}")

FIX 2: Show KG node properties, not just labels:
    Before: "- Rule s08"
    After:  "- Rule s08 (description: daemon threads run commands; requires: [s01, s02]; pattern_type: background)"
    Before: "- See's Candies"
    After:  "- See's Candies (year: 1972; purchase_price: 25000000; revenue_at_acquisition: 31300000)"
```
Result: Domain-agent-builder jumped to AEC 1.0. Buffett improved significantly.

**PROMPT 15**: Add keyword extraction to distill()
```
Problem: augment misses KG nodes because distill() only extracts capitalized entities.
"background execution" has no capitalized words → no KG matches.

Fix: Add stop-word-filtered keyword extraction alongside entity extraction.
    keywords = [w.lower() for w in words if w.lower() not in stop_words and len(w) > 2]
    ctx["distilled"]["keywords"] = keywords

In augment(), use search_terms = entities + keywords for both KB and KG search.
```
Result: s08 now found for "background execution". Buffett finds CAGR nodes. Scores improved.

**PROMPT 16-17**: Educate and re-test domain-agent-builder
```
python cli.py educate examples/domain-agent-builder --provider anthropic
python cli.py run examples/domain-agent-builder "How do I add background execution to my agent?" --provider anthropic
```
Result: Score trajectory for background execution query:
  0.5 → 0.667 → 0.714 → 0.857 (PASSED!)

**PROMPT 18**: Commit all
```
commit all
```
Result: Committed as "Add domain-agent-builder capsule, keyword extraction, enriched KG prompts"

---

## Session 2 (478c9a25) — 2026-03-07
### Theme: Prompt templates, ingest pipeline, SAP CAP agent

**PROMPT 2**: Populate prompts/ directory
```
Create prompts/README.md with inventory table
Create prompts/project-summary.md (codebase analysis prompt)
Copy deep-research-v3.1.md, scholar-jefferson-v3.md, scholar-buffett-v3.md from IGNORE/
```
Result: README and project-summary created. Deep research + scholar prompts found and copied from IGNORE/.

**PROMPT 4**: Clean up and commit prompts
```
Remove prompts/Aether_Deep_Research_Prompt_v3.md (duplicate with old naming)
git add prompts/ && git commit && git push
```
Result: 5 prompt files committed.

**PROMPT 5**: Build ingest.py (~200 lines)
```
Two functions:

1. ingest_research(source_path, output_path, agent_name, version="1.0.0") -> Path
   DETERMINISTIC — no LLM needed.
   Parse deep research markdown with sections:
   - Research body → kb.md
   - Knowledge Graph Relationships (JSON) → kg.jsonld
   - Structured Persona Meta-data (JSON) → persona.json
   - Agent Definition (JSON) → definition.json
   Handle Gemini markdown escaping damage (\_  \[  \]  \*  \#)

2. ingest_document(source_path, output_path, agent_name, ..., llm_fn=None) -> Path
   Three LLM calls: KG extraction, persona suggestion, definition generation
   Falls back to stubs if llm_fn is None or JSON parse fails

CLI commands: aether ingest-research, aether ingest
```
Result: ingest.py created (253 lines). Both modes working.

**PROMPT 6**: Test ingest on Jefferson research paper
```
python cli.py ingest-research IGNORE/phase-1/"Research Paper on Thomas Jefferson.md" "scholar-jefferson-test" --output ./test-ingest
```
Result: IGNORE/ directory not present in codespace (local-only).

**PROMPT 7**: Preemptive parser fix for SAP CAP
```
_split_sections() must be code-fence-aware.
Don't scan whole file for JSON — split into sections FIRST,
then extract JSON only from correct sections (KG, Persona, Definition).
```
Result: _split_sections() rewritten line-by-line with in_fence tracking.

**PROMPT 8**: Ingest SAP CAP research paper
```
cp input/SAP_CAP_Domain_Expert_Agent_Definition.md input/domain-sap-cap-research.md
python cli.py ingest-research input/domain-sap-cap-research.md "domain-sap-cap" --output ./examples
```
Result: Multiple rounds of parser fixes for Gemini output:
- **Bold** headers instead of ## headers
- Bare JSON (no code fences) with escaped underscores
- Trailing commas, malformed values
- Truncated JSON arrays
- _fix_json_str() and _extract_all_objects() (salvage mode) added
Final: SAP CAP capsule created with 26 KG nodes.

**PROMPT 9**: Validate and test SAP CAP capsule
```
python cli.py validate examples/domain-sap-cap
python cli.py info examples/domain-sap-cap
python cli.py run examples/domain-sap-cap "What is the CDS modeling approach in CAP?" --provider anthropic
```
Result: Valid capsule. 26 KG nodes. CDS query ran successfully.

**PROMPT 10**: Check KG stats
```
python -c "from kg import load_kg, stats; print(stats(load_kg('examples/domain-sap-cap/domain-sap-cap-kg.jsonld')))"
```

**PROMPT 11-12**: Test SAP CAP with ECC migration queries
```
python cli.py run examples/domain-sap-cap "How does CAP handle the migration from SAP ECC given that mainstream support ends December 31 2027?" --provider anthropic
python cli.py run examples/domain-sap-cap "What is the end date for mainstream SAP ECC support and what are the maintenance conditions between 2028 and 2030?" --provider anthropic
```
Result: Both queries ran. AEC verified dates against KG.

**PROMPT 13**: Commit and push
```
git add -A
git commit -m "SAP CAP agent via ingest pipeline, education improvements, prompt v3.1"
git push
```
Result: Committed. HEAD at 7519fb0.

---

## Session 3 (07569d13) — 2026-03-07
### Theme: Resume, full codebase review, history recovery

PROMPT 1: --resume
PROMPT 2: read all of the files and get acquainted
PROMPT 3: find project memory/history
PROMPT 4: extract full prompts from conversation history

---

## Key Metrics Across Sessions

| Capsule | Query | Initial AEC | Final AEC | Method |
|---------|-------|-------------|-----------|--------|
| scholar-buffett | See's Candies price | 0.444 | 0.625 | education loop |
| domain-agent-builder | background execution | 0.5 | 0.857 | constraints + keywords + KG enrichment + education |
| domain-agent-builder | delegate to teammates | 0.889 | 1.0 | constraints + KG enrichment |
| domain-sap-cap | CDS modeling | n/a | passed | ingest pipeline |

## Key Code Changes Made
1. `llm.py`: Added _load_env() for .env loading
2. `aether.py generate()`: Added persona constraints injection (expanded slugs)
3. `aether.py generate()`: Enriched KG display (properties not just labels)
4. `aether.py distill()`: Added keyword extraction alongside entity extraction
5. `aether.py augment()`: Uses entities + keywords for search
6. `ingest.py`: Full document-to-capsule pipeline (253 lines)
7. `ingest.py _split_sections()`: Code-fence-aware section splitting
8. `ingest.py _fix_json_str()`: Gemini JSON damage repair
9. `ingest.py _extract_all_objects()`: Recursive JSON salvage from broken output
10. `cli.py`: Added ingest-research and ingest commands
