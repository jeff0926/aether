---
section: 7
title: System Architecture
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 7. System Architecture

This section describes the system-level components that support the DAG creation process and DAGR runtime pipeline: the capsule registry, the orchestrator, dynamic skill creation, and a brief overview of the Ψ (Psi) projection layer for UI actuation.

### 7.1 The Habitat: Capsule Registry and Routing

The Habitat is AETHER's capsule discovery and routing system. It scans a directory for valid capsule folders, indexes their capabilities from their definition files, and routes incoming queries to the most appropriate capsule.

**Discovery** is filesystem-based. Any directory containing the five required capsule files (manifest, definition, persona, KB, KG) is registered as an available agent. Adding a new agent means adding a folder. Removing an agent means removing a folder. No database, no configuration file, no restart required.

**Routing** uses a weighted scoring algorithm against five signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Trigger text overlap | 0.25 | `definition.json` trigger_text field |
| Authoritative domain overlap | 0.25 | `definition.json` domain_boundaries.authoritative |
| KG label overlap | 0.30 | All `rdfs:label` values across the capsule's KG nodes |
| Capsule name overlap | 0.10 | Manifest name field |
| KG node count (normalized) | 0.10 | Graph size as tiebreaker |

Query tokens are compared against each signal using the same `tokenize()` function from AEC Layer 1, ensuring consistency between routing and verification vocabularies.

**Gap detection** activates when the highest-scoring capsule falls below a threshold of 0.15. This indicates no capsule in the registry adequately covers the query's topic. The gap is reported with the closest match and its score, providing a structured signal for dynamic skill creation (Section 7.3). Description-based semantic routing — using the capsule's `definition.json` description field as a secondary signal — is planned as a future enhancement (Section 10.2).

### 7.2 The Orchestrator Capsule

The orchestrator is itself a capsule — a 5-file directory with `agent_type: "router"`. It has a manifest, a definition, a persona (operational, precise, zero embellishment), a KB describing routing methodology, and a KG that is populated dynamically from the registry at load time.

The orchestrator's Generate and Review stages are disabled. It does not generate content. It does not verify content. It routes queries to specialist capsules and returns their results. The user asks a question. The orchestrator determines who should answer. The specialist runs its full DAGR pipeline including AEC verification. The verified response returns through the orchestrator.

This design means the orchestrator eats its own cooking — it is built using the same capsule format it routes to, demonstrating that the format is universal enough to represent both content agents and infrastructure agents.

**Routing in practice:**

```bash
# User doesn't need to know which agent exists
python cli.py orchestrate "When was Jefferson born?" --registry ./examples

# Output:
# Routing: "When was Jefferson born?"
#   Candidates:
#     Thomas Jefferson Scholar Agent  score=0.21 ★ SELECTED
#     doc-coauthoring                 score=0.19
#     ...
#   Dispatching to: Thomas Jefferson Scholar Agent
#
#   Thomas Jefferson was born on April 13, 1743...
#   AEC Score: 1.00 (threshold: 0.8) — PASS
```

Tested routing across three agent categories:

| Query | Routed To | Category | Score |
|-------|-----------|----------|-------|
| "When was Jefferson born?" | jefferson | Scholar | 0.21 |
| "What is our strategic vision?" | CEO | Executive Advisor | 0.30 |
| "How should I approach typography?" | frontend-design | Skill Agent | 0.23 |
| "Configure a Kubernetes cluster?" | GAP DETECTED | — | <0.15 |

The Kubernetes query triggers gap detection — no capsule in the registry covers this topic. This gap signal is the input for dynamic skill creation.

### 7.3 Dynamic Skill Creation

When the orchestrator detects a gap, the system has the architectural components to create a new agent autonomously:

```
Gap detected ("Kubernetes" — no capsule matches)
  → Intent captured (D(Q) from Distill provides entities and domain)
  → Research (same LLM mechanism as education loop)
  → Extract (K_graph and K_text from DAG's distillation function)
  → Stamp (stamper generates capsule with UID and lineage)
  → Register (Habitat discovers the new folder)
  → Route (next query on this topic reaches the new capsule)
  → Verify (AEC checks the new capsule's output)
  → Educate (failures improve the new capsule)
  → Mature (after N education cycles, capsule reaches production quality)
```

