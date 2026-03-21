---
section: "9-10"
title: Discussion, Conclusion, and References
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 9. Discussion and Limitations

### 9.1 Implications for Agent Accountability

AETHER demonstrates that the verification gap in current agent systems is an architectural choice, not an inherent constraint. The key insight is that knowledge graphs can serve simultaneously as retrieval stores, policy engines, and verification runtimes — the same artifact, compiled once, serving three functions. No existing framework we surveyed exploits this property.

The practical implication is immediate: any system that maintains a knowledge graph for RAG can, with the addition of type annotations and a compilation step, gain deterministic output verification at sub-millisecond cost. The verification does not require a separate infrastructure (no vector database, no judge model, no GPU). It requires only that the knowledge graph's nodes carry types that encode verification semantics.

### 9.2 The Skill Thesis Revisited

The experimental results support the five-property skill definition introduced in Section 3.1. The Jefferson capsule demonstrated Knowledge (51 KG nodes), Identity (persistent manifest with lineage), Expression (formal academic persona), Behavior (scholar agent type with AEC gates), and Improvement (0.143 → 0.889 through autonomous education). No property was simulated or mocked — each was exercised through the DAGR pipeline under standard conditions.

The portable proof — that the same capsule produces the same verification results regardless of which LLM generates the response — follows from the architecture: AEC compiles and verifies against the capsule's KG, not against the model's weights. The model is the engine. The skill is the asset. The model did not change. **The skill did.**

### 9.3 Relationship to Enterprise Architecture

SAP's published reference architecture for AI Agents and Tools (March 2026) provides a six-layer stack: Experience, Cognitive, Multi-Agentic, Capability, Backend, and SAP Systems layers. The Cognitive Layer includes an Enterprise Knowledge Graph and Document Grounding component. Content Filtering is present but operates on the input side — sanitizing what reaches the AI Engine. No output verification layer exists in the published architecture.

AEC addresses this gap directly. It sits between the AI Engine's response and delivery to the user, verifying compliance against the enterprise knowledge graph. The JSON-LD format used by both SAP's A2A protocol and AETHER's knowledge graphs enables native interoperability without format translation. A CAP (Cloud Application Programming) adapter exposing AEC as a service endpoint would require approximately 40 lines of integration code.

The broader enterprise implication: any organization that already maintains structured knowledge (ontologies, policy documents, compliance frameworks) can compile that knowledge into AEC verification detectors. The knowledge they already have becomes the verification engine they currently lack.

### 9.4 Multi-LLM Validation

During the development of AETHER, architectural decisions were independently reviewed by five LLM systems (Gemini, GPT-4, Kimi, Copilot, Grok) across two review rounds. Points of unanimous consensus included: the tiered deterministic-first verification architecture, the type-driven operator approach, the core/acquired immutability distinction, and the self-education loop as a genuine differentiator. This cross-model review process is itself a form of the verification thesis: no single model's opinion governs the architecture.

### 9.5 Limitations

We identify eight limitations of the current implementation, organized by severity.

**Negation blindness (High).** The blacklist detector does not understand negation. "Avoid using Inter" triggers a violation because "Inter" is in the blacklist, even though the agent is advising against the anti-pattern. Distinguishing "avoid Inter" from "use Inter" requires natural language understanding beyond tokenization — likely lightweight dependency parsing or negation scope detection. This is the most impactful known limitation.

**LLM-dependent scores (High).** Because the Generate stage uses an LLM, responses vary between runs. AEC scores for the same query against the same capsule can vary by ±0.15 depending on the specific response generated. The verification architecture is deterministic; the content being verified is not. Reproducibility requires fixing the response text, which we provide in the repository.

**Single-capsule evaluation (Medium).** All experimental results are from individual capsules tested in isolation. Multi-capsule interactions — where orchestrated queries traverse multiple agents — have not been evaluated for score propagation, latency accumulation, or error compounding.

