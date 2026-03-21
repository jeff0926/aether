---
section: 3
title: Preliminaries
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 3. Preliminaries

This section formalizes the core definitions that govern the remainder of the paper. We begin with the conceptual foundation — what distinguishes a skill from a tool — then define the capsule as the structural realization of that distinction, and establish the formal notation for DAG, DAGR, AEC, and the knowledge graph type system.

### 3.1 What Is a Skill?

A skill is something an entity **knows**, **expresses consistently**, and **gets better at through practice.**

This definition is deliberately distinct from what agent frameworks currently ship. A function call is not a skill — it has no knowledge, no consistency of expression, no improvement through use. A prompt template is not a skill — it has knowledge but no identity, no persistence, no self-correction. A fine-tuned model has absorbed skills into its weights, but those skills are not inspectable, not portable, and not independently improvable.

A skill, properly defined, requires five properties:

| Property | Meaning | Agent Equivalent |
|----------|---------|-----------------|
| **Knowledge** | Domain-specific information the skill draws from | Structured + unstructured knowledge base |
| **Identity** | Persistent, versioned existence independent of runtime | Manifest with UID and lineage |
| **Expression** | Consistent voice, reasoning style, behavioral traits | Persona definition |
| **Behavior** | Configurable operational parameters and boundaries | Pipeline configuration and domain limits |
| **Improvement** | Gets better from practice; failures inform growth | Verified self-education loop |

No mainstream agent framework satisfies all five. Most satisfy zero or one.

### 3.2 The Capsule: A Skill as an Agent

The AETHER capsule is the structural realization of all five skill properties as files in a directory:

| Skill Property | Capsule File | Format | Mutability |
|---------------|-------------|--------|------------|
| Knowledge (structured) | `{id}-kg.jsonld` | Typed JSON-LD graph | Core: immutable. Acquired: mutable via education. |
| Knowledge (unstructured) | `{id}-kb.md` | Markdown | Immutable core |
| Identity | `{id}-manifest.json` | JSON | Updated on restamp only |
| Expression | `{id}-persona.json` | JSON | Configurable |
| Behavior | `{id}-definition.json` | JSON | Configurable |
| Improvement | Education loop + AEC | Runtime mechanism | Writes acquired nodes to KG |

**The capsule is not an agent that has skills. The capsule is a skill that is an agent.**

The folder exists. The agent exists. They are the same thing. No runtime, no framework, no process required for the agent to *be* — only for it to *act*. Copy the folder to another machine, point it at any LLM, and the complete agent — knowledge, identity, expression, behavior, and verification rules — is operational.

### 3.3 Formal Definitions

**Definition 1 (Capsule).** A capsule C is a 5-tuple:

```
C = (M, Δ, Π, KB, KG)

Where:
  M  = manifest (id, name, version, created, lineage)
  Δ  = definition (pipeline config, thresholds, domain boundaries, triggers)
  Π  = persona (tone, style, traits, description)
  KB = knowledge base (unstructured markdown)
  KG = knowledge graph (typed JSON-LD)
```

**Definition 2 (Knowledge Graph).** A knowledge graph KG is a set of typed nodes with edges:

```
KG = (N, E, T, O)

Where:
  N = {n₁, n₂, ..., nₖ}  — nodes
  E = {(nᵢ, relation, nⱼ)...}  — directed typed edges
  T: N → {Concept, Rule, AntiPattern, Technique, Tool, Trait}  — type function
  O: N → {core, acquired, updated, deprecated, provenance}  — origin function
```

The type function T is not metadata. It is a verification instruction — the mechanism by which the knowledge graph compiles into executable logic (Section 5).

The origin function O enforces the core/acquired distinction. Nodes with `O(n) = core` are immutable at runtime. Nodes with `O(n) = acquired` are mutable and subject to the contradiction gate — an algorithm that checks proposed acquired nodes against core nodes before integration (defined in Section 6). This structural separation enables self-education without knowledge corruption.

**Definition 3 (DAG — Distilled Augmented Generation).** The agent creation process.

*Running example: Consider a frontend-design SKILL.md containing rules like "Avoid generic fonts (Inter, Roboto, Arial)" and techniques like "Use staggered animation reveals." DAG distills this into a capsule with 73 typed KG nodes — 22 Rules, 22 Techniques, 14 Concepts, 6 AntiPatterns — each carrying verification semantics that AEC will compile into policy checkers. This capsule and its verification behavior will illustrate each definition that follows.*

```
DAG: (S, K, P) → C

Where:
  S = source material ∈ {SKILL.md, research document, markdown, repository}
  K: S → (KB, KG)  — knowledge distillation function
    K decomposes into:
      K_text: S → KB  — extract unstructured knowledge as markdown
      K_graph: S → KG  — extract typed nodes and edges as JSON-LD
  P: S → Π  — persona extraction function
  C = (M_generated, Δ_extracted, P(S), K_text(S), K_graph(S))
```

DAG distills knowledge from any source, augments it with typed relationships and structural classification, and generates a capsule. The manifest M is generated by the stamper with a unique identifier. The definition Δ is extracted from the source material's domain boundaries and behavioral indicators.

**Definition 4 (DAGR — Distillation + Augment + Generation + Retrieval).** The agent runtime pipeline:

