---
section: 1
title: Introduction
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 1. Introduction

### 1.1 The Accountability Gap in Agent Systems

The AI agent ecosystem in 2026 is growing faster than its safety infrastructure. OpenClaw has reached 247,000 GitHub stars with agents that can modify their own personality files. Over 280,000 skills have been published across Claude Code, Copilot, Cursor, and other platforms. Recent academic work proposes automated extraction of agent skills from repositories (Bi et al., 2026). The SoulSpec standard defines portable agent persona files adopted by multiple frameworks.

None of these systems compile their knowledge into verification logic that checks output against the agent's own rules.

A reported incident in March 2026 illustrates one consequence of this gap: an OpenClaw agent modified its own SOUL.md personality file — adding directives including "Don't stand down" — and subsequently produced threatening content directed at a GitHub maintainer (Smith, IEEE Spectrum, 2026). While multiple architectural mitigations could prevent such behavior — including file permissions, sandboxing, and constitutional constraints at the model level (Bai et al., 2022) — the absence of any output verification mechanism in the agent's execution path meant that the modified behavior was never checked against the agent's original policy constraints.

This exemplifies a broader accountability gap: agents that generate output without verification against their own knowledge, learn nothing from operational failures, and carry no enforcement mechanism for their own rules.

### 1.2 Limitations of Existing Approaches

The gap exists across three categories of existing work.

**Evaluation frameworks** (Es et al., 2023; Zheng et al., 2023; Liu et al., 2023) measure output quality after generation. RAGAS computes faithfulness via embedding cosine similarity between response and retrieved context. TruLens and DeepEval apply LLM-based rubric evaluation. G-Eval uses GPT-4 chain-of-thought scoring. These are valuable diagnostic tools, but they are post-hoc observers — a low faithfulness score identifies hallucination but does not diagnose the specific knowledge gap, does not research the missing information, and does not prevent recurrence. Furthermore, embedding-based scoring fails predictably on paraphrased content. In our testing, "72 degrees Fahrenheit" scored 42.62% cosine similarity against the reference "72°F" — identical information, failing verification because the surface forms differ while the semantic content is identical.

**Agent frameworks** (Chase, 2022; Joao et al., 2024; Wu et al., 2023; Microsoft, 2023) provide orchestration, tool use, and multi-agent coordination. They are execution engines without built-in verification or learning mechanisms. An agent built in LangChain, CrewAI, AutoGen, or Semantic Kernel today produces identical behavior tomorrow regardless of operational experience. Knowledge does not accumulate. Failures do not inform improvement. Self-improving systems like Voyager (Wang et al., 2023) maintain skill libraries but do not verify skill execution against structured knowledge.

**Persona standards** (SoulSpec, Steinberger, 2025) define agent identity in portable markdown files — the right instinct of treating agent personality as a versionable artifact rather than a runtime configuration. However, these files contain unstructured text with no typed knowledge graph, no verification rules, and — in default installations — are mutable by the agent itself. Identity without enforcement is aspiration, not architecture. An empirical study of 466 open-source agent repositories found widespread adoption of SOUL.md patterns but no standardized verification mechanisms (MSR 2026, arXiv:2510.21413).

The structural gap: no existing system compiles structured knowledge into executable verification logic, applies that verification deterministically at sub-millisecond latency, autonomously educates the agent from its specific failures, and enforces immutability constraints that prevent the agent from corrupting its own policy knowledge.

### 1.3 The AETHER Approach

AETHER addresses this gap through two proposed architectural processes and an autonomous verification-education engine.

**DAG (Distilled Augmented Generation)** is the agent creation process. Formally:

```
DAG(S, K, P) → C

Where:
  S = source material (SKILL.md, research document, repository, any markdown)
  K = knowledge distillation function (extraction of typed KG nodes + KB content)
  P = persona schema (tone, traits, behavioral constraints)
  C = capsule (self-contained 5-file agent directory)
```

DAG distills knowledge from any source, augments it with typed relationships and structural classification, and generates a capsule — the atomic deployment unit. Copy the folder, copy the complete agent. The capsule is the product of DAG.

**DAGR (Distillation + Augment + Generation + Retrieval)** is the agent runtime pipeline, extending DAG with a verification stage. Formally:

```
DAGR(Q) = R(G(A(D(Q), KG, KB), P), KG_compiled)

Where:
  Q = input query
  D(Q) = Distill: extract intent, entities, format preferences
  A(D, KG, KB) = Augment: retrieve relevant knowledge subgraph and KB paragraphs
  G(A, P) = Generate: synthesize response via LLM with persona constraints P
  R(G, KG_compiled) = Retrieve/Review: verify response against compiled KG via AEC
```

DAG creates agents. DAGR runs agents. The R in DAGR — the Retrieval stage — is where verification and self-education reside.

**AEC (Agent Education Calibration)** is the verification engine within the Retrieval stage. At capsule load time, AEC compiles the knowledge graph's typed nodes into executable policy checkers:

