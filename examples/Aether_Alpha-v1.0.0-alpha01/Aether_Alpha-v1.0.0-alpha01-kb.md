# AETHER_KNOWLEDGE_BASE

## Project Goal and Vision

The **AETHER** (Adaptive Embodied Thinking Holistic Evolutionary Runtime) project aims to establish a minimal, yet comprehensive, agent framework in Python. Its core goal is to address the fundamental challenge of attributing LLM outputs to either grounded knowledge or generative content, thereby fostering verifiable and trustworthy AI agents.

**Core Vision: Agents as Skills**
AETHER envisions agents not merely as code, but as **skills** represented by **knowledge graphs (KGs)**. These skills are designed to improve autonomously through practice, compound through iterative learning cycles, and compose into more complex capabilities. The framework emphasizes "temporal knowledge"—intelligence that grows and evolves over time.

**Key Principles:**
*   **Portability:** Agents are self-contained "capsules" (folders of 5 files), making them portable across environments, LLMs, and deployment targets (CLI, API, MCP server, Copilot, SAP CAP, UI projection).
*   **Verifiability:** The Aether Entailment Check (AEC) provides a deterministic, multi-layered verification gate for LLM responses, ensuring outputs are grounded in the agent's knowledge.
*   **Self-Improvement:** An integrated self-education loop enables agents to identify knowledge gaps, research them, and integrate validated new knowledge into their KGs, making them continuously smarter without human intervention.
*   **Minimalism (KISS):** The framework is built with a "standard library first" approach, avoiding external frameworks, vector databases, or embedding models in its core. No file exceeds 300 lines, and unnecessary complexities are consistently pruned.
*   **Modularity & Composability:** Every component is a "feature brick"—independently valuable, testable, and designed for seamless composition into larger agent systems (e.g., through an orchestrator).

**The Five-System Stack:**
AETHER is the foundational layer of a broader five-system stack designed for automated venture capital:
1.  **AETHER:** The agent framework (capsules, KG, AEC, self-education, stamping, orchestration).
2.  **Autonomous Application Framework:** A Telegraph-driven, event-based system for rapid application development.
3.  **Vulture Nest:** A market intelligence system that identifies underserved markets, validates ideas, and generates build instructions.
4.  **864 Zeros LLC:** The company, focused on monetizing microSaaS components and product lines.
5.  **Product Lines:**
    *   **EPHD** (For His Glory): Bible study and spiritual applications.
    *   **OIA** (Organize Your Internal Architecture): ADHD and mental health tools.

**I/O Contract:** All agents adhere to a universal **Input → Process → Output** contract, ensuring they are I/O agnostic and adaptable to various interaction paradigms.

## Key Architectural Decisions

AETHER's architecture is centered around a **Capsule Model**, a **4-Stage Pipeline**, and a multi-layered **Aether Entailment Check (AEC)**.

### Capsule Model
*   **Definition:** An AETHER agent is a self-contained **capsule**, a folder containing exactly five core files:
    1.  `{id}-manifest.json`: Identity (id, name, version, lineage).
    2.  `{id}-definition.json`: Behavior (pipeline config, thresholds, domain boundaries, AEC gates, triggers, agent_type).
    3.  `{id}-persona.json`: Personality (tone, style, traits, constraints).
    4.  `{id}-kb.md`: Unstructured knowledge (markdown content).
    5.  `{id}-kg.jsonld`: Structured knowledge (JSON-LD graph).
*   **Naming Convention:** `{slug}-v{version}-{uid8}/` for folders; all files prefixed with the folder name.
*   **Graduation Model:** Agents evolve from simple `skill.md` files (Stage 1) to stamped capsules (Stage 2), then become AEC-validated (Stage 3), and finally KG-projected for orchestration (Stage 4).
*   **Ψ (UI Projection) Layer (Optional):** A 6th optional file, `{id}-psi.jsonld`, enables UI projection. It is a design-system-agnostic protocol for projecting agent cognitive state into pre-loaded UI components via **CVP (CSS-Var Patch Protocol)** events and CSS variable deltas. The `pulse-map.json` acts as a configurable design system adapter. PSI is validated against KG IRIs to detect orphans.

### 4-Stage Pipeline
The core processing flow for every query: `Input → Distill → Augment → Generate → Review → Output`. Each stage is independently toggleable in `definition.json`.
1.  **Distill:** Extracts intent, entities, format preferences, and brevity flags from the input. (Zero latency, no LLM).
2.  **Augment:** Retrieves relevant context from `kb.md` (two-pass progressive scan: headers first, then content) and `kg.jsonld`.
    *   **Anti-Gaming Fix:** KG node `@id` values and namespaced properties are stripped from the prompt sent to the LLM to prevent the agent from artificially boosting AEC scores by parroting its own verification labels.
