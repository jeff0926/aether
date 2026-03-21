---
section: 0
title: Abstract
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# Abstract

The deployment of AI agents in specialized domains requires mechanisms to distinguish between knowledge-grounded output and hallucination, yet current approaches — embedding similarity, LLM-as-judge, and manual review — fail on paraphrased content, introduce non-deterministic bias, or cannot scale. This paper presents AETHER (Adaptive Embodied Thinking : Holistic Evolutionary Runtime), a minimal agent framework built on two proposed architectural processes: DAG (Distilled Augmented Generation) for agent creation, formally defined as DAG(S, K, P) → C where source material S is distilled through knowledge extraction K and persona schema P to produce a capsule C; and DAGR (Distillation + Augment + Generation + Retrieval) for agent runtime execution, defined as the composed pipeline DAGR(Q) = R(G(A(D(Q), KG, KB), P), KG_compiled) where each stage transforms and verifies the query Q through the agent's knowledge.

The Retrieval stage of DAGR implements Agent Education Calibration (AEC), a verification engine that compiles typed JSON-LD knowledge graph nodes into executable policy checkers at capsule load time in O(|N|) — linear because each node is visited exactly once to extract its token pattern set into a pre-computed detector. At runtime, AEC verifies each statement in O(|tokens|) via set intersection against these pre-computed detectors — no embeddings, no vector databases, no GPU. Measured verification time is 0.3–0.8ms per statement on standard consumer hardware (single-threaded Python, Apple M-series / Intel i7 equivalent).

When verification fails, a self-education loop autonomously identifies knowledge gaps, researches missing content via LLM, validates new knowledge through AEC itself, and enforces a contradiction gate where immutable core nodes hold absolute veto over proposed acquired knowledge. The framework is implemented in 14 Python files (~4,700 lines) using only the standard library, with 29 capsules and reproducibility commands in the public repository.

Evaluation demonstrates precise grounding discrimination (AEC scores: 1.0, 0.6, 0.14 across three knowledge coverage scenarios), meaningful skill verification (0.857 on a 73-node design agent with real rule compliance and anti-pattern violation detection), and autonomous self-education (score improvement from 0.143 to 0.889 with 17 knowledge triples acquired, zero human intervention during the education cycle). The model did not change. The skill did. The concepts presented here originated in the author's research beginning mid-2025, with initial prototypes on Google Firebase and the current architecture formalized in early 2026.
