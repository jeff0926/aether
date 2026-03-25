# AETHER: Adaptive Embodied Thinking — Holistic Evolutionary Runtime

**Self-educating. Self-healing. Persona-aware. Grounded. Portable. Agent as skill.**

> *What if we built AI agents the way autonomous robots are built?*

Skill.md in. Smarter skill.md out. Works with Claude, GPT-4, Gemini, Copilot, or any LLM.
The model is replaceable. The skill is the asset.

> Zenodo: https://zenodo.org/records/19212829
> DOI: 10.5281/zenodo.19212829
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-864%20Zeros%20LLC-purple.svg)](LICENSE)
[![Stdlib only](https://img.shields.io/badge/dependencies-stdlib%20only-green.svg)]()

---

## The Idea

During the 2024–2025 high school robotics competition season, a pattern emerged: the autonomous robot already had everything an AI agent needs but currently lacks.

A compiled navigation mesh. A persistent identity. A communication protocol. A terrain-mapping mechanism that learned from failure. A safety stop that halted rather than guessing.

AETHER applies that pattern to software agents. Every design decision traces to a robot subsystem:

| Robot | AETHER capsule |
|-------|----------------|
| Compiled navigation mesh | `kg.jsonld` — compiled KG, AEC verifies against this |
| Operator field notes | `kb.md` — unstructured knowledge base |
| Team identity | `persona.json` — tone, traits, persists across any LLM |
| Communication protocol | `definition.json` — pipeline config, domain boundaries |
| Serial number + lineage | `manifest.json` — UID, version, lineage chain |
| Terrain mapping mechanism | Self-education loop — gaps researched, triples integrated |
| Safety stop | GHOST state — configurable halt on AEC failure |

The pattern is not metaphor. It is the engineering specification.

---

## What It Does

AETHER creates, runs, verifies, and improves **capsules** — self-contained agents stored as 5-file folders. Point any capsule at any LLM. The knowledge, identity, verification rules, and persona travel intact.

```
SKILL.md (flat markdown) → DAG → verified capsule (5 files)
                                        ↓
                              DAGR pipeline on every query
                                        ↓
                              AEC verifies every response
                                        ↓
                           failure → self-education → improvement
```

**The model did not change. The skill did.**

---

## Quick Start

```bash
git clone https://github.com/jeff0926/aether.git
cd aether

# Optional: set your API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Run a capsule
python cli.py run examples/jefferson "When was Jefferson born?" --provider anthropic

# See AEC verification in action
python cli.py run examples/frontend-design "How should I approach typography for a luxury brand?" \
  --provider anthropic --report full

# Ingest any SKILL.md into a verified capsule (Anthropic, Copilot, any platform)
python cli.py ingest-skill path/to/SKILL.md --output ./examples --provider anthropic

# Auto-route a query to the right agent
python cli.py orchestrate "What is Buffett's investment philosophy?" \
  --registry ./examples --provider anthropic

# Trigger self-education on a failure
python cli.py educate examples/jefferson --item 0 --provider anthropic

# Launch the dashboard
python dashboard.py  # http://localhost:8864
```

**Requirements:** Python 3.11+ · stdlib only · `anthropic` SDK optional (stub provider works without it)

---

## The Capsule: 5 Files = Complete Agent

```
frontend-design-v1.0.0-ff6ab491/
├── frontend-design-v1.0.0-ff6ab491-manifest.json     UID · version · lineage
├── frontend-design-v1.0.0-ff6ab491-definition.json   pipeline config · AEC thresholds · GHOST mode
├── frontend-design-v1.0.0-ff6ab491-persona.json      tone · style · traits · identity
├── frontend-design-v1.0.0-ff6ab491-kb.md             knowledge base (markdown + provenance URLs)
└── frontend-design-v1.0.0-ff6ab491-kg.jsonld         73 typed KG nodes · 180 triples
```

Copy the folder. Email it. Check it into Git. Point it at any LLM. The complete agent is operational anywhere.

**The capsule is not an agent that has skills. The capsule is a skill that is an agent.**

---

## The Pipeline: DAG + DAGR

### DAG — Distilled Augmented Generation (creation)

```
DAG(S, K, P) → C

  S = source material (SKILL.md, research doc, any markdown)
  K = knowledge distillation (typed KG nodes + KB content)
  P = persona extraction (tone, traits, identity)
  C = capsule (5-file directory)
```

One CLI command. Seconds to complete. All 17 Anthropic official Claude Code skills ingested — frontend-design fully validated as the reference implementation (3,956 chars → 73 typed KG nodes, 180 triples).

### DAGR — runtime execution (query → verified response)

```
DAGR(Q) = R( G( A( D(Q), KG, KB ), Π ), compile(KG) )

  D = Distill:  extract intent, entities, format preference  (<0.1ms)
  A = Augment:  retrieve KB paragraphs + KG nodes            (0.1–0.5ms)
  G = Generate: LLM call with persona + context              (LLM latency)
  R = Review:   AEC verifies response against compiled KG    (<2ms)
```

Framework overhead excluding LLM: **< 3ms**. All latency is LLM response time.

---

## AEC — Agent Education Calibration

AEC is the verification engine. It compiles the knowledge graph into executable policy checkers **once at capsule load**, then verifies every response in milliseconds.

### Three verification layers

**Layer 1 — Compiled pattern matching (deterministic)**
KG node labels compile into token sets. Statement matching via set intersection.
Anti-pattern blacklist for instant violation detection. O(|tokens|) per statement.

```
"Use CSS variables for consistency"
→ tokens: {css, variables, consistency}
→ detector patterns for rule:use_css_variables: {css, variables, consistency, centralized}
→ coverage: 3/4 = 0.75 ≥ threshold 0.50 → GROUNDED
```

**Layer 2 — Type-driven LLM operators (fallback only)**
The node's `@type` determines the verification question. Rules check compliance.
AntiPatterns check violations. Fires only when Layer 1 is inconclusive. Max 3 LLM calls per response.

**Layer 3 — Edge policy traversal (deterministic)**
Compiled `avoids`, `requires`, `contradicts` edges catch compositional violations.
```
concept:typography → avoids → antipattern:overused_fonts {inter, roboto, arial}
statement mentions "Inter" → VIOLATION via graph path
```

### Scoring

```
score = grounded / (grounded + ungrounded)
```
Persona statements excluded. Default threshold: 0.80.

### Measured performance

| Operation | Time |
|-----------|------|
| compile_kg() — 73 nodes | 0.62ms |
| Layer 1 per statement | 0.1–0.3ms |
| Layer 3 per statement | <0.5ms |
| Full verification — 6 statements (no Layer 2) | <2ms |
| Total framework overhead (excl. LLM) | <3ms |

No embeddings. No vector database. No GPU. Runs on standard consumer hardware.

### Proof point: frontend-design skill verification

Anthropic's frontend-design SKILL.md ingested via DAG → 73-node capsule.
Query: *"How should I approach typography for a luxury brand?"*

| Metric | Value |
|--------|-------|
| Statements evaluated | 8 |
| Grounded (Layer 1 + 2) | 6 |
| Anti-pattern violation caught | 1 ("Inter" in blacklist) |
| Persona | 1 |
| **AEC score** | **0.857 — PASS** |

---

## Self-Education Loop

When AEC fails, the agent learns:

```
1. QUEUE      AEC failure + gap list enters education queue
2. RESEARCH   LLM researches specific gaps → proposed triples
3. VALIDATE   Each triple verified through AEC at threshold 0.5
4. CONTRADICT Contradiction gate: core nodes hold absolute veto
5. INTEGRATE  Surviving triples added to KG as origin: acquired
6. RE-EVALUATE Original query re-run against expanded KG
```

### Proof point: Jefferson self-education

| | Before | After |
|--|--------|-------|
| Query | "What happened during the Louisiana Purchase?" | same |
| AEC score | 0.143 | **0.889** |
| Grounded | 1 | 8 |
| KG nodes | 51 | 68 |
| Human intervention | — | **zero** |

17 triples acquired. 5 rejected (3 failed AEC validation, 2 duplicates). 0 core conflicts.

**The model did not change. The skill did.**

---

## Capsule Inventory (33 capsules)

| Category | Count | Examples |
|----------|-------|---------|
| Skill Agents | 17 | frontend-design · brand-guidelines · claude-api · doc-coauthoring · skill-creator · mcp-builder · +11 Anthropic skills |
| Executive Advisors | 8 | CEO · CTO · CPO · CFO · CISO · CLO · Lead Dev · Lead Data Arch |
| Scholars | 2 | Thomas Jefferson · Warren Buffett |
| Validators | 2 | AETHER Validator · Test Agent |
| Domain Experts | 3 | Domain Agent Builder · Domain Expert CAP · Agent Performance Mgr |
| Infrastructure | 1 | Orchestrator (router) |

All created via DAG from SKILL.md files, research documents, or collaborative extraction.
All run through the same DAGR pipeline and AEC verification.

---

## Orchestrator

The orchestrator is itself a capsule. It routes queries automatically to the right specialist.

```bash
# Auto-route — user doesn't need to know which agent exists
python cli.py orchestrate "When was Jefferson born?" --registry ./examples --provider anthropic
# → Routes to: Thomas Jefferson Scholar Agent (score: 0.21)
# → AEC Score: 1.00 — PASS

# Gap detection — no capsule covers this topic
python cli.py orchestrate "Configure a Kubernetes cluster" --registry ./examples --dry-run
# → GAP DETECTED (score < 0.15) — no capsule handles this domain
```

5-signal routing: trigger text · authoritative domains · KG labels · capsule name · node count.
Gap threshold: 0.15. The orchestrator eats its own cooking — built using the same format it routes to.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `run` | Execute DAGR pipeline on a query |
| `orchestrate` | Auto-route query to best capsule |
| `verify` | Standalone AEC on any text against any KG |
| `validate` | Check capsule folder integrity |
| `info` | Display capsule metadata and KG stats |
| `stamp` | Create a new empty capsule |
| `ingest-skill` | Ingest a SKILL.md into a capsule |
| `ingest-research` | Ingest a research document (no LLM needed) |
| `ingest-document` | Ingest any markdown document |
| `queue` | View education queue status |
| `educate` | Run self-education on a pending failure |

---

## Architecture

```
aether/
├── aec.py          AEC verification engine (3-layer cascade)
├── aether.py       Capsule class · DAGR 4-stage pipeline
├── cli.py          Command-line interface
├── dashboard.py    Operational dashboard (port 8864)
├── education.py    Self-education loop (queue · research · validate · integrate)
├── habitat.py      Capsule registry · topic routing · orchestration
├── ingest.py       Source material → capsule pipeline
├── kg.py           JSON-LD knowledge graph · 5 origin types
├── llm.py          LLM wrapper (Anthropic · OpenAI · stub)
├── report.py       ASCII execution report
├── stamper.py      Capsule folder factory with lineage
├── README.md       This file
├── examples/       33 production capsules
└── tests/          Diagnostic suite
```

**Dependencies:** Python 3.11+ standard library only.
`anthropic` SDK required for LLM generation and Layer 2 verification.
All other operations — AEC compilation, Layer 1, Layer 3, orchestrator routing — run with zero external dependencies.

---

## What Makes AETHER Different

**Portable intelligence.** Agents are files, not runtime objects. Copy the folder = copy the complete agent. Same capsule, same results, any LLM.

**The graph is the program.** The knowledge graph is simultaneously: knowledge store, policy engine, and compiled verification runtime. One artifact. Three functions. Compile once at load. Verify every response in milliseconds.

**Self-verifying output.** AEC compiles typed KG nodes into deterministic policy checkers. No embeddings. No vector DB. No LLM-judging-LLM. Set intersection. Milliseconds.

**Self-improving knowledge.** Failures trigger autonomous education. The KG grows through use. Every failure specifies its own curriculum. The next query benefits from every previous failure.

**Type-driven entailment.** The KG node's `@type` drives verification strategy. Rules check compliance. AntiPatterns check violations. Techniques check application. The schema IS the verification program.

**Any skill, any platform.** Ingest any SKILL.md from any platform. The capsule is the output. The platform is interchangeable.

---

## Paper

**AETHER: Adaptive Embodied Thinking — Holistic Evolutionary Runtime**
Jeff Conn · 864 Zeros LLC · March 2026

> arXiv: [link after submission]

*The thoughts and ideas in this paper and repository are my own and do not represent my employer, its subsidiaries, or any affiliated organizations.*

---

## License

864 Zeros LLC · March 2026

---

*The model is the motor. The skill is the asset.*
