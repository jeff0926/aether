# Aether Clean Build: Extraction Analysis

**Purpose:** Identify exactly what carries forward from five experimental projects into one clean Aether implementation.

**Target:** ~1,000-1,200 lines of Python. Zero unnecessary dependencies. KISS.

---

## Guiding Principles for the Clean Build

1. **If it's not needed to create, stamp, run, or improve a capsule, it doesn't exist.**
2. **Standard library first.** Only add a dependency when Python stdlib genuinely can't do the job.
3. **One file per concern.** No file exceeds 300 lines. If it does, it's doing too much.
4. **No frameworks.** No Pydantic. No CBOR. No async unless actually needed. JSON, files, folders.
5. **Capsule is a folder.** The framework reads folders. That's it.

---

## Project-by-Project Extraction

### 1. aether-framework (271 lines) — THE SEED

**What it got right:**
- The 4-node DAI pipeline concept (distill → augment → generate → review)
- The Brain Contract as a JSON config file
- The stamper as a simple factory that creates folders with files
- Agent subclassing for specialization (MarketAnalystAgent)

**What carries forward:**
| Component | Source File | Extract |
|-----------|-----------|---------|
| Pipeline concept | `aether_core.py` | The 4-method pattern: distill(), augment(), generate(), review(). Not the class hierarchy. |
| Stamper concept | `aether_stamper.py` | Create folder, write files. The 36-line version is closer to right than the later versions. |
| Brain Contract | `aether_contract.py` | Agent config as a simple JSON dict. NOT Pydantic. Just json.load(). |

**What dies:**
- Pydantic dependency (unnecessary for config validation)
- jsonschema dependency (unnecessary)
- Standalone node files (node_01 through node_04 — duplicates)
- The nul file (Windows artifact)
- The hardcoded working directory pattern

**Verdict:** The original instinct was right. This was the simplest version. The later projects added complexity that needs to be re-earned.

---

### 2. aether-KB-as-body (5,500 lines) — THE BODY PROOF

**What it got right:**
- The "agent IS the UI" concept — capsules carrying their own rendering
- Sovereign capsules with their own signal classification
- The 17-line mirror.html kernel — proof that the client can be almost nothing
- SSE streaming from Python's http.server (stdlib, no framework)
- Signal gate with hysteresis (prevents state thrashing)
- The .psi anatomy files and .gamma signal files as capsule DNA

**What carries forward:**
| Component | Source File | Extract |
|-----------|-----------|---------|
| CapsuleBase pattern | `core/capsule_base.py` | The idea of loading 4 files from a folder. Simplify to 5 files (add manifest). ~50 lines. |
| SignalGate classification | `core/signal_gate.py` | The threshold-based state classification. ~60 lines of the core logic. NOT the hysteresis (premature optimization). |
| SSE streaming pattern | `logic.py` | The http.server + SSE pattern for UI updates. ~40 lines. Only if UI projection is in scope for v1. |
| Capsule folder structure | `capsules/*/` | The pattern of each capsule being a folder with .kg, .psi, .gamma, skin.json, sensor.py. Rename to standard names. |

**What dies:**
- The MANIFEST.json as a separate registry file (manifest belongs inside each capsule)
- habitat.json legacy file
- torrent-worker.js (premature optimization)
- diagnostic.html (1,387 lines of debug UI — build this later when needed)
- The 14 prompt files in prompts/ (working notes, not code)
- D3.js visualization (not core)
- The 5 specific capsule implementations (weather, ecommerce, supply, hr, habitat) — they're demos, not framework

**Verdict:** The body concept is valid and unique. But it's a layer ON TOP of the core. For the clean build, the core capsule runner must work without any UI projection. UI projection becomes an optional capability declared in the manifest.

---

### 3. aether-RD (9,500 lines) — THE COMMUNICATION PROOF

**What it got right:**
- Stigmergic communication (pheromone emit/sniff pattern)
- The 5-part DNA structure (Γ, KB, Ω, Ψ, Λ) — the most complete capsule definition
- The Habitat as an environment/registry for capsules
- Acrylic as a lightweight message format (≤1KB constraint)
- EDSSliver as a lightweight output format (≤1KB constraint)
- The skill.jsonld format for machine-readable skill definitions
- The Anti-Graph Manifesto principles (capsules never call each other directly)
- The 500-byte Aura kernel — extreme minimalism proof

**What carries forward:**
| Component | Source File | Extract |
|-----------|-----------|---------|
| 5-part DNA concept | `capsules/core/capsule_base.py` | The Γ/KB/Ω/Ψ/Λ structure mapped to concrete files. This IS the capsule spec. |
| Habitat registry | `capsules/core/habitat.py` | The register/broadcast/detect_gaps pattern. Simplify to ~80 lines. |
| Pheromone pattern | `capsules/core/capsule_base.py` | emit() and sniff() as the inter-capsule protocol. ~30 lines. |
| skill.jsonld format | `capsules/support/skill.jsonld` | JSON-LD skill definition as a standard. Keep the format, not the implementation. |
| Gap detection | `capsules/core/habitat.py` | detect_signal_gaps() — this feeds the future auto-stamping / self-assembly. |
| Size constraints | conceptual | The ≤1KB constraint for messages and outputs. Enforce in the clean build. |