```
DAGR: Q × C → (response, score, gaps, KG')

Where:
  Q = input query
  C = capsule (M, Δ, Π, KB, KG)

  D(Q) → (intent, entities, format)              — Distill
  A(D(Q), KG, KB) → context                      — Augment
  G(context, Π) → response                        — Generate (LLM call)
  R(response, KG_compiled) → (score, gaps)         — Retrieve/Review (AEC)

  DAGR(Q, C) = R(G(A(D(Q), KG, KB), Π), compile(KG))

  If score ≥ threshold: return (response, score, ∅, KG)
  If score < threshold: return (response, score, gaps, KG)
    and queue (Q, response, gaps) for education
```

DAG creates the capsule. DAGR runs the capsule. The R in DAGR — the Retrieval stage — is where verification and the education trigger reside.

**Definition 5 (AEC — Agent Education Calibration).** The verification engine:

```
compile: KG → (D_set, B, P_edge)

Where:
  D_set = {(nᵢ, patterns_i, threshold_i, weight_i)...}  — compiled detectors
    patterns_i = tokenize(label(nᵢ)) \ stopwords
    threshold_i = f(T(nᵢ))  — type-specific threshold
    weight_i = g(T(nᵢ))  — type-specific weight

  B = ∪{parenthetical_terms(label(n)) : T(n) = AntiPattern}  — blacklist

  P_edge = {(nᵢ, nⱼ, relation, B_target)...}  — edge policies
    for each (nᵢ, relation, nⱼ) where relation ∈ {avoids, requires, contradicts}

Compile time: O(|N|) — each node visited once
```

```
verify: (response, D_set, B, P_edge) → {(statement, category, evidence)...}

Where:
  category ∈ {grounded, ungrounded, persona}

  For each statement s in split(response):
    tokens_s = tokenize(s) \ stopwords

    Layer 1 (deterministic):
      If tokens_s ∩ B ≠ ∅ → (s, ungrounded, blacklist_hit)
      For each d ∈ D_set:
        coverage = |tokens_s ∩ d.patterns| / |d.patterns|
        If coverage ≥ d.threshold → (s, grounded, d.node_id)

    Layer 2 (type-driven, if Layer 1 inconclusive and LLM available):
      Select top-3 candidates from D_set by partial coverage
      For each candidate:
        classification = LLM_classify(s, candidate, T(candidate))
          — prompts the LLM: "Does statement s FOLLOW, VIOLATE, or have
            NO RELATION to this [T(candidate)] node?" Forces structured
            JSON output. Includes generosity guard: "If merely good advice
            but not explicitly supported, classify UNRELATED."
        If classification = FOLLOW → (s, grounded, candidate.node_id)
        If classification = VIOLATE → (s, ungrounded, candidate.node_id)

    Layer 3 (edge traversal, if Layer 1/2 matched a node):
      For each matched node nᵢ:
        For each (nᵢ, avoids, nⱼ) ∈ P_edge:
          If tokens_s ∩ B_target(nⱼ) ≠ ∅ → (s, ungrounded, edge_path)

    Default: (s, persona, no_match)

Runtime per statement: O(|tokens_s|) for set intersection operations
```

```
score: results → [0, 1]

  score = |{r : r.category = grounded}| / |{r : r.category ∈ {grounded, ungrounded}}|

  Persona statements excluded from both numerator and denominator.
  If all statements are persona: score = 1.0 (all-persona pass)
```

### 3.4 Knowledge Graph Type System

The type function T maps each node to exactly one of six types. Each type carries verification semantics — it determines how AEC evaluates statements that match the node:

| Type | Verification Semantics | Threshold | Weight | AEC Behavior |
|------|----------------------|-----------|--------|-------------|
| `Concept` | Relevance detection | 0.30 | 0.5 | Does the statement address this domain? |
| `Rule` | Compliance checking | 0.50 | 1.0 | Does the statement follow this guideline? |
| `AntiPattern` | Violation detection | 0.40 | 1.0 | Does the statement use what this pattern forbids? |
| `Technique` | Application verification | 0.55 | 1.0 | Is this technique being applied? |
| `Tool` | Usage context | 0.60 | 0.3 | Is this tool referenced appropriately? |
| `Trait` | Persona alignment | 0.70 | 0.2 | Is the expression consistent with this trait? |

These thresholds were tuned empirically against the 73-node frontend-design skill agent using a 50-query validation set spanning rule compliance, anti-pattern violation, and technique application scenarios. Concepts receive the lowest threshold (0.30) because domain relevance can be expressed with few overlapping terms. Rules and AntiPatterns receive the highest weight (1.0) because policy compliance is the primary verification target. The threshold values represent the minimum token coverage ratio required for a Layer 1 match to be classified as grounded. Broader validation across diverse knowledge graphs is ongoing (Section 9).

### 3.5 Edge Types and Verification Semantics

Three edge types carry verification semantics — they compile into Layer 3 policy functions:

| Edge | Formal | Verification Logic |
|------|--------|--------------------|
| `avoids` | (nᵢ, avoids, nⱼ) | If statement matches nᵢ AND tokens overlap with nⱼ blacklist → violation |
| `requires` | (nᵢ, requires, nⱼ) | Informational in v1 — logged if nⱼ absent, not scored |
| `contradicts` | (nᵢ, contradicts, nⱼ) | If statement matches both nᵢ AND nⱼ → contradiction |

Three additional edge types provide structural organization but do not compile into verification policies:

| Edge | Purpose |
|------|---------|
| `enables` | nᵢ makes nⱼ possible (routing signal) |
| `contains` | Hierarchical grouping |
| `prioritizes` | Relative importance (routing tiebreaker) |

The distinction between verification edges and structural edges is architecturally significant: `compile_kg()` processes only the first three, keeping compilation time strictly proportional to the number of verification-relevant edges, not the total edge count.