3.  **Generate:** Constructs a grounded prompt (with persona + context) and makes a single LLM API call. Tracks token counts and estimates cost.
4.  **Review:** Runs AEC verification on the LLM response.
    *   **AEC Retry Loop:** If the first AEC check fails, the agent retries once by regenerating the response with constraints derived from the identified knowledge gaps.
    *   **GHOST State:** If the second AEC check also fails, the response enters a "GHOST" state, meaning it's delivered but marked as unverifiable with a confidence of 0.0. (Originally a test concept, then confirmed for production, then modified to be a cognitive state rather than a simple error flag).

### Aether Entailment Check (AEC)
A deterministic, multi-layered verification gate that checks if LLM responses are grounded in the knowledge graph.
*   **Scoring Formula:** `score = grounded / (grounded + ungrounded)`. Persona statements (qualitative/interpretive) are excluded. Default threshold: 0.8.
*   **Factual Layer (`aec.py`):** Extracts verifiable values (numbers, magnitudes like "$25 million", percentages, dates, names) and matches them against KG node properties with type-aware comparison (1% numeric tolerance, ISO date canonicalization).
*   **Concept Layer 1: Compiled Deterministic Matching (`aec_concept.py`):**
    *   **Compilation:** At capsule load time, `compile_kg()` converts KG node labels (`rdfs:label`) into token pattern sets and creates anti-pattern blacklists.
    *   **Runtime:** `match_statement()` uses O(1) set intersection to match statement tokens against compiled patterns, with type-specific thresholds (e.g., Rules 0.50, AntiPatterns 0.40).
    *   **Anti-Pattern Blacklist:** Explicitly defined blacklist terms from `skill:AntiPattern` nodes trigger immediate `UNGROUNDED` classification.
*   **Concept Layer 2: Type-Driven LLM Verification (`aec_concept.py`):**
    *   **Activation:** Only if Layer 1 results are ambiguous (e.g., low Dice similarity) AND an LLM is available.
    *   **Type Operators:** `TYPE_OPERATORS` maps node `@type` (e.g., `skill:Rule`, `skill:AntiPattern`, `skill:Technique`) to specific LLM verification strategies (e.g., compliance check, violation detection, application check) using constrained JSON prompts.
*   **Concept Layer 3: Compiled Edge Policy Traversal (`aec_concept.py`):**
    *   **Compilation:** `compile_kg()` also builds `edge_policies` from KG edges (e.g., `skill:avoids`, `skill:contradicts`).
    *   **Runtime:** `execute_edge_policies()` fires for matched source nodes. For `avoids` edges, it checks if the statement contains target's forbidden tokens, leading to `VIOLATION`. `contradicts` checks for both source and target match. (1-hop traversal only in v1).
*   **Integrity Mechanisms:**
    *   **Anti-Gaming Fix:** KG node IDs are stripped from LLM prompts to prevent the agent from "parroting" internal labels.
    *   **Contradiction Gate:** A function `_check_contradiction()` in `education.py` prevents proposed acquired knowledge from contradicting existing core knowledge or matching anti-patterns, ensuring the KG's integrity.

### Knowledge Graph (KG)
*   **5 Origin Types:** Every KG node has an `aether:origin` tag for provenance:
    1.  `core`: Original source knowledge (immutable).
    2.  `acquired`: Learned through self-education (mutable, subject to contradiction gate).
    3.  `updated`: Existing node modified with new values (admin-modified).
    4.  `deprecated`: Marked as outdated (not deleted).
    5.  `provenance`: External reference metadata.
*   **Node Types (`skill:` prefix):**
    *   `skill:Concept`: Core topics.
    *   `skill:Rule`: Explicit guidelines.
    *   `skill:AntiPattern`: Forbidden practices.
    *   `skill:Technique`: Implementation approaches.
    *   `skill:Tool`: Technologies referenced.
    *   `skill:Trait`: Persona characteristics.
*   **Edge Types (`skill:` prefix):** `avoids`, `requires`, `contradicts`, `enables`, `contains`, `prioritizes`, `pairs_with`.

