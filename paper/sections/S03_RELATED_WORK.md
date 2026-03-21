---
section: 2
title: Related Work
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 2. Related Work

AETHER intersects six categories of existing work. Each addresses part of the agent accountability problem; none addresses the complete cycle of verified generation, autonomous education, and integrity enforcement. Table 1 summarizes the positioning.

**Table 1: Related Work Taxonomy and AETHER Differentiation**

| Category | Representative Work | What It Solves | What It Leaves Open | AETHER's Contribution |
|----------|-------------------|----------------|--------------------|-----------------------|
| Retrieval-Augmented Generation | Lewis et al. 2020, Guu et al. 2020 | Grounding LLM output in retrieved context | No post-generation verification; retrieval quality ≠ output quality | DAGR verifies *after* generation via AEC; retrieval (Augment) and verification (Retrieve) are separate stages |
| LLM Evaluation Frameworks | RAGAS (Es et al., 2023), G-Eval (Liu et al., 2023), TruLens, DeepEval | Scoring faithfulness, relevance, coherence | Post-hoc observation without remediation; embedding similarity fails on paraphrase; LLM-as-judge is non-deterministic | AEC compiles verification into deterministic detectors; failures feed education loop; sub-ms not seconds |
| Agent Frameworks | LangChain (Chase, 2022), CrewAI, AutoGen (Wu et al., 2023), Semantic Kernel (Microsoft, 2023) | Orchestration, tool use, multi-agent coordination | No verification layer; no learning from failure; agents are stateless across sessions | DAGR pipeline includes verification as a stage; self-education loop persists acquired knowledge in KG |
| Agent Safety & Constitutional AI | Constitutional AI (Bai et al., 2022), RLHF (Ouyang et al., 2022) | Constraining model behavior through training-time rules and human feedback | Rules embedded in weights, not inspectable or portable; no per-agent customization; cannot verify individual outputs against specific policies | AEC compiles inspectable, portable JSON-LD policies into per-agent verification; rules are files, not weights |
| Knowledge Graph Reasoning | RDF/OWL (W3C), SHACL (Knublauch & Kontokostas, 2017), TransE (Bordes et al., 2013) | Structured knowledge representation, schema validation, link prediction | SHACL validates *structured data* against shapes; KG reasoning operates on *graph queries*, not natural language | AEC validates *natural language* against typed knowledge — bridging the gap between graph-based policy and LLM output |
| Self-Improving Agent Systems | Voyager (Wang et al., 2023), ADAS (Hu et al., 2024), ReAct (Yao et al., 2022), AdaPlanner (Sun et al., 2023) | Skill libraries, iterative refinement, reasoning-action loops | Skills accumulate but aren't verified against structured knowledge; no contradiction detection; no immutable core | AEC validates acquired knowledge before integration; contradiction gate enforces core immutability; education is verified, not blind |

### 2.1 Retrieval-Augmented Generation

RAG (Lewis et al., 2020) augments LLM generation with retrieved context from external knowledge stores. The standard pipeline embeds queries and documents into a shared vector space, retrieves the most similar documents, and provides them as context for generation. REALM (Guu et al., 2020) extends this with end-to-end training of the retriever.

RAG addresses the *input* side of grounding: providing relevant context to the LLM. It does not address the *output* side: verifying that the generated response actually used that context faithfully. A high-quality retrieval step does not guarantee a grounded response — the LLM may ignore, misinterpret, or selectively use the retrieved context.

AETHER's DAGR pipeline separates these concerns explicitly. The Augment stage handles retrieval (input grounding). The Retrieve/Review stage handles verification (output checking). They are distinct pipeline stages with distinct functions, connected but not conflated.

### 2.2 LLM Evaluation Frameworks

RAGAS (Es et al., 2023) is the most widely adopted RAG evaluation framework, computing faithfulness, answer relevance, and context precision using embedding similarity and LLM-based scoring. G-Eval (Liu et al., 2023) uses GPT-4 chain-of-thought evaluation with human-aligned rubrics. TruLens provides guardrail-based evaluation with customizable feedback functions. DeepEval offers an open-source alternative with similar metrics.

These tools share three structural limitations for agent verification:

First, **embedding similarity fails on paraphrased content.** LLMs routinely restructure and rephrase retrieved content — this is their normal generation behavior. In our testing, cosine similarity between "72 degrees Fahrenheit" and the reference "72°F" was 42.62%. Between "approximately fifteen million dollars" and "$15,000,000," similarity was low despite identical semantic content. Any verification system built on text similarity will systematically undercount grounding when the LLM paraphrases — which is always.

Second, **LLM-as-judge introduces non-determinism.** The same response evaluated twice by the same judge model may receive different scores. When the judge is the same model that generated the response — common in production due to cost constraints — structural generosity bias means the system tends to approve its own work. We observed this directly when using Claude to verify Claude's output.

Third, **evaluation without remediation is incomplete.** A RAGAS faithfulness score of 0.4 tells you the response is poorly grounded. It does not tell you *which specific knowledge* is missing, does not research that knowledge, and does not prevent the same failure on the next query. The evaluation is diagnostic but not therapeutic.

AEC addresses all three: verification via compiled set intersection (not embedding similarity), deterministic scoring (not LLM judgment for the primary layer), and failure-driven education (not just scoring but remediation through the self-education loop).

### 2.3 Agent Frameworks

LangChain (Chase, 2022) provides chains, agents, and tools as composable abstractions for LLM applications. CrewAI (Joao et al., 2024) organizes agents into role-based crews with task delegation. AutoGen (Wu et al., 2023) enables multi-agent conversations with human-in-the-loop patterns. Semantic Kernel (Microsoft, 2023) provides an SDK for integrating LLMs into applications with plugin architectures.

