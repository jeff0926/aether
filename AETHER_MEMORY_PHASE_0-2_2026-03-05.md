# AETHER Project Memory Document
## Phase 0-2 Complete | 2026-03-05 19:45 UTC

---

## Project Overview

**AETHER** = Adaptive Embodied Thinking Holistic Evolutionary Runtime

A minimal agent framework in ~1,500 lines of Python. No frameworks. Standard library only. The `anthropic` SDK is the only optional external dependency.

**Repository**: https://github.com/jeff0926/aether.git
**Author**: Jeff Conn (jeff0926, jeff.m.conn@gmail.com)
**Working Directory**: `C:\Users\I820965\dev\aether`

---

## Core Concept: Capsules

A **capsule** is a folder containing exactly 5 files that define an agent's identity and knowledge:

```
{slug}-v{version}-{uid8}/
├── {id}-manifest.json      # Identity (id, name, version, created)
├── {id}-definition.json    # Behavior (pipeline config, thresholds)
├── {id}-persona.json       # Personality (tone, style, constraints)
├── {id}-kb.md              # Knowledge Base (markdown content)
└── {id}-kg.jsonld          # Knowledge Graph (JSON-LD structured data)
```

**Naming Convention**:
- Folder name = `{slug}-v{version}-{uid8}` (e.g., `jefferson-v1.0.0-a3f7c2d1`)
- All files prefixed with folder name (e.g., `jefferson-v1.0.0-a3f7c2d1-manifest.json`)
- `uid8` = first 8 chars of SHA256 hash for uniqueness

---

## Architecture: 7 Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `aether.py` | ~280 | Capsule class, 4-stage pipeline, telemetry |
| `aec.py` | ~250 | Entailment checking, verification gate |
| `kg.py` | ~180 | JSON-LD loader, 5 origin types |
| `stamper.py` | ~140 | Capsule folder factory |
| `habitat.py` | ~135 | Capsule registry, message routing |
| `llm.py` | ~120 | LLM wrapper, token counting, cost estimation |
| `cli.py` | ~270 | Command-line interface |

**Supporting Files**:
- `education.py` (~250 lines) - Failure queue, self-education loop
- `report.py` (~220 lines) - ASCII execution report

---

## The 4-Stage Pipeline

```
Input → Distill → Augment → Generate → Review → Output
```

1. **Distill**: Extract intent, entities, constraints from input
2. **Augment**: Retrieve relevant context from KB (markdown) and KG (JSON-LD)
3. **Generate**: Build prompt with persona + context, call LLM
4. **Review**: Verify response via AEC (Aether Entailment Check)

Each stage can be enabled/disabled in `definition.json`:
```json
{
  "pipeline": {
    "distill": {"enabled": true},
    "augment": {"enabled": true},
    "generate": {"enabled": true},  // false for validator agents
    "review": {"enabled": true}
  }
}
```

---

## AEC (Aether Entailment Check)

Deterministic verification gate that checks if LLM responses are grounded in the knowledge graph.

**Statement Categories**:
- **GROUNDED**: Contains verifiable values that match KG
- **UNGROUNDED**: Contains verifiable values that DON'T match KG
- **PERSONA**: No verifiable values (qualitative/interpretive)

**Score Formula**: `grounded / (grounded + ungrounded)`
- Persona statements excluded from ratio
- Default threshold: 0.8 (80% grounded minimum)

**Extracted Value Types**:
- Numbers: integers, decimals, comma-grouped (1% tolerance)
- Magnitude numbers: "$25 million" → 25000000
- Percentages: N%, N percent, N pct
- Dates: Years (1700-2099), full dates (Month Day, Year → ISO)
- Names: Capitalized word sequences

---

## Knowledge Graph: 5 Origin Types

```python
ORIGIN_TYPES = ["core", "acquired", "updated", "deprecated", "provenance"]
```

- **core**: Original source knowledge (no tag or `aether:origin: "core"`)
- **acquired**: Learned through self-education (AEC triggers)
- **updated**: Existing node modified with new values
- **deprecated**: Marked as outdated (not deleted)
- **provenance**: External reference metadata

**Key Functions**:
```python
from kg import load_kg, add_knowledge, save_kg, get_nodes, stats
from kg import mark_deprecated, mark_updated, get_nodes_by_origin
```

---

## Self-Education Loop

When AEC fails (score < threshold):
1. Failure queued to `{capsule}/education-queue.json`
2. `educate()` function processes pending failures:
   - Research gaps via LLM (structured JSON output)
   - Validate research through AEC
   - Integrate validated triples into KG as `acquired` origin
   - Re-evaluate original response with updated KG

**Queue Statuses**: `pending` → `researching` → `validated`/`failed` → `integrated`

---

## CLI Commands

```bash
# Capsule management
aether stamp <name> [--source FILE] [--output DIR] [--version 1.0.0]
aether validate <capsule_path>
aether info <capsule_path>

# Pipeline execution
aether run <capsule_path> <query> [--provider PROVIDER] [--model MODEL] [--report full]

# Education queue
aether queue <capsule_path>
aether educate <capsule_path> [--record-id ID] [--provider anthropic]

# Standalone verification
aether verify <text_or_file> --reference <kg_file> [--threshold 0.8]
```

---

## LLM Integration

**Providers**: `anthropic`, `openai`, `stub`

```python
from llm import make_llm_fn, call_llm, estimate_cost, COST_PER_1K_TOKENS

# Returns dict with tokens
result = call_llm(prompt, provider="anthropic")
# {"text": "...", "tokens_in": N, "tokens_out": N, "model": "...", "cost": 0.00X}
```

**Environment**: API keys loaded from `.env` file at project root.

---

## Telemetry