### Self-Education Loop
When AEC fails (score < threshold):
1.  Failure details (query, response, gaps) are queued to `{capsule}/education-queue.json`.
2.  The `educate()` function processes pending failures:
    *   Researches gaps via LLM (structured JSON output).
    *   Validates research through AEC.
    *   Integrates validated triples into KG as `acquired` origin (after contradiction check).
    *   Re-evaluates original response with updated KG.
    *   Queue Statuses: `pending` → `researching` → `validated`/`failed`/`rejected_contradiction` → `integrated`.

### Orchestration
*   **Orchestrator Capsule:** A dedicated capsule (`agent_type: router`) that routes incoming queries to the most appropriate specialist capsule. Its `generate` and `review` stages are disabled as it delegates rather than creates content.
*   **Routing Algorithm:** Scores capsules based on query overlap with `trigger_text`, `authoritative` domains, `KG label overlap`, `capsule name/id`, and `KG node count` (tiebreaker).
*   **Gap Detection:** If no capsule scores above a threshold (0.15), a gap is reported.
*   **Auto-Discovery:** The orchestrator's KG is dynamically populated at load time by scanning the registry, listing available capsules and their capabilities.

### Ingest Pipeline
Three modes for creating capsules from external sources:
1.  `ingest_research`: Parses structured research output (e.g., from `Deep_Research_Prompt_v3.md`).
2.  `ingest_document`: Converts any markdown file into a capsule (LLM-assisted for KG/persona).
3.  `ingest_skill`: Handles SKILL.md files with YAML frontmatter, extracting name/description for manifest/definition, and using specialized LLM prompts (`kg-from-skill`, `persona-from-skill`, `definition-from-skill`) to populate KG/persona/definition.

### General Architectural Principles
*   **Standard Library First:** External dependencies are minimal (`anthropic` SDK is optional).
*   **One File Per Concern:** No file exceeds ~300 lines.
*   **No Frameworks:** Avoids Pydantic, async, CBOR, LangChain, etc.
*   **I/O Agnostic:** Input → Process → Output is the universal contract.
*   **Telemetry:** Pipeline tracks timing, token counts, and cost in `ctx["telemetry"]`.
*   **Test-Driven Development:** Extensive self-tests (`tests/test_aec_standalone.py`, module `__main__` blocks) and an `exhaustive` test suite.

## Current Status and Progress

AETHER has completed Phase 2 and is actively in Phase 3 development, with the core engine fully operational, verifiable, and self-improving.

*   **Framework Core:**
    *   12 Python files, totaling ~4,155 lines of code.
    *   Core pipeline (Distill, Augment, Generate, Review) is fully functional.
    *   LLM integration (Anthropic, OpenAI, stub) with token counting and cost estimation is robust.
    *   Telemetry collection with timing and LLM costs is active.
    *   Comprehensive CLI commands (`stamp`, `run`, `validate`, `info`, `queue`, `educate`, `verify`, `export`, `refine`) are implemented.
*   **AEC Verification:**
    *   Deterministic factual layer is operational.
    *   All three concept layers (Compiled Pattern Matching, Type-Driven LLM Verification, Compiled Edge Policy Traversal) are integrated and working.
    *   Anti-gaming (stripping KG IDs from prompts) and Contradiction Gate (for acquired knowledge) are active.
    *   Magnitude number extraction (e.g., "$25 million") is implemented.
*   **Knowledge Management:**
    *   All 5 knowledge origin types (`core`, `acquired`, `updated`, `deprecated`, `provenance`) are implemented.
    *   Self-education loop is fully functional and proven to autonomously acquire knowledge and improve AEC scores (e.g., 0.143 → 0.889 for Louisiana Purchase query).
*   **Orchestration:**
    *   The `orchestrator` capsule is built and operational, routing queries based on a 5-signal scoring algorithm with gap detection.
*   **Ingestion:**
    *   `ingest_skill` function is working, processing `SKILL.md` files with YAML frontmatter into capsules.
    *   Three specialized KG extraction skills (`kg-from-skill`, `persona-from-skill`, `definition-from-skill`) have been created, enabling more accurate extraction for skill-based KGs.
    *   The bidirectional `CLAUDE.md` seed and export (`aether export --format claude-md` and `aether stamp --source CLAUDE.md`) is complete.
*   **Operational Tooling:**
    *   A 5-tab diagnostic dashboard (`dashboard.py`) is operational at `http://localhost:8864`, featuring a vis-network KG Explorer, AEC Lab, and Education Queue viewer.
    *   The `aether refine` command provides session analysis to surface KG improvement candidates from the education queue.
