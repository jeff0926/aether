# AETHER — Adaptive Embodied Thinking Holistic Evolutionary Runtime

**Self-educating skills for any LLM.**

Skill.md in. Smarter skill.md out. Works with Claude, GPT, Gemini, Copilot, or any LLM. The model is replaceable. The skill is the asset.

---

## What Is AETHER

AETHER is an agent framework where agents are files, not code. Every agent is a folder of 5 files — a **capsule** — that carries its own identity, knowledge, personality, and verification rules. Capsules run through a 4-stage pipeline, verify their own output against a compiled knowledge graph, and self-educate when they fail.

No frameworks. No vector databases. No embeddings. Python stdlib + one LLM SDK.

---

## Quick Start

```bash
# Clone
git clone https://github.com/jeff0926/aether.git
cd aether

# Optional: Set API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Run a capsule
python cli.py run examples/jefferson "When was Jefferson born?" --provider anthropic

# Orchestrate (auto-route to the right agent)
python cli.py orchestrate "When was Jefferson born?" --registry ./examples --provider anthropic

# Verify any text against any KG
python cli.py verify "Jefferson was born in 1743" -r examples/jefferson/jefferson-kg.jsonld

# Stamp a new agent from a skill.md
python cli.py ingest-skill input/skills/my-skill/SKILL.md --output ./examples --provider anthropic

# Start the dashboard
python dashboard.py
```

---

## The Capsule: 5 Files = Complete Agent

```
my-agent-v1.0.0-a3f7c2d1/
├── my-agent-v1.0.0-a3f7c2d1-manifest.json      Identity & lineage
├── my-agent-v1.0.0-a3f7c2d1-definition.json     Behavior, pipeline config, AEC gates
├── my-agent-v1.0.0-a3f7c2d1-persona.json        Tone, style, traits
├── my-agent-v1.0.0-a3f7c2d1-kb.md               Knowledge base (markdown)
└── my-agent-v1.0.0-a3f7c2d1-kg.jsonld           Knowledge graph (typed JSON-LD)
```

Copy the folder. Email it. Check it into Git. The agent works anywhere.

---

## The Pipeline: 4 Stages

Every query runs through:

1. **Distill** — Extract intent, entities, format preferences from the query
2. **Augment** — Match entities against KB paragraphs and KG nodes, retrieve grounding context
3. **Generate** — Call LLM with persona + matched context + query
4. **Review** — AEC verifies the response against the knowledge graph

Framework overhead: <1ms. All latency is LLM response time.

---

## AEC: Agent Education Calibration

AEC is AETHER's verification engine. It compiles the knowledge graph into executable policy checkers at load time, then verifies every response in milliseconds.

### Four Verification Layers

**Factual Gate** — Extracts numbers, dates, percentages, names. Matches against KG properties. Deterministic. The foundation.

**Layer 1: Compiled Pattern Matching** — KG node labels compile into token sets at capsule load. Statement matching via set intersection. Sørensen-Dice for ambiguous cases. Anti-pattern blacklist for instant violation detection. O(statements), not O(statements × nodes).

**Layer 2: Type-Driven Verification** — The node's `@type` determines which verification operator fires. Rules check compliance. AntiPatterns check violations. Techniques check application. LLM fallback only when deterministic is inconclusive.

**Layer 3: Edge Policy Traversal** — Typed edges (`avoids`, `requires`, `contradicts`) compile into composed policy functions. 1-hop traversal. If `concept:typography → avoids → antipattern:inter_roboto_arial`, and a statement about typography mentions "Inter" — violation detected via graph path.

### Scoring

```
Score = Grounded / (Grounded + Ungrounded)
```

Persona statements (no verifiable content) excluded. Default threshold: 0.80.

### Self-Education

When AEC fails:
1. Failure enters the education queue with gaps identified
2. LLM researches the specific missing knowledge
3. New triples validated through AEC before integration
4. Validated knowledge added to KG as `acquired` origin
5. Original query re-evaluated against expanded KG
6. Contradiction gate prevents acquired nodes from conflicting with core

---

## Orchestrator

The orchestrator is itself a capsule. It routes queries to the right agent automatically.