**Layer 2 scalability (Medium).** Layer 2's LLM calls (2-8 seconds each) represent a latency and cost bottleneck in high-throughput environments. The architecture mitigates this through the cascade design — Layer 1 resolves the majority of statements deterministically before Layer 2 fires. However, capsules with thin knowledge graphs (few typed nodes, weak label overlap) will trigger Layer 2 more frequently. The primary mitigation is higher-quality DAG distillation: richer extraction produces more detectors, which means more Layer 1 matches, which means fewer Layer 2 calls.

**Threshold sensitivity (Medium).** The type-specific thresholds (Rules 0.50, Techniques 0.55, AntiPatterns 0.40, Concepts 0.30) were tuned empirically against one capsule (frontend-design, 73 nodes). Broader validation across diverse knowledge graphs — different domains, different node counts, different edge densities — is needed to confirm these values generalize. A grid search or learned threshold approach may be warranted.

**Augment weakness (Medium).** The top-3 KB paragraph matching in the Augment stage uses simple entity overlap, which misses semantically relevant paragraphs that use different terminology. A "Quick Answer" block at the top of each kb.md — a 50-word distilled summary that the Augment stage always retrieves — is a planned mitigation (not yet implemented).

**Education learns tokens, not principles (Low).** During frontend-design testing, the education loop acquired specific terms (font names, CSS property names) rather than generalizable design principles. The agent learned that "Playfair Display" is acceptable but did not generalize to "serif fonts with high contrast are appropriate for luxury." This suggests that education research prompts may need to request principles, not just facts.

**Single-hop edge traversal (Low).** Layer 3's edge policy traversal is limited to one hop — source to immediate target. Multi-hop reasoning chains (A avoids B, B requires C, therefore A has implications for C) are not evaluated. Extending to multi-hop introduces combinatorial complexity that must be bounded.

### 9.6 Threats to Validity

**Internal validity.** AEC scores are computed by the same system that generated the response. While Layers 1 and 3 are deterministic (no model involvement), Layer 2 uses an LLM call — introducing the same judge-bias concern we critique in Section 2.2. The mitigation is that Layer 2 is fallback only, the generosity guard constrains it, and the majority of statements are resolved by deterministic layers.

**External validity.** All capsules were created by the authors using the DAG process. No external capsule creators have tested the framework. The extraction skills may encode assumptions about source material structure that do not generalize to arbitrary documents.

**Construct validity.** The AEC score measures grounding against the capsule's own KG — not against ground truth. A capsule with an incorrect KG will produce high scores on incorrect responses. AEC measures consistency with stated knowledge, not correctness of that knowledge. An external auditor capsule (Section 10) addresses this.

**Conclusion validity.** The evaluation covers 29 capsules across five categories, providing preliminary evidence across diverse agent types. However, statistical power is limited: larger-scale evaluation across hundreds of capsules, diverse domains, and multiple LLM providers is needed to establish generalizability with confidence.

---

# 10. Conclusion, Broader Impact, and Reproducibility

### 10.1 Summary

This paper presented AETHER, a minimal agent framework where agents are portable skills — not code, not configurations, not transient sessions. Each agent is a capsule: five files in a folder carrying knowledge, identity, expression, behavior, and verification rules. Copy the folder. Copy the agent.

Two proprietary architectural processes govern the agent lifecycle. **DAG (Distilled Augmented Generation)** creates agents by distilling knowledge from any source, augmenting it with typed relationships, and generating a self-contained capsule. **DAGR (Distillation + Augment + Generation + Retrieval)** runs agents through a four-stage pipeline where the Retrieval stage compiles the knowledge graph into executable policy checkers and verifies every generated response.

**Agent Education Calibration (AEC)** — the verification engine within DAGR's Retrieval stage — transforms the knowledge graph from a passive data store into an active policy engine. The node's `@type` drives the verification strategy. The edges encode composed policies. Compilation runs once at load time in O(|N|). Verification runs in sub-millisecond time via set intersection. No embeddings. No vector databases. No GPU.

When verification fails, the self-education loop identifies the specific knowledge gaps, researches them via LLM, validates proposed knowledge through AEC itself, enforces a contradiction gate where immutable core knowledge holds absolute veto, and integrates verified triples. The agent that fails is the agent that learns. The failure specifies its own curriculum.