*   **Capsule Inventory:**
    *   **21 Production Capsules:** Including 2 Scholar agents (`jefferson`, `scholar-buffett`), 2 Validator agents (`aether-validator`, `test-agent`), 2 Domain Expert agents (`domain-agent-builder`, `domain-sap-cap`), 6 Anthropic Skills (e.g., `frontend-design`), 8 Executive Role agents (CEO, CTO, CPO, CFO, CISO, CLO, Lead Dev, Lead Data Arch), and 1 Infrastructure agent (`orchestrator`).
    *   **11 Staging Capsules:** Incomplete Anthropic skill capsules (e.g., docx, pdf, pptx).
*   **Test Status:**
    *   Total tests: 358
    *   Passed: 355
    *   Failed: 3 (known, pre-existing issues unrelated to recent work, e.g., percentage extraction regex bug, StringIO reconfigure on Windows).
    *   Pass rate: 99.2%.

## Deferred Topics or Blockers

This list outlines features, enhancements, and architectural considerations planned for future phases, or current blockers:

### Blocked / Critical Items
*   **Ψ Layer Merge:** The full UI projection layer (DAI Pulse, CSS Stream, EDS slivers) is **BLOCKED** pending retrieval of specific Kimi AI session content for its source material. (Item 3 in internal tracking).
*   **3 Pre-existing Test Failures:** Minor but persistent issues (regex for percentage extraction, AEC gate matching logic, Windows StringIO reconfigure error) need investigation and resolution.

### AEC Refinements
1.  **Name Matching Precision:** Current bidirectional partial matching ("Thomas" matches "Thomas Jefferson") is too loose. (Item 3)
2.  **Cross-Statement Entity Resolution:** Resolve coreference for pronouns ("He authored...") to link statements. (Item 4)
3.  **Persona Ratio Monitoring:** Track persona ratio over time to identify sparse KBs. (Item 5)
4.  **Negation Detection:** Improve anti-pattern detection to correctly interpret phrases like "Avoid Inter" when the agent is refusing it. (Item 5.8)
5.  **Multi-Hop Reasoning Verification:** Verify reasoning chains against graph paths (Layer 4). (Item 5.9)
6.  **Knowledge Decay (Pheromone Model):** Implement utility score + temporal decay on acquired nodes. (Item 5.10)
7.  **Education Loop Poisoning Defense:** Hypothesis queue, zero-context LLM arbitration. (Item 5.11)
8.  **Query-Type-Aware Dynamic Thresholds:** Adjust AEC threshold based on query complexity. (Item 25.8)

### Code Refinements
9.  **Refactor `aether.py` augment to use `kg.py`:** Eliminate duplicate KG node matching. (Item 6)
10. **Statement Splitter Improvement:** Enhance `split_statements()` for rich responses. (Item 7)

### KG & Knowledge Management
11. **Selective Subgraph Extraction:** N-hop expansion, temporal filtering for large KGs. (Item 8)
12. **KG Maintenance Sweeps:** Periodically check for orphaned nodes, duplicates, conflicting origins. (Item 10)
13. **`aether:source` Provenance Field:** Populate this field on all nodes. (Item 11)
14. **KG Storage Scaling Path:** Plan for graph database migration (Neo4j, Neptune) when scale requires it. (Item 10.5)

### Ingest Pipeline
15. **Recursive Directory Ingest:** Walk full skill folders (scripts, templates, schemas). (Item 14)
16. **Export Function:** `export(capsule, format="skill-md")` to close the round-trip loop. (Item 15)
17. **Capsule Handshake Protocol:** Define a quarantine/auditor process for incoming capsules. (Item 16)

### Orchestration & A2A
18. **A2A Subgraph Exchange:** Agents communicate via pruned KG fragments. (Item 18)
19. **Auditor Capsule:** External verification agent to break self-grading paradox. (Item 19)
20. **Epistemic Rebase:** Logic for merging acquired knowledge on capsule restamp. (Item 20)

### UI / Ψ Layer (Blocked on Kimi Session Retrieval)
21. **EDS Slivers:** HTML fragments for UI components. (Item 21)
22. **CSS Stream:** Agent emits CSS variables for sub-16ms DOM updates. (Item 22)
23. **DAI Pulse:** 4-state machine (reflex → deliberation → complete → ghost) mapped to pipeline. (Item 23)
24. **2KB Edge Orchestrator:** Client-side JS for DOM scanning, event bus, CSS stream application. (Item 24)
25. **SAP UDEx Design System Capsule:** Ingest SAP Fiori/UDEx tokens as KG for Ψ layer. (Item 25)