**What dies:**
- The entire Aura protocol directory (aura/) — 2,000+ lines of TypeScript. This is a separate project.
- UDEx-Atomic-DNA-Technical-Manifest.md (SAP-specific, not core)
- The LangGraph integration in aura/ (framework coupling)
- skill_lab.html (1,454 lines of debug UI)
- The specific capsule implementations (jefferson, sentiment, support, hamilton, knowledge_router) — demos
- The manifesto/base.md (philosophy doc, not code)

**Verdict:** The communication model is the most mature piece across all projects. The pheromone pattern and habitat registry are clean concepts. But the Aura protocol is a separate concern — it's a UI delivery mechanism, not an agent framework component.

---

### 4. aether-core (15,000 lines) — THE FULL FRAMEWORK

**What it got right:**
- AEC with three validated fixes (CanonicalEntailmentJudge, EnrichmentEngine, ActiveRemedySystem)
- The dual-path architecture (reflex <10ms + background deliberation)
- Statement-level attribution (StatementAttribution dataclass)
- Knowledge gap detection (KnowledgeGap dataclass)
- Ghost state with remedy workflow
- The unified LLM client wrapper
- Schema definitions for all capsule files
- Framework adapters (LangChain, LangGraph, CrewAI)
- The stamp CLI tool

**What carries forward:**
| Component | Source File | Lines to Extract | Notes |
|-----------|-----------|-----------------|-------|
| AEC core logic | `aether/core/aec.py` | ~200 of 1,954 | The verify() method, threshold check, score calculation. Strip the three fixes down to essentials. |
| CanonicalEntailmentJudge | `aether/core/aec.py` | ~100 | Entity extraction + canonical comparison. This is the deterministic gate. Proven. Keep it. |
| ActiveRemedySystem concept | `aether/core/aec.py` | ~50 | The ghost state → queue → research → re-validate pattern. Simplify to a queue interface. |
| StatementAttribution | `aether/core/data_types.py` | ~20 | The per-statement grounding dataclass. Use a simple dict or namedtuple, not a full dataclass hierarchy. |
| KnowledgeGap | `aether/core/data_types.py` | ~15 | Gap detection output. Simple dict. |
| Capsule loading | `aether/core/loaders.py` | ~80 of 1,047 | ManifestLoader + KBLoader + KGLoader only. Kill the rest (VectorDoc, ScholarKB, SkillKB, PlasticLoader, StampedKGLoader, EnrichmentEngine). |
| LLM client | `aether/core/llm_client.py` | ~60 of 130 | The wrapper pattern. One function: call_llm(prompt, provider, model). Provider-agnostic. |
| Stamp CLI | `aether/cli/stamp.py` | ~80 of 394 | Validate folder has required files, assign ID, write manifest. |
| JSON schemas | `schemas/*.json` | keep as-is | Reference schemas for definition.json, persona.json, kb.json, kg.json. |

**What dies:**
- `aether/core/dai_pulse.py` (530 lines) — The dual-path engine is overbuilt. Replace with a simple sequential pipeline function: distill → augment → generate → review. ~40 lines.
- `aether/core/data_types.py` (663 lines) — Massive dataclass hierarchy with CBOR serialization. Replace with plain dicts and namedtuples. ~30 lines for the ones that matter.
- `aether/core/signal_bus.py` (143 lines) — Replace with the simpler Habitat pattern from aether-RD.
- `aether/adapters/` (entire directory, ~1,300 lines) — All four adapters. These are important but they're NOT core. They're plugins that come later.
- `aether/ui/` (entire directory, ~960 lines) — EDS, streaming, tokens. This is the UI projection layer. Not core.
- `aether/llm/` (most of directory) — The provider abstraction with Anthropic and OpenAI implementations is overengineered for v1. One simple function that calls the anthropic SDK is enough.
- All three example capsules (hamilton, market_analyst, weather) — Rebuild one clean example capsule for the new structure.
- `aether/core/loaders.py` — 1,047 lines with 9 different loaders. Needs 3: manifest, kb, kg.
- CBOR dependency — unnecessary. JSON is fine.
- pyld dependency — unnecessary for v1. JSON-LD is just JSON with @context.
- numpy dependency — only needed for TF-IDF vectors, which are cut from v1.
- aiofiles/aiohttp — async not needed for v1.
- EnrichmentEngine (Fix 2) — the TF-IDF enrichment with canonical tags. Interesting but only achieves 50-70% accuracy. Cut it. The CanonicalEntailmentJudge (Fix 1) handles the deterministic cases that matter.

**Verdict:** This is where the most value lives, but it's buried under 15,000 lines of overengineering. The AEC module alone is 1,954 lines when the core logic is ~200. The extraction ratio is roughly 600 useful lines out of 15,000. That's the cost of experimentation — now we harvest.

---

### 5. sem-platform (25,000 lines) — THE WORK PROJECT

