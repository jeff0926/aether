---
section: 4
title: "Method: Agent Creation via DAG"
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 4. Method: Agent Creation via DAG

This section describes how agents are created through the DAG (Distilled Augmented Generation) process. DAG transforms source material — a SKILL.md file, a research document, a markdown reference, or any structured text — into a complete capsule. The process is automatic: one CLI command, one source file, one output directory.

### 4.1 The Ingest Pipeline

DAG is implemented through three ingest modes, each optimized for a different source format:

| Mode | Source | LLM Required | Use Case |
|------|--------|-------------|----------|
| `ingest_skill` | SKILL.md with YAML frontmatter | Yes | Claude/Copilot skill files, SoulSpec agents |
| `ingest_research` | Structured deep research output | No | Gemini Deep Research, structured reports |
| `ingest_document` | Any markdown file | Yes | Documentation, guidelines, references |

All three modes produce the same output: a valid 5-file capsule directory. The difference is in how knowledge is extracted — `ingest_research` parses deterministically (no LLM call), while `ingest_skill` and `ingest_document` use LLM-assisted extraction.

**Returning to the running example:** The frontend-design capsule was created via `ingest_skill` from Anthropic's official frontend-design SKILL.md (3,956 characters, published as part of Claude's 17 official skills). A single CLI command:

```bash
python cli.py ingest-skill input/skills/frontend-design/SKILL.md \
  --output ./examples --provider anthropic
```

This produced a complete capsule in `examples/frontend-design-v1.0.0-ff6ab491/` with 73 KG nodes, 180 triples, and a structured persona — from a flat markdown file to a self-verifying agent in one invocation.

### 4.2 Knowledge Distillation: Three Extraction Skills

The critical step in DAG is knowledge distillation: transforming unstructured source text into a typed knowledge graph. Generic LLM prompts produce thin, poorly typed graphs. AETHER addresses this with **extraction skills** — specialized prompt templates that themselves follow the SKILL.md format.

Three extraction skills govern the distillation process:

**kg-from-skill** extracts the knowledge graph. It instructs the LLM to identify six node types (Concept, Rule, AntiPattern, Technique, Tool, Trait), establish relationship edges between them (avoids, requires, enables, contradicts, contains, prioritizes), and produce valid JSON-LD with the AETHER `@context`. The prompt specifies that every "never," "always," "must," and "avoid" in the source should become Rule or AntiPattern nodes — capturing policy knowledge that will later compile into AEC verification detectors.

**persona-from-skill** derives the agent's personality. It reads the source material's language — bold assertions suggest confidence, warning-heavy text suggests caution, creative direction suggests artistry — and produces a structured persona with named traits, keywords, and a distinctive identity.

**definition-from-skill** extracts behavioral configuration. Domain boundaries (what the agent is authoritative on, what it must defer), trigger conditions (when should this agent activate), and suggested AEC verification gates specific to this domain.

The extraction skills are themselves SKILL.md files — AETHER using its own skill format to build its own agents. This meta-circularity is a concrete demonstration of the skill-as-agent thesis: the extraction skills are agents that create agents.

### 4.3 Extraction Quality

The specialized extraction skills produce significantly richer knowledge graphs than generic LLM prompts. On the same frontend-design source material:

| Extraction Method | Total Nodes | Rules | AntiPatterns | Techniques | Concepts | Edges |
|------------------|------------|-------|-------------|------------|----------|-------|
| Generic prompt | 50 | 14 | 3 | 11 | 18 | ~60 |
| Specialized kg-from-skill | 73 | 22 | 6 | 22 | 14 | 180 |
| **Improvement** | **+46%** | **+57%** | **+100%** | **+100%** | -22% | **+200%** |

The specialized skill produces 46% more nodes overall, with the most significant gains in the categories that matter most for AEC verification: Rules (+57%), AntiPatterns (+100%), and Techniques (+100%). The decrease in Concept nodes reflects better classification — nodes that generic prompts loosely typed as Concepts were correctly identified as specific Rules or Techniques by the specialized prompt.

Edge density increased by 200%, which directly impacts Layer 3 verification: more edges mean more compiled policy functions, which means richer compositional violation detection.

### 4.4 The Stamper

Once knowledge distillation produces the five capsule files, the **stamper** generates the capsule directory:

1. Computes a unique identifier from name + version + timestamp: `{slug}-v{version}-{uid8}`
2. Creates the directory in the output path
3. Names all files with the capsule ID prefix (ensuring files are identifiable outside their directory)
4. Records lineage: `previous_id` and `previous_version` if this is a restamp of an existing capsule
5. Validates the capsule (all five files present and parseable)

The stamper is the "birth certificate" mechanism. Every capsule has a provenance chain — who was its parent, what version did it descend from. When capsules improve through education and are re-stamped as new versions, the lineage record creates an auditable evolution trail.

### 4.5 Skill Portability: Any Source, Same Output

DAG's three ingest modes share a common output format: the 5-file capsule. This means any source of agent knowledge — regardless of its origin format — produces the same portable artifact.

| Source Ecosystem | Input Format | DAG Mode | Output |
|-----------------|-------------|----------|--------|
| Claude Code | SKILL.md | `ingest_skill` | Capsule |
| Copilot | SKILL.md / .agent.md | `ingest_skill` | Capsule |
| SoulSpec / OpenClaw | SOUL.md + soul.json | `ingest_skill` (planned) | Capsule |
| Gemini Deep Research | Structured markdown | `ingest_research` | Capsule |
| Enterprise documentation | Markdown / PDF | `ingest_document` | Capsule |
| GitHub repositories | Code + README | Planned | Capsule |

The source format is consumed. The capsule is produced. The skill has been distilled, augmented with typed structure, and generated as an agent. DAG complete.

All 17 of Anthropic's official skills were ingested through DAG, producing 17 complete capsules — each with typed knowledge graphs, structured personas, and AEC-ready verification targets. An additional 8 executive advisory capsules were created through a collaborative DAG process using Gemini for knowledge research and the AETHER extraction skills for graph generation.

### 4.6 What DAG Does Not Do

DAG creates the capsule. It does not run the capsule (that is DAGR, Section 5). It does not verify the capsule's output (that is AEC within DAGR). It does not improve the capsule (that is the self-education loop, Section 6).

A capsule produced by DAG is operational but unrefined. Its knowledge graph reflects the source material faithfully, but the thresholds may need tuning, the coverage may have gaps, and the anti-patterns may be incomplete. This is by design — the DAGR pipeline and self-education loop handle refinement through use. DAG produces the seed. DAGR and AEC grow it.

This separation is architecturally significant: it means DAG can be fast and automated (one command, seconds to complete) without requiring the capsule to be perfect at creation. The education loop closes the quality gap over time. The first response from a DAG-created capsule will be verified by AEC. If it fails, education begins. The skill improves through practice — exactly as the skill definition in Section 3.1 requires.