```bash
# User asks a question — AETHER figures out who answers
python cli.py orchestrate "What is Buffett's investment philosophy?" --registry ./examples --provider anthropic

# See routing decision without executing
python cli.py orchestrate "How should I approach typography?" --registry ./examples --dry-run
```

Scoring uses trigger text, domain boundaries, KG labels, and capsule name. Gap detection when no capsule matches.

---

## Ingest Pipeline

### From Skill.md

```bash
python cli.py ingest-skill path/to/SKILL.md --output ./examples --provider anthropic
```

Parses YAML frontmatter, uses body as KB, runs three specialized extraction skills to generate KG (typed nodes), persona, and definition. All 17 Anthropic official skills have been ingested.

### From Research Document

```bash
# Deterministic parsing of deep research output (no LLM needed)
python ingest.py research path/to/research.md --output ./examples --name "My Agent"
```

### From Any Document

```bash
# LLM-assisted extraction
python ingest.py document path/to/doc.md --output ./examples --name "My Agent" --provider anthropic
```

---

## Capsule Inventory (21 production capsules)

| Category | Capsules |
|----------|----------|
| **Scholars** | Thomas Jefferson, Warren Buffett |
| **Validators** | AETHER Validator, Test Agent |
| **Domain Experts** | Domain Agent Builder, Domain SAP CAP |
| **Anthropic Skills** | frontend-design, brand-guidelines, doc-coauthoring, claude-api, skill-creator, mcp-builder |
| **Executive Roles** | CEO, CTO, CPO, CFO, CISO, CLO, Lead Dev, Lead Data Arch, Agent Performance Mgr |
| **Infrastructure** | Orchestrator |

---

## Dashboard

```bash
python dashboard.py          # http://localhost:8864
```

Five tabs: Overview, KG Explorer (vis-network), AEC Lab, Force Test, Education Queue.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Execute pipeline on a query against a capsule |
| `orchestrate` | Auto-route query to the best capsule |
| `verify` | Standalone AEC on any text against any KG |
| `validate` | Check capsule folder integrity |
| `info` | Display capsule metadata and stats |
| `stamp` | Create a new empty capsule |
| `ingest-skill` | Ingest a SKILL.md into a capsule |
| `queue` | View education queue status |
| `educate` | Run self-education on a pending failure |

---

## Architecture

```
aether/
├── aec.py              Factual entailment check (deterministic gate)
├── aec_concept.py      Concept-level AEC (3 layers: compiled matching, type-driven, edge traversal)
├── aether.py           Capsule class, 4-stage pipeline
├── cli.py              Command-line interface
├── dashboard.py        Operational diagnostics (port 8864)
├── education.py        Self-education loop (queue, research, validate, integrate)
├── habitat.py          Capsule registry, topic routing, orchestration
├── ingest.py           Document/skill → capsule pipeline
├── kg.py               JSON-LD knowledge graph (5 origin types)
├── llm.py              LLM wrapper (Anthropic, OpenAI, stub)
├── report.py           ASCII execution report
├── stamper.py          Capsule folder factory with lineage
├── README.md           This file
├── examples/           21+ capsules
├── input/skills/       Cloned skill repos (gitignored)
└── tests/              Diagnostic suite
```

**Dependencies:** Python 3.11+ standard library. `anthropic` SDK optional (stub provider works without it).

---

## What Makes AETHER Different

**Portable intelligence.** Agents are files, not runtime objects. Copy the folder = copy the complete agent. Works with any LLM.

**Self-verifying output.** AEC compiles the KG into deterministic policy checkers. No embeddings. No vector DB. No LLM-judging-LLM. Set intersection. Milliseconds.

**Self-improving knowledge.** Failures trigger autonomous education. The KG grows through use. The next query benefits from every previous failure.

**Type-driven entailment.** The KG node's `@type` drives verification strategy. Rules check compliance. AntiPatterns check violations. The schema IS the verification program.

**The graph is the program.** The knowledge graph is simultaneously: knowledge store, policy engine, and compiled verification runtime. One artifact, three functions.

---

## License

864 Zeros LLC — March 2026

---

*AETHER — Adaptive Embodied Thinking Holistic Evolutionary Runtime*
*github.com/jeff0926/aether*