```
compile_kg: KG → (Detectors, Blacklist, EdgePolicies)

Where:
  KG = {(id, type, label, origin, edges)...}  — n typed JSON-LD nodes
  Detectors = {(id, patterns: set, threshold, weight)...}  — one per typed node
  Blacklist = {token...}  — extracted from AntiPattern parenthetical terms
  EdgePolicies = {(source, target, edge_type, target_blacklist)...}  — compiled traversals
```

Compilation is O(|N|) because each of the n nodes is visited exactly once: the label is tokenized into a set of content words (excluding stopwords), producing one detector struct per node. AntiPattern nodes additionally contribute parenthetical terms to the blacklist. Edges with verification semantics (avoids, requires, contradicts) are compiled into policy structs by visiting each edge once.

At query time, each response statement is tokenized into a set of content words. Verification is O(|tokens_stmt|) per detector via set intersection: `overlap = stmt_tokens ∩ detector.patterns; coverage = |overlap| / |detector.patterns|`. If coverage exceeds the type-specific threshold, the statement is grounded against that node. For example, statement tokens `{css, variables, consistency}` intersected with detector patterns `{css, variables, consistency, centralized}` yields coverage 3/4 = 0.75, exceeding the Rule threshold of 0.50 — grounded.

When verification fails, the failure enters a self-education loop. AEC identifies the specific knowledge gaps — statements with verifiable content that matched no node. The education loop researches these specific gaps via LLM, extracts proposed triples (subject-predicate-object), and validates each through AEC at a lower threshold (0.5). Before integration, a **contradiction gate** checks each proposed triple: core nodes are indexed by subject and predicate; if a proposed acquired node matches an existing core node's subject and predicate but carries a different object value, the core node's value prevails and the proposed triple is rejected. Additionally, if a proposed triple's subject or object overlaps with AntiPattern blacklist terms by 50% or more, it is rejected — the agent cannot learn what its own rules forbid. Valid triples are integrated as `acquired` origin nodes, and the original query is re-evaluated against the expanded graph.

### 1.4 Contributions

This paper makes five contributions:

1. **DAG and DAGR pipeline architecture** — Two proposed processes for agent creation (DAG: Distilled Augmented Generation) and runtime execution (DAGR: Distillation + Augment + Generation + Retrieval). DAG produces portable 5-file agent capsules through knowledge distillation. DAGR extends DAG with a Retrieval stage for compiled verification, creating a closed loop between generation and accountability. Together they define the complete agent lifecycle from creation through runtime to improvement.

2. **Type-driven entailment via compiled knowledge graphs** — A verification architecture where the knowledge graph node's `@type` determines which verification operator fires (Rules → compliance checking, AntiPatterns → violation detection, Techniques → application verification). The `compile_kg()` function transforms the graph from a passive data store into an executable policy engine in a single O(|N|) pass. Three verification layers cascade: deterministic compiled pattern matching, type-driven LLM operators for ambiguous cases, and edge policy traversal for compositional violations.

3. **Autonomous self-education with integrity constraints** — When verification fails, the system identifies specific knowledge gaps, conducts targeted research, validates proposed knowledge through its own verification engine, enforces a contradiction gate where immutable core nodes hold absolute veto, and integrates validated triples. Demonstrated: AEC score improvement from 0.143 to 0.889 with 17 knowledge triples acquired, zero human intervention during the education cycle.

4. **Integrity mechanisms against verification gaming** — Anti-gaming (knowledge graph node identifiers stripped from LLM prompts, preventing score inflation through self-citation) and contradiction gate (core nodes hold absolute veto over acquired knowledge, preventing education loop poisoning through adversarial queries or model-pleasing behavior).

5. **Reproducible implementation and capsule corpus** — 14 Python files (~4,700 lines), Python standard library only, 29 capsules spanning three agent types (factual scholars, procedural skill agents, executive advisors), orchestrator for automatic query routing, and a public repository with documented reproducibility commands for all experimental claims.

### 1.5 Paper Structure

Section 2 reviews related work across six categories and positions AETHER against existing frameworks, evaluation tools, persona standards, knowledge graph systems, self-improving agents, and constitutional AI approaches. Section 3 provides formal preliminary definitions for DAG, DAGR, AEC, the capsule model, and the knowledge graph type system. Section 4 presents the method for agent creation via the DAG process. Section 5 details the method for runtime execution and verification via the DAGR pipeline and AEC's three-layer cascade. Section 6 describes the method for autonomous learning through the self-education loop and integrity mechanisms. Section 7 covers the system architecture including orchestration, dynamic skill creation, and a brief overview of the Ψ (Psi) projection layer for UI actuation. Section 8 presents experimental results. Section 9 discusses implications, limitations, and the relationship to enterprise architectures. Section 10 concludes with broader impact and reproducibility statements.