These frameworks excel at orchestration — defining what agents do, how they communicate, and how they use tools. But their use of the word "skill" obscures a fundamental limitation. A LangChain agent is a function router. A CrewAI agent is a prompt template with memory bolted on. A Semantic Kernel "skill" is literally a C# method. None have knowledge that belongs to the agent. None persist identity when the process stops. None improve from failure. They are hammers pretending to be carpenters.

AETHER's capsule model is fundamentally different. The knowledge graph persists across sessions. The education loop writes acquired knowledge back to the graph. The compiled verification engine is rebuilt at each load to incorporate new knowledge. The agent that ran 100 queries is measurably different from the agent that ran 10, because its knowledge graph has grown through verified self-education. Point the same capsule at Claude, GPT-4, or Gemini — the knowledge, verification, and identity travel intact. The model is the engine. The skill is the asset.

### 2.4 Agent Safety and Constitutional AI

Constitutional AI (Bai et al., 2022) constrains model behavior through a set of principles applied during training. The model learns to self-critique and revise its outputs according to a constitution. RLHF (Ouyang et al., 2022) aligns model behavior with human preferences through reinforcement learning from human feedback.

These approaches operate at the *model* level — the constraints are embedded in the model's weights through training. This has three implications that AEC addresses differently:

First, constitutional constraints are **not inspectable** at inference time. You cannot examine a trained model and determine exactly which rules it follows. AEC's knowledge graph is a JSON-LD file — human-readable, machine-parseable, auditable.

Second, constitutional constraints are **not portable** between models. Training Claude with a constitution does not transfer those constraints to GPT-4. AEC's verification is model-independent — the same capsule with the same KG produces the same verification results regardless of which LLM generated the response.

Third, constitutional constraints are **not per-agent customizable.** Every instance of Claude follows the same constitution. AEC's verification rules are per-capsule — a medical agent and a legal agent can have entirely different verification policies encoded in their respective knowledge graphs.

### 2.5 Knowledge Graph Reasoning

RDF (W3C, 2014) and OWL (W3C, 2012) provide formal ontology languages for structured knowledge representation. SHACL (Knublauch & Kontokostas, 2017) validates RDF graph data against structural constraints — shapes that define which properties a node must have, cardinality restrictions, and value type constraints. Knowledge graph embedding methods like TransE (Bordes et al., 2013) and RotatE (Sun et al., 2019) learn vector representations for link prediction and graph completion.

SHACL is the closest prior art to AEC's compilation approach. Both share the principle that the *schema drives the validation logic* — verification rules are derived from structural definitions, not learned or manually coded. However, SHACL validates **structured data** against shapes: does this RDF node have the required properties with valid values? AEC validates **natural language** against typed knowledge: does this LLM-generated sentence comply with the rules encoded in these typed graph nodes?

This is the specific gap AEC bridges. The input to SHACL is a graph node. The input to AEC is a sentence. The verification logic for SHACL is shape conformance. The verification logic for AEC is type-driven entailment — the node's `@type` determines which natural language verification operator fires. The output of both is a compliance determination, but they operate on fundamentally different inputs.

AETHER uses JSON-LD (W3C, 2014) as its knowledge graph format specifically because it provides the structured typing that AEC requires for compilation while remaining compatible with the broader linked data ecosystem. SAP's A2A agent communication protocol also uses JSON-LD, enabling native interoperability without format translation.

### 2.6 Self-Improving Agent Systems

Voyager (Wang et al., 2023) maintains a skill library that grows through exploration in Minecraft — discovered behaviors are stored as executable code for reuse. ADAS (Hu et al., 2024) proposes meta-agents that iteratively program, evaluate, and refine new agents. ReAct (Yao et al., 2022) implements reasoning-action loops where agents update their context through observation. AdaPlanner (Sun et al., 2023) refines plans through feedback from environmental interaction.

These systems share a common pattern: improvement through operational experience. They differ from AETHER in three respects.

First, **accumulated skills are not verified against structured knowledge.** Voyager adds code to its skill library when it works in practice. It does not check whether the code is consistent with any formal specification. AEC validates proposed knowledge against the compiled policy engine before integration — the education loop is verified, not blind.

Second, **there is no contradiction detection.** When a self-improving agent acquires knowledge that conflicts with its existing knowledge, most systems either overwrite silently or accumulate contradictions. AETHER's contradiction gate explicitly checks proposed acquired nodes against immutable core nodes: same subject and predicate with different object values triggers a rejection. The agent cannot unlearn its foundational knowledge through operational experience.

Third, **there is no immutable core.** In Voyager, all skills are equally mutable. In OpenClaw, the agent can edit its own SOUL.md. AETHER distinguishes between core knowledge (immutable at runtime, representing the agent's foundational training) and acquired knowledge (mutable, representing operational learning). The core/acquired distinction is enforced by the contradiction gate and is structurally visible in the JSON-LD origin types.

### 2.7 Concurrent Work

Bi et al. (2026) propose a framework for automated acquisition of agent skills through mining open-source repositories, translating extracted procedural knowledge into standardized SKILL.md format. Their work addresses skill *creation* — how to produce agent skills from existing codebases — but not skill *verification* or *improvement*. A skill extracted from a GitHub repository has no mechanism to verify that an agent using that skill follows its procedures, and no mechanism to improve the skill through operational feedback.

AETHER's DAG process addresses the same creation challenge (distilling knowledge into agent artifacts) while DAGR adds the verification and education dimensions that Bi et al. do not address. The two approaches are complementary: repository mining could serve as an additional input source for the DAG process, with AEC providing the verification layer that extracted skills currently lack.