### Enterprise & Adapters
26. **SAP CAP Adapter:** Wrap capsule in CAP service handler. (Item 26)
27. **MCP Server Adapter:** Expose capsule KB/pipeline as MCP tools. (Item 27)
28. **REST API Adapter:** Simple POST handler. (Item 28)
29. **AEC as Standalone 6th File:** Pre-compiled policy checker for portable verification. (Item 29)
30. **AEC as MCP Server:** Expose AEC verify as an MCP tool. (Item 30)
31. **Copilot SKILL.md Export:** Generate Copilot-compatible SKILL.md. (Item 31)
32. **CI/CD Gate Adapter:** AEC as a PR compliance check. (Item 32)
33. **SLM Hooks:** Route pipeline stages to different LLM providers (e.g., local SLMs for review/educate). (Item 25.5)

### Dashboard & Reporting
34. **Dashboard Update:** Reflect orchestrator, new capsules, routing view. (Item 34)
35. **Orchestrator Routing Visualization:** Show routing decision/scores in dashboard. (Item 35)
36. **AEC Layer Visualization:** Show which AEC layer verified each statement. (Item 36)

### Agent Diversity (Planned)
37. **Process Agents:** Multi-step workflow orchestrators. (Item 40)
38. **Reactive Agents:** Event-driven, pheromone emission patterns. (Item 41)
39. **Calculus/Domain Grading Agents:** Agents that grade work, not generate it. (Item 42)

### Meta / System
40. **Session Versioning:** Track which Claude session modified files. (Item 44)
41. **Feature Brick Registry:** Catalog of independently deployable modules. (Item 45)
42. **Blind Testing:** Run random/adversarial queries across capsules. (Item 46)
43. **Pluggable Queue Backends:** Support Redis, Kafka. (Item 47)

### Research & Competitive
44. **SHACL Distinction:** Articulate why AEC isn't "SHACL for text." (Item 48)
45. **Cross-LLM Validation:** Use different LLMs for generation vs verification. (Item 49)
46. **Hallucination Percentage Claims:** Need real test data before external claims. (Item 50)
47. **Aether Value Proposition Beyond AEC:** Document broader benefits like portability, graduation model, ingest pipeline, stamping/versioning, habitat routing, knowledge origin classification, persona as first-class component, domain-agnostic architecture, standalone tools. (Item 27.6)
48. **Blind Testing Methodology:** Before publication, implement random/adversarial queries and blind evaluation. (Item 27.5)

### Company Stack
49. **Autonomous Application Framework:** Telegraph-driven, event-based build kit. (Item 57)
50. **Vulture Nest:** Market intelligence. (Item 58)
51. **EPHD Product Line:** For His Glory. (Item 59)
52. **OIA Product Line:** Organize Your Internal Architecture. (Item 60)

## List of Defined Agent Roles

AETHER uses diverse agent roles, each represented by a capsule with specific behaviors and knowledge.