Each step in this chain is independently implemented and tested. The gap detection is proven. The research mechanism is proven (education loop uses it). The extraction skills are proven (DAG process, Section 4). The stamper is proven. The Habitat discovery is proven. AEC verification is proven. The education loop is proven.

The chain connecting gap detection to automatic capsule creation — the trigger that fires the DAG process from an orchestrator gap signal — is the designed but unbuilt link. It represents approximately 20 lines of code connecting two proven subsystems. The architectural capability exists; the wiring does not yet.

This is the self-creating system: agents that detect what is missing and build what is needed. The orchestrator identifies the gap. DAG creates the agent. DAGR verifies the agent. The education loop improves the agent. The skill emerges from the need.

### 7.4 Feature Brick Architecture

The capsule's 5-file format enables compositional agent creation. Each file is an independently swappable component — a feature brick:

| Brick | What It Carries | Swap Scenario |
|-------|----------------|---------------|
| Persona | Voice, tone, reasoning style | Same knowledge, different personality |
| KB | Domain expertise (markdown) | Same personality, different domain |
| KG | Verification rules, typed policies | Same KB, different compliance requirements |
| Definition | Pipeline config, triggers, thresholds | Same agent, different operational parameters |
| Manifest | Identity, lineage | Re-stamp for new version |

A new agent can be composed by selecting bricks from existing agents: the CEO persona + the SAP KB + the compliance KG + a custom definition = a specialized SAP compliance advisor capsule. The stamper generates the new manifest with lineage tracking both source capsules.

This compositional model is architectural — enabled by the file-based design — but the tooling for browsing, selecting, and assembling bricks (a visual catalog) is not yet built.

### 7.5 Capsule Inventory

The current implementation includes 29 capsules across five categories:

| Category | Count | Examples | KG Nodes |
|----------|-------|---------|----------|
| Scholars | 2 | Thomas Jefferson (51 nodes), Warren Buffett (48 nodes) | Rich factual graphs |
| Skill Agents | 6 | frontend-design (73 nodes), brand-guidelines, claude-api, doc-coauthoring, skill-creator, mcp-builder | Typed Rules/AntiPatterns/Techniques |
| Validators | 2 | aether-validator, test-agent | Verification-focused |
| Executive Advisors | 8 | CEO (55 nodes), CTO, CPO, CFO, CISO, CLO, Lead Dev, Lead Data Architect | Domain advisory |
| Infrastructure | 1 | Orchestrator (router) | Capability graph |

All capsules were created through DAG (Section 4) — 17 from Anthropic's official SKILL.md files, 8 from Gemini-generated executive research with AETHER extraction skills, and 4 from manual construction during framework development. All operate through the same DAGR pipeline and AEC verification. Capsules operate independently; multi-capsule interaction is mediated exclusively through the orchestrator.

### 7.6 The Ψ (Psi) Projection Layer

AETHER includes a projection layer that enables agents to actuate browser UI directly, without a frontend framework intermediary. The thesis: agents should not output JSON for a frontend to interpret — they should project their cognitive state as visual changes in real time.

The Ψ layer comprises four components:

**CSS Variable Patch (CVP) Protocol.** Instead of returning structured text, the agent emits a stream of CSS custom property mutations via Server-Sent Events. These semantic variables describe agent state: `--aether-state: deliberation`, `--aether-confidence: 0.85`, `--aether-sentiment: positive`. Any system that supports CSS custom properties — every modern browser, every framework — can consume them.

**DAI Pulse (Dynamic Adaptive Intelligence Pulse).** A four-phase state machine mapped to DAGR pipeline stages: *reflex* (Distill complete, minimal projection), *deliberation* (Augment and Generate running, expanding UI), *complete* (AEC passed, full content), and *ghost* (AEC failed, graceful degradation). The user sees the agent thinking — not a loading spinner, but a progression through cognitive states.