The model did not change. **The skill did.**

### 10.2 Future Work

**Near-term (designed, not built):**

*Negation detection.* Distinguishing "avoid Inter" from "use Inter" in the context of anti-pattern blacklists. Likely requires lightweight dependency parsing or negation scope detection beyond tokenization.

*Dynamic skill creation trigger.* Connecting gap detection (proven) to automatic DAG invocation (proven) — the ~20 lines of wiring that enable fully autonomous agent creation from detected need.

*External auditor capsule.* A separate agent whose sole function is skeptical verification of other agents' output, using a different persona, different knowledge graph, and potentially a different LLM — breaking the self-grading concern identified in Section 9.6.

*A2A subgraph exchange.* When agents communicate, they share typed, AEC-verifiable KG fragments rather than unstructured text. Each receiving agent verifies incoming knowledge against its own compiled policies before integration — creating trust chains where verification quality does not degrade with communication hops.

*Quick Answer block in kb.md.* A 50-word distilled summary at the top of each knowledge base that the Augment stage always retrieves, addressing the augment weakness identified in Section 9.5.

**Medium-term (research directions):**

*Knowledge decay.* Adding `utility_score` and `last_accessed` fields to acquired nodes with temporal decay at compile time. Nodes below a utility threshold are deprecated and excluded from compiled detectors — preventing unbounded KG growth.

*Multi-hop edge traversal.* Extending Layer 3 from one-hop to bounded multi-hop verification using type-constrained path enumeration. Legal but unverified paths classified as hypotheses and queued for education.

*Benchmark comparison.* Formal evaluation of AEC against RAGAS faithfulness, TruLens guardrails, and DeepEval metrics on a standardized dataset. This paper reports AEC results in isolation; comparative evaluation would strengthen the positioning.

*Cross-model generalization.* Systematic evaluation of the same capsules across Claude, GPT-4, Gemini, and open-source models to quantify the portability claim.

### 10.3 Broader Impact

AETHER's verification architecture has implications beyond the immediate agent framework context.

**For enterprise AI governance:** Organizations deploying AI agents in regulated industries (finance, healthcare, legal) require audit trails for every generated response. AEC's per-statement verdicts with matched node evidence provide exactly this — a complete, deterministic record of what the agent knew, what it verified, and what it could not ground. In the context of the EU AI Act, AEC's per-statement audit trail directly supports the transparency requirements of Article 13.

**For AI safety research:** The contradiction gate and anti-gaming mechanisms demonstrate that structural integrity can be enforced without relying on the model's cooperation. The agent cannot corrupt its own rules because the rules compile from immutable sources, and the agent never sees the compilation parameters. This is safety through architecture, not through training.

**For the open-source agent ecosystem:** The 280,000+ skills published across Claude Code, Copilot, and other platforms currently have no verification mechanism. AETHER's DAG process can ingest any SKILL.md and produce a self-verifying capsule — adding accountability to the existing skill ecosystem without requiring changes to the platforms that host those skills.

**Potential risks:** A verification system that produces high scores could create false confidence if the underlying knowledge graph is incorrect. AEC measures consistency with the capsule's own knowledge, not ground truth. Organizations deploying AEC should ensure that core KG nodes are reviewed by domain experts before production use. The external auditor capsule (Section 10.2) is designed to mitigate this risk.

### 10.4 Reproducibility Statement

All experimental results reported in this paper can be reproduced using the public repository:

**Repository:** `github.com/jeff0926/aether`

**Requirements:** Python 3.11+, standard library only. The `anthropic` SDK is required only for LLM-dependent experiments (Generate stage and Layer 2 verification). AEC compilation, Layer 1 verification, Layer 3 edge traversal, and orchestrator routing run without any external dependency.

**Reproducibility commands:**