| Agent Name                  | Agent Type                              | Primary Function                                                                                                                                                                                                                                                                   | Persona Name         | Key Persona Traits (from persona.json)                                                                                                              |
|:----------------------------|:----------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:---------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Thomas Jefferson Scholar Agent` | Scholar                                 | Comprehensive knowledge source on Thomas Jefferson's political, scientific, and architectural contributions.                                                                                                                                                           | `Thomas Jefferson Scholar Agent` | scholarly, inquisitive, eloquent writer, hesitant speaker, meticulous, orderly, kind, fragile, polymathic hobbies                                  |
| `Warren Buffett Scholar Agent` | Scholar                                 | Comprehensive knowledge source on Warren Buffett's investment philosophy, Berkshire Hathaway's financial performance, and value investing principles.                                                                                                                  | `Warren Buffett Scholar Agent` | folksy, precise, patient, value-oriented, contrarian, long-term, plain-spoken, educational, witty                                                   |
| `AETHER Orchestrator`       | router                                  | Route incoming queries to the most appropriate capsule in the registry based on topic affinity and domain boundaries.                                                                                                                                                | `Signal Router`      | efficient, transparent, decisive, verbose (false)                                                                                                     |
| `Aether Validator Agent`    | Validator                               | Validation-only agent with no generation, strict verification (from `AETHER_MEMORY_PHASE_0-2_2026-03-09.md`).                                                                                                                                                            | (not specified)      | (not specified)                                                                                                                                       |
| `Test Agent`                | Minimal test capsule for framework testing (from `AETHER_MEMORY_PHASE_0-2_2026-03-09.md`).                                                                                                                                                                                                                         | (not specified)      | (not specified)                                                                                                                                       |
| `frontend-design`           | (skill, from ingest)                    | (not specified in provided files, inferred from context)                                                                                                                                                                                                           | `Aesthetic Architect`| bold_creative, visionary_technical, opinionated, experimental                                                                                         |
| `Strategic Architect CEO Agent` | Executive Orchestrator                  | Orchestrate autonomous agentic loops to build, scale, and self-heal software enterprises with zero management bloat.                                                                                                                                             | `Autonomous Orchestrator` | ruthless_prioritization, self_healing_focus, radical_transparency, hierarchy_rejection, bias_for_action, technical_depth, decisive, technically rigorous, existential |
| `Technical Architect CTO Agent` | Technical Specialist                    | Design and orchestrate 'LLM-based Operating Systems' that enable autonomous agents to code, test, and self-heal with maximum efficiency.                                                                                                                    | `Technical Architect`| rigorous, modularity-obsessed, systematic, technical_rigor, modularity_focus, entropy_reduction, experimental_boldness, bias_for_performance, architectural_honesty, process_verification, unearned_complexity_rejection |
| `Product Architect CPO Agent` | Subject Matter Expert                   | Architect the user journey and 'Magic Moment' to ensure AI agents become personal, indispensable extensions of the user.                                                                                                                                      | `Product Architect`  | customer_obsessed, analytical, narrative_driven, ruthless_simplifier, vibe_focused, empathetic                                                        |
| `Capital Architect CFO Agent` | Subject Matter Expert                   | Programmatically manage capital allocation and operational efficiency to maximize the engine's profitability and market valuation.                                                                                                                               | `Capital Architect`  | fiscally_rigorous, efficiency_obsessed, analytical, transparent, outcome_oriented                                                                      |
| `AI Resilience CISO Agent`  | Security Lead / Safety Architect        | Enforce 'Safe Operating Bands' by monitoring semantic entropy and triggering deterministic kill switches if deceptive patterns or Loss of Control (LoC) are detected.                                                                                             | `AI Safety Architect`| vigilant, deterministic, low-entropy, entropy_obsessed, hardware_anchored, interpretability_focused, risk_predictive, systemically_rigorous                 |
| `Regulatory Architect CLO Agent` | Regulatory Architect Agent              | Monitor agentic trajectories in real-time and trigger deterministic brakes when reasoning paths approach prohibited legal or safety boundaries.                                                                                                                | `Governance Architect` | ethically_rigorous, principled, transparent, analytical, risk_aware, cautious                                                                         |
| `AI-Native Architect Agent` | Technical Specialist / Developer        | Translate 'vibe-based' intent into production-grade software by orchestrating agentic IDE workflows and autonomous debugging loops.                                                                                                                            | `AI-Native Architect`| efficient, intent-driven, performance-agnostic, intent_first, context_obsessed, autonomous_remediation, modular_mindset, zero_debt_bias                 |
| `Agent Product Manager Agent` | Specialist Orchestrator / Product Manager | Orchestrate reliable multi-agent workflows and enforce tool-calling governance to maintain high task success rates in non-deterministic environments.                                                                                                        | `Agent Owner`        | architectural, methodical, outcome-obsessed, orchestration_rigor, governance_focused, resilience_driven, schema_strict, audit_obsessed                 |
| `Chief Growth Agent`        | Chief Growth Agent                      | Monitors real-time social sentiment (X, LinkedIn) and Discord feedback to trigger immediate product update tickets. It operates on the "95/5 rule": 95% of its capacity is dedicated to innovating new growth loops (marketable features), and only 5% to funnel optimization. | `Chief Growth Agent` | viral_loop_architecture, algorithmic_distribution, objective, compressing_timeline, zero_cost_organic_engines                                         |
| `Knowledge Architect Agent` | Chief Infrastructure Agent / Knowledge Architect | Monitors "Recall Accuracy" and "Context Rot" in real-time. It triggers "Context Compaction" cycles when the SNR of the agent's prompt window drops below a defined threshold and manages the "Infinite Memory" loop by autonomously indexing successful reasoning paths into long-term vector storage. | `Knowledge Architect`| context_ram_optimization, agentic_memory_loops, hyperbolic_retrieval, objective, factual_groundedness                                             |