**What carries forward into Aether:** Nothing directly. This is a separate project (the team's sales agent platform). However:

**What it informs:**
- The SAP CAP integration pattern — Aether must be pluggable into CAP applications
- The MCP tool pattern — 18 tools built as a registry. This validates the skill-as-tool concept.
- The A2A agent card pattern (`app/.well-known/agent-card.json`) — capsules need a similar discovery mechanism
- The workspace manifest pattern (sem.yaml as single source of truth) — validates the manifest-per-capsule approach
- The pain points: LangGraph + LangChain + CopilotKit + React + UI5 + AG-UI = the complexity Aether replaces

**What dies:** All 25,000 lines stay in sem-platform. Aether is separate. But the clean Aether build should be demonstrably pluggable into a CAP application.

---

## The Clean Build: File Structure

```
aether/
├── aether.py              # Core: Capsule class, pipeline runner (~250 lines)
├── aec.py                 # AEC: Verify, score, threshold, deterministic gate (~250 lines)
├── stamper.py             # Stamper: Create capsule folders from source material (~150 lines)
├── kg.py                  # KG: JSON-LD loader, subgraph query, core/acquired zones (~150 lines)
├── habitat.py             # Habitat: Capsule registry, pheromone routing, gap detection (~100 lines)
├── llm.py                 # LLM: Simple call_llm() wrapper (~60 lines)
├── cli.py                 # CLI: stamp, run, validate commands (~100 lines)
├── schemas/               # JSON schemas for capsule files
│   ├── definition.json
│   ├── persona.json
│   ├── kb.json
│   └── kg.json
├── examples/
│   └── thomas_jefferson/  # One clean example capsule
│       ├── manifest.json
│       ├── definition.json
│       ├── persona.json
│       ├── kb.md
│       └── kg.jsonld
├── skills/                # Built-in skills (each is a capsule)
│   └── kg_drawio/         # The skill we built last night
│       ├── skill.md
│       └── kg_drawio.py
├── README.md
└── requirements.txt       # Minimal: anthropic SDK only (optional)
```

**Total estimated lines: ~1,060**

---

## Dependencies

### Required (stdlib only)
- `json` — config loading
- `os` / `pathlib` — file operations
- `re` — entity extraction in deterministic gate
- `hashlib` — capsule ID generation
- `http.server` — only if running standalone
- `argparse` — CLI

### Optional (one external package)
- `anthropic` — only if calling Claude for generation

### Killed
- pydantic (use plain dicts + json.load)
- cbor2 (use JSON)
- pyld (JSON-LD is just JSON)
- numpy (no vectors in v1)
- aiofiles / aiohttp (no async needed)
- jsonschema (validate manually or not at all in v1)

---

## Extraction Checklist for Claude Code

When you take this to Claude Code, here's the order:

1. **Create the repo and folder structure** as shown above
2. **Write aether.py first** — Capsule class that loads 5 files from a folder and runs the pipeline
3. **Write aec.py second** — Port the CanonicalEntailmentJudge and the 60/40 scoring from aether-core/aec.py. Strip everything else.
4. **Write kg.py third** — JSON-LD loader with core/acquired zone separation
5. **Write stamper.py fourth** — Given a source document, create the capsule folder
6. **Write habitat.py fifth** — Registry and pheromone routing
7. **Write llm.py sixth** — Simple wrapper, can be a stub initially
8. **Write cli.py last** — Ties it all together
9. **Create the Thomas Jefferson example capsule** using the v2 deep research prompt output
10. **Move the kg_drawio skill** into skills/

Each file gets written, tested, and verified before moving to the next. No file depends on a file that hasn't been written yet (except aether.py which everything imports from).

---

## What to Reference in Each Existing Project

| New File | Reference From | What to Look At |
|----------|---------------|-----------------|
| `aether.py` | aether-framework/aether_core.py | The run() method pattern. Simplify. |
| `aether.py` | aether-KB-as-body/core/capsule_base.py | The file-loading pattern. Simplify. |
| `aether.py` | aether-RD/capsules/core/capsule_base.py | The 5-part DNA structure. Map to files. |
| `aec.py` | aether-core/aether/core/aec.py | CanonicalEntailmentJudge + verify() + 60/40 scoring. Extract ~200 lines from 1,954. |
| `kg.py` | aether-core/aether/core/loaders.py | KGLoader only. ~40 lines from 1,047. |
| `kg.py` | This conversation | Core/acquired/provenance zone design. New code. |
| `stamper.py` | aether-framework/aether_stamper.py | The 36-line version. Expand slightly. |
| `stamper.py` | aether-core/aether/cli/stamp.py | The validation logic. ~40 lines from 394. |
| `habitat.py` | aether-RD/capsules/core/habitat.py | Register, broadcast, detect_gaps. ~80 lines from 273. |
| `habitat.py` | aether-KB-as-body/core/signal_gate.py | SignalBus publish/subscribe. ~30 lines from 177. |
| `llm.py` | aether-core/aether/core/llm_client.py | The wrapper concept. Simplify to one function. |
| `cli.py` | aether-core/aether/cli/stamp.py | The CLI pattern. Simplify. |

---

*This document is the bridge between experimentation and production. Every line in the clean build earns its place.*