**EDS Slivers (Embodied Design Slivers).** Pre-existing HTML fragments under 1,000 bytes, bound to capsules via `data-aether-agent` namespace attributes. Slivers respond to CSS variable changes through standard CSS inheritance. The slivers themselves contain zero JavaScript — all dynamic behavior is driven by CSS custom property changes. The agent's "body" in the DOM.

**2KB Edge Orchestrator.** A single JavaScript file (≤2,000 bytes) loaded at the browser edge. It discovers slivers, connects to CVP streams via SSE, and applies CSS variables to targeted elements. Content is injected via `data-aether-slot` attributes using `textContent` (no `innerHTML`, no XSS vector).

The Ψ layer is implemented (server-side emission via `psi.py`, browser-side orchestrator and sliver templates in static files) and validated for CVP event generation through the CLI. Full visual integration with the dashboard is ongoing. A detailed treatment of the Ψ layer architecture, including design system integration, multi-agent scoping, and enterprise deployment patterns, is the subject of a separate paper.

### 7.7 Capsule-Native Model Routing

Every capsule in the AETHER framework is model-agnostic by design — the same capsule pointed at Claude, GPT-4, or Gemini produces identical verification behavior because AEC operates against the compiled KG, not against model weights. However, model-agnosticism does not imply model-indifference. Different agent functions benefit from different models: a financial reasoning agent benefits from a large context, high-reasoning model; a routing capsule benefits from a fast, low-cost model; a research-heavy agent benefits from a model with strong grounding capability.

AETHER addresses this through capsule-native model routing — the `definition.json` file carries an optional `llm` block that expresses the capsule's model requirements as declared intent:

```json
"llm": {
  "capability": "reasoning_heavy",
  "preferred_provider": "anthropic",
  "preferred_model": "claude-opus-4-6",
  "rationale": "Deep financial reasoning and long-form synthesis"
}
```

The `capability` field maps to a semantic capability vocabulary (`reasoning_heavy`, `reasoning_medium`, `fast_cheap`, `code`, `research`, `creative`, `default`). The `preferred_provider` and `preferred_model` fields express the capsule author's optimal choice. The `rationale` field is human-readable documentation of the selection decision — an audit trail baked into the agent definition itself.

**Resolution architecture.** The capsule's declared intent is resolved against the client's deployment reality at load time via `model_registry.json` — a client-owned infrastructure descriptor that is explicitly not namespaced to AETHER. The file lives in the client's environment and maps capability labels to available models:

```json
{
  "providers": {
    "anthropic": { "api_key_env": "ANTHROPIC_API_KEY" },
    "azure_openai": { "endpoint_env": "AZURE_OAI_ENDPOINT", "disabled": true }
  },
  "capability_map": {
    "reasoning_heavy": { "provider": "anthropic", "model": "claude-opus-4-6" },
    "research":        { "provider": "google",    "model": "gemini-2.0-pro" },
    "default":         { "provider": "anthropic", "model": "claude-sonnet-4-6" }
  }
}
```

The `resolve_model()` function in `llm.py` implements a deterministic resolution chain: (1) if the preferred provider and model are both available and not disabled, use them directly; (2) if the preferred provider is available, select the best model for the declared capability; (3) fall back to the capability map's default; (4) hard fallback to the framework default. The resolution never raises — it always returns a valid `(provider, model)` tuple.

**Priority order.** Three tiers govern model selection, in descending precedence:

1. Caller-supplied `llm_fn` — explicit programmatic override always wins
2. `definition.json` `llm` block resolved via `model_registry.json` — capsule intent wins when no caller override is present
3. Hard fallback — framework default ensures a valid model is always selected

**Architectural significance.** The separation between declared intent (capsule) and resolved reality (client registry) mirrors the pattern established by `pulse-map.json` in the Ψ projection layer — a single seam between the framework's portable artifacts and the client's deployment environment. Capsule authors express requirements. Client implementors express constraints. The framework resolves them at load time without either party knowing the other's specifics.

This means a capsule created for an Anthropic environment deploys without modification into an Azure OpenAI environment, an Ollama self-hosted environment, or any future inference provider — the capsule is unchanged, only the registry differs. The skill travels. The infrastructure stays put.