# Aether Clean Build: Extraction Analysis

**Recovered from git history** — this document was deleted in commit 0713540 (Phase 2).
It was the original architectural design document that guided the clean build.

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
| SignalGate classification | `core/signal_gate.py` | The threshold-based state classification. ~60 lines of the core logic. NOT the hysteresis. |
| SSE streaming pattern | `logic.py` | The http.server + SSE pattern for UI updates. ~40 lines. Only if UI projection is in scope for v1. |
| Capsule folder structure | `capsules/*/` | The pattern of each capsule being a folder with .kg, .psi, .gamma, skin.json, sensor.py. |

**What dies:**
- The MANIFEST.json as a separate registry file
- habitat.json legacy file
- torrent-worker.js (premature optimization)
- diagnostic.html (1,387 lines of debug UI)
- The 14 prompt files in prompts/ (working notes, not code)
- D3.js visualization (not core)
- The 5 specific capsule implementations (weather, ecommerce, supply, hr, habitat)

**Verdict:** The body concept is valid and unique. But it's a layer ON TOP of the core. UI projection becomes an optional capability declared in the manifest.

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
| skill.jsonld format | `capsules/support/skill.jsonld` | JSON-LD skill definition as a standard. Keep the format. |
| Gap detection | `capsules/core/habitat.py` | detect_signal_gaps() — feeds future auto-stamping / self-assembly. |
| Size constraints | conceptual | The ≤1KB constraint for messages and outputs. |

**What dies:**
- The entire Aura protocol directory (aura/) — 2,000+ lines of TypeScript
- UDEx-Atomic-DNA-Technical-Manifest.md (SAP-specific, not core)
- The LangGraph integration in aura/ (framework coupling)
- skill_lab.html (1,454 lines of debug UI)
- The specific capsule implementations (jefferson, sentiment, support, hamilton, knowledge_router)
- The manifesto/base.md (philosophy doc, not code)

**Verdict:** The communication model is the most mature piece. The pheromone pattern and habitat registry are clean concepts. But the Aura protocol is a separate concern.

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
| AEC core logic | `aether/core/aec.py` | ~200 of 1,954 | verify() method, threshold check, score calculation. |
| CanonicalEntailmentJudge | `aether/core/aec.py` | ~100 | Entity extraction + canonical comparison. The deterministic gate. |
| ActiveRemedySystem concept | `aether/core/aec.py` | ~50 | ghost state → queue → research → re-validate. Simplify to queue. |
| StatementAttribution | `aether/core/data_types.py` | ~20 | Per-statement grounding. Simple dict. |
| KnowledgeGap | `aether/core/data_types.py` | ~15 | Gap detection output. Simple dict. |
| Capsule loading | `aether/core/loaders.py` | ~80 of 1,047 | ManifestLoader + KBLoader + KGLoader only. |
| LLM client | `aether/core/llm_client.py` | ~60 of 130 | One function: call_llm(prompt, provider, model). |
| Stamp CLI | `aether/cli/stamp.py` | ~80 of 394 | Validate folder, assign ID, write manifest. |

**What dies:**
- `dai_pulse.py` (530 lines) — Replace with simple sequential pipeline (~40 lines)
- `data_types.py` (663 lines) — Replace with plain dicts (~30 lines)
- `signal_bus.py` (143 lines) — Replace with simpler Habitat pattern
- `adapters/` (entire directory, ~1,300 lines) — Plugins for later
- `ui/` (entire directory, ~960 lines) — UI projection layer. Not core.
- `llm/` (most of directory) — Overengineered for v1
- CBOR, pyld, numpy, aiofiles/aiohttp dependencies
- EnrichmentEngine (Fix 2) — Only achieves 50-70% accuracy. Cut it.

**Verdict:** Most value lives here, buried under 15,000 lines of overengineering. AEC module is 1,954 lines when core logic is ~200. Extraction ratio: ~600 useful lines out of 15,000.

---

### 5. sem-platform (25,000 lines) — THE WORK PROJECT

**What carries forward into Aether:** Nothing directly. Separate project (team's sales agent platform).

**What it informs:**
- SAP CAP integration pattern — Aether must be pluggable into CAP applications
- MCP tool pattern — 18 tools built as a registry. Validates skill-as-tool concept.
- A2A agent card pattern — capsules need similar discovery mechanism
- Workspace manifest pattern (sem.yaml) — validates manifest-per-capsule approach
- Pain points: LangGraph + LangChain + CopilotKit + React + UI5 + AG-UI = the complexity Aether replaces

---

## Total Source Material

| Project | Lines | Lines Extracted | Ratio |
|---------|-------|----------------|-------|
| aether-framework | 271 | ~100 | 37% |
| aether-KB-as-body | 5,500 | ~180 | 3% |
| aether-RD | 9,500 | ~240 | 3% |
| aether-core | 15,000 | ~600 | 4% |
| sem-platform | 25,000 | 0 | 0% |
| **Total** | **55,271** | **~1,120** | **2%** |

*This document is the bridge between experimentation and production. Every line in the clean build earns its place.*