Pipeline tracks timing and counts in `ctx["telemetry"]`:
```python
{
  "start": timestamp,
  "total_ms": 1234.5,
  "stages": {
    "distill": {"time_ms": 0.5, "entities_extracted": 3},
    "augment": {"time_ms": 1.2, "kb_matches": 2, "kg_matches": 1},
    "generate": {"time_ms": 1230.0, "prompt_chars": 500, "tokens_in": 100, "tokens_out": 200},
    "review": {"time_ms": 2.8}
  }
}
```

---

## Example Capsules

Located in `examples/`:

1. **test-agent-v1.0.0-24f8476e** - Minimal test capsule for framework testing
2. **jefferson** - Thomas Jefferson scholar (historical facts, birth dates)
3. **scholar-buffett** - Warren Buffett investment scholar (financial data, acquisitions)
4. **aether-validator-v1.0.0-d5a16071** - Validation-only agent (generate disabled, threshold 1.0)

---

## Key Implementation Details

### Circular Import Prevention
`education.py` uses lazy imports inside `educate()` to avoid circular dependency with `aether.py`:
```python
def educate(...):
    from aether import get_required_files
    from kg import load_kg, add_knowledge, save_kg, get_nodes
    from aec import verify as aec_verify
```

### Windows Encoding
Report and other Unicode output uses UTF-8 reconfiguration:
```python
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
```

### Magnitude Number Extraction
In `aec.py`, magnitude words are processed BEFORE plain numbers:
```python
magnitude = {"million": 1e6, "billion": 1e9, "trillion": 1e12, "thousand": 1e3}
mag_pattern = r'\$?\s*(\d+(?:[.,]\d+)?)\s*(million|billion|trillion|thousand)\b'
```

---

## File Dependencies

```
cli.py
├── aether.py (Capsule, validate_folder, get_required_files)
│   ├── aec.py (verify as aec_verify)
│   ├── kg.py (query_nodes as kg_query)
│   └── education.py (queue_failure)
├── stamper.py (stamp_empty, stamp_from_source, validate_capsule)
├── llm.py (make_llm_fn)
├── kg.py (load_kg, stats)
├── education.py (queue_stats, get_pending, get_oldest_pending, educate)
└── report.py (print_report) [lazy import]
```

---

## Testing

**Standalone AEC tests**: `python tests/test_aec_standalone.py`
- 10 test cases covering grounding, failure, mixed, persona, tolerance, etc.
- No pytest required - simple assert statements

**Module self-tests**: Each module has `if __name__ == "__main__":` test block
```bash
python aether.py <capsule_folder>
python aec.py
python kg.py
python education.py
python llm.py
```

---

## Design Principles

1. **Capsule is a folder.** The framework reads folders. That's it.
2. **Standard library first.** Only add a dependency when stdlib can't do the job.
3. **One file per concern.** No file exceeds 300 lines (target).
4. **No frameworks.** No Pydantic, no async, no CBOR. JSON and plain dicts.
5. **If it's not needed to create, stamp, run, or improve a capsule, it doesn't exist.**

---

## What's NOT Included (by design)

- Async/await
- Vector databases
- Embedding models
- Web UI
- Database persistence
- Multi-turn conversation
- Tool use / function calling
- Streaming responses

These are layers that can be added on top. The core framework stays minimal.

---

## Git Workflow

```bash
# Standard commit format
git commit -m "$(cat <<'EOF'
Brief description of changes

Details...

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

git push
```

---

## Common Operations

### Create a new capsule
```bash
python cli.py stamp "Agent Name" --output ./examples
# Then populate the 5 files manually
```

### Run a query
```bash
python cli.py run examples/capsule-folder "Your query" --provider anthropic
```

### Check AEC on arbitrary text
```bash
python cli.py verify "Text to check" --reference path/to/kg.jsonld
```

### Process education queue
```bash
python cli.py queue examples/capsule-folder    # View queue
python cli.py educate examples/capsule-folder  # Process oldest pending
```

---

## Current State (Phase 2 Complete)

✅ Core pipeline working (distill, augment, generate, review)
✅ AEC verification integrated into review stage
✅ Telemetry with timing, token counts, cost estimation
✅ ASCII execution report (--report full)
✅ Education queue and self-education loop
✅ 5 knowledge origin types
✅ Standalone verify command
✅ Multiple example capsules
✅ Magnitude number extraction ($25 million → 25000000)

---

## Next Steps (Phase 3+)

Potential areas for extension:
- Habitat multi-capsule routing
- Background education daemon
- Capsule versioning and lineage tracking
- Enhanced KB search (beyond paragraph matching)
- Custom AEC gates per capsule

---

## Quick Reference: Key Functions

```python
# aether.py
Capsule(path, llm_fn=None)
capsule.run(query) → ctx dict
generate_id(name, version) → "{slug}-v{version}-{uid8}"

# aec.py
verify(response, kg_nodes, threshold=0.8) → {score, passed, gaps, ...}
split_statements(response) → [statements]
deterministic_gate(statement, kg_nodes) → {matched, method, ...}

# kg.py
load_kg(path) → kg dict
add_knowledge(kg, triple, origin="acquired") → kg
mark_deprecated(kg, node_id, reason) → kg
mark_updated(kg, node_id, updates) → kg
stats(kg) → {total, core, acquired, updated, deprecated, provenance}

# education.py
queue_failure(capsule_path, query, response, aec_result) → record
educate(capsule_path, record_id, llm_fn) → {status, new_score, ...}
get_pending(capsule_path) → [records]

# llm.py
make_llm_fn(provider, model, api_key) → callable
call_llm(prompt, provider, ...) → {text, tokens_in, tokens_out, cost}
```

---

*This document provides complete context for continuing AETHER development. Read this first, then explore the codebase as needed.*
