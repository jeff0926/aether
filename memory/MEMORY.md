# AETHER Project Memory

## Overview
**AETHER** = Adaptive Embodied Thinking Holistic Evolutionary Runtime
Minimal agent framework (~1500 lines Python). Standard library + optional `anthropic` SDK.
Author: Jeff Conn (jeff0926). Repo: github.com/jeff0926/aether.git

## Core Concept: Capsules
A capsule = folder with 5 files defining an agent:
- `{id}-manifest.json` (identity), `{id}-definition.json` (behavior/pipeline config)
- `{id}-persona.json` (tone/style/constraints), `{id}-kb.md` (knowledge base)
- `{id}-kg.jsonld` (JSON-LD knowledge graph)
Naming: `{slug}-v{version}-{uid8}` (uid8 = first 8 chars SHA256)

## Architecture (9 files)
| File | Purpose |
|------|---------|
| `aether.py` | Capsule class, 4-stage pipeline (distill/augment/generate/review) |
| `aec.py` | Deterministic entailment check (grounded/ungrounded/persona scoring) |
| `kg.py` | JSON-LD loader, 5 origin types (core/acquired/updated/deprecated/provenance) |
| `stamper.py` | Capsule folder factory, restamp with lineage |
| `habitat.py` | In-memory capsule registry, topic-based routing |
| `llm.py` | LLM wrapper (anthropic/openai/stub), cost estimation |
| `cli.py` | CLI: stamp, run, validate, info, queue, educate, verify, ingest |
| `education.py` | AEC failure queue, self-education loop (research/validate/integrate) |
| `ingest.py` | Document-to-capsule pipeline (deterministic + LLM-assisted) |
| `report.py` | ASCII execution report with box drawing |

## Key Patterns
- AEC score = grounded/(grounded+ungrounded), persona excluded. Default threshold 0.8
- Education: failed AEC -> queue -> LLM research -> validate -> integrate into KG as "acquired"
- Ingest: two modes - `ingest_research` (deterministic, parses deep research MD) and `ingest_document` (LLM-assisted)
- `_clean_gemini()` and `_fix_json_str()` in ingest.py handle Gemini output damage
- Circular import: education.py uses lazy imports for aether/kg/aec

## Example Capsules (in examples/)
- `test-agent-v1.0.0-24f8476e` - minimal test capsule
- `jefferson` - Thomas Jefferson scholar (non-standard naming, no version in folder)
- `scholar-buffett` - Warren Buffett (non-standard naming)
- `aether-validator-v1.0.0-d5a16071` - validation-only (generate disabled, threshold 1.0)
- `domain-agent-builder` - domain agent builder (non-standard naming)
- `domain-sap-cap-v1.0.0-f23f10ee` - SAP CAP domain expert

## Tests
- `tests/test_aec_standalone.py` - 10 AEC tests (no pytest, plain asserts)
- Each module has `if __name__ == "__main__":` self-test block

## Detailed History
See [session-history.md](session-history.md) for complete prompt archive across all 3 sessions.

## State: Phase 2 complete (as of 2026-03-05)