```bash
# Factual grounding (Experiment 1)
python cli.py run examples/jefferson "When was Jefferson born?" --provider anthropic --report full
python cli.py run examples/jefferson "Jefferson vs Hamilton disagreements?" --provider anthropic --report full
python cli.py run examples/jefferson "Louisiana Purchase details and cost?" --provider anthropic --report full

# Skill verification (Experiment 2)
python cli.py run examples/frontend-design-v1.0.0-ff6ab491 \
  "How should I approach typography for a luxury brand?" --provider anthropic --report full

# Self-education (Experiment 3)
python cli.py educate examples/jefferson --item 0 --provider anthropic

# Orchestrator routing (Experiment 4)
python cli.py orchestrate "When was Jefferson born?" --registry ./examples --dry-run

# AEC standalone verification (no LLM required)
python cli.py verify "Thomas Jefferson was born in 1743" -r examples/jefferson/jefferson-kg.jsonld
python cli.py verify "Use Inter for body text" \
  -r examples/frontend-design-v1.0.0-ff6ab491/frontend-design-v1.0.0-ff6ab491-kg.jsonld
```

**Note on LLM variability:** Because the Generate stage uses an LLM, exact AEC scores will vary between runs as the model produces different responses. The verification architecture is deterministic — the same response text against the same compiled KG will always produce the same score. Reference response texts for all reported scores are available in the repository.

**Capsule corpus:** 29 capsules are included in the repository's `examples/` directory, spanning factual scholars, procedural skill agents, executive advisors, validators, and the orchestrator. All were created through the DAG process described in Section 4.

---

## References

1. Lewis, P., et al. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." NeurIPS 2020.
2. Guu, K., et al. "REALM: Retrieval-Augmented Language Model Pre-Training." ICML 2020.
3. Es, S., et al. "RAGAS: Automated Evaluation of Retrieval Augmented Generation." arXiv:2309.15217, 2023.
4. Liu, Y., et al. "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment." arXiv:2303.16634, 2023.
5. Zheng, L., et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023.
6. Chase, H. "LangChain." GitHub, 2022.
7. Wu, Q., et al. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." arXiv:2308.08155, 2023.
8. Microsoft. "Semantic Kernel." GitHub, 2023.
9. Joao, M., et al. "CrewAI: Framework for Orchestrating Role-Playing AI Agents." GitHub, 2024.
10. Bai, Y., et al. "Constitutional AI: Harmlessness from AI Feedback." arXiv:2212.08073, 2022.
11. Ouyang, L., et al. "Training Language Models to Follow Instructions with Human Feedback." NeurIPS 2022.
12. Wang, G., et al. "Voyager: An Open-Ended Embodied Agent with Large Language Models." arXiv:2305.16291, 2023.
13. Hu, S., et al. "Automated Design of Agentic Systems." arXiv:2408.08435, 2024.
14. Yao, S., et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023.
15. Sun, H., et al. "AdaPlanner: Adaptive Planning from Feedback with Language Models." NeurIPS 2023.
16. Knublauch, H. & Kontokostas, D. "Shapes Constraint Language (SHACL)." W3C Recommendation, 2017.
17. Bordes, A., et al. "Translating Embeddings for Modeling Multi-relational Data." NeurIPS 2013.
18. Sun, Z., et al. "RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space." ICLR 2019.
19. W3C. "JSON-LD 1.1." W3C Recommendation, 2020.
20. Bi, S., et al. "Automating Skill Acquisition through Large-Scale Mining of Open-Source Agentic Repositories." arXiv:2603.11808, March 2026.
21. Steinberger, P. "SoulSpec: The Open Standard for AI Agent Personas." soulspec.org, 2025.
22. Smith, M. "An AI Agent Blackmailed a Developer. Now What?" IEEE Spectrum, March 2026.
23. SAP. "AI Agents and Tools — Reference Architecture." docs.udex.services.sap.com, 2026.
24. Kim, S., et al. "FactKG: Fact Verification via Reasoning on Knowledge Graphs." ACL 2023.

---

*AETHER — Adaptive Embodied Thinking : Holistic Evolutionary Runtime*
*864 Zeros LLC — March 2026*
*github.com/jeff0926/aether*
