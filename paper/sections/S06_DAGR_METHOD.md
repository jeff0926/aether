---
section: 5
title: "Method: Runtime Execution and Verification via DAGR"
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 5. Method: Runtime Execution and Verification via DAGR

This section describes how agents operate at runtime through the DAGR (Distillation + Augment + Generation + Retrieval) pipeline. The focus is the Retrieval stage — where AEC (Agent Education Calibration) compiles the knowledge graph into executable verification logic and evaluates every generated response.

### 5.1 The DAGR Pipeline

A query enters the capsule and passes through four stages. Each stage receives a shared context dictionary, adds its results, and passes forward.

**Stage 1: Distill.** Extracts structure from the raw query without an LLM call. Using regex and keyword patterns, Distill identifies: intent (question, instruction, comparison, creation, or general), named entities (capitalized terms), format preference (list, table, JSON, prose), and brevity flag. Processing time: <0.1ms. The output narrows the search space for the Augment stage.

*Running example: Query "How should I approach typography for a luxury brand?" → intent: general, entities: {typography, luxury, brand}, format: prose, brevity: false.*

**Stage 2: Augment.** Retrieves relevant knowledge from the capsule's KB and KG. KB paragraphs are scored by entity overlap against the distilled entities (top-3 returned). KG nodes are matched by property value overlap. The matched content becomes the grounding context for generation.

*Running example: Augment retrieves 3 KB paragraphs discussing typography principles and 5 KG nodes including `concept:typography`, `concept:aesthetic_vision`, `trait:bold_creative`.*

**Anti-gaming note:** KG nodes included in the prompt have their `@id` values and all `aether:` namespaced properties stripped. The LLM receives human-readable labels ("Avoid generic fonts like Arial and Inter") but not node identifiers (`rule:avoid_generic_fonts`). This prevents the LLM from embedding verification labels in its response to inflate AEC scores. AEC in the Retrieval stage retains full access to all fields. This mechanism is detailed in Section 6.

**Stage 3: Generate.** Constructs a prompt from three components: persona instructions (from `persona.json` — tone, style, behavioral constraints), matched KB and KG context (from Augment, with node IDs stripped), and the original query. A single LLM API call produces the response. This is the only stage that makes an external call, the only stage that costs money, and the only stage that introduces non-determinism. All other stages are pure Python stdlib operations.

*Running example: The LLM receives the persona ("bold creative, visionary technical"), the matched typography context, and the query. It generates a response recommending Playfair Display, Crimson Pro, and Space Grotesk with CSS implementation details and a negative letter-spacing technique.*

**Stage 4: Retrieve/Review.** AEC verifies the generated response against the compiled knowledge graph. This is the R in DAGR — the stage that closes the accountability loop. If the response passes the threshold (default 0.80), it is delivered. If it fails, the response is delivered with a below-threshold warning, and the failure enters the education queue (Section 6).

*Running example: AEC evaluates 8 statements. 6 are grounded against KG Rules and Techniques via compiled pattern matching. 1 triggers an anti-pattern violation ("Inter" detected in blacklist). 1 is classified as persona (genuine opinion). Score: 0.857. Threshold: 0.80. PASS.*

### 5.2 AEC Compilation: The Knowledge Graph as Program

The central mechanism of AEC is `compile_kg()` — a function that transforms the knowledge graph from a data structure into an executable verification program. This function runs once when the capsule loads. All subsequent verification uses the compiled output.

**What compilation produces:**

```
compile_kg(KG) → {
    detectors:     [{node_id, label, node_type, patterns: set, threshold, weight}...],
    blacklist:     {token...},
    blacklist_map: {token → {node_id, label}...},
    edge_policies: [{source_id, source_patterns, target_id, target_patterns,
                     target_blacklist, edge_type}...],
    node_lookup:   {node_id → node...}
}
```

**How compilation works:**

For each of the n nodes in the knowledge graph:
1. The `rdfs:label` is tokenized into a set of content words, excluding stopwords. This produces the `patterns` set — the compiled representation of what this node "means" at the token level.
2. The node's `@type` determines the `threshold` and `weight` via the type configuration table (Section 3.4).
3. If the node is an AntiPattern, parenthetical terms from the label are extracted into the global blacklist. "Overused fonts (Inter, Roboto, Arial)" contributes `{inter, roboto, arial}` to the blacklist. Only parenthetical terms are extracted — this prevents common words in AntiPattern descriptions from triggering false violations.
4. If the node has outgoing `skill:avoids`, `skill:requires`, or `skill:contradicts` edges, those edges compile into edge policy structs containing source patterns, target patterns, and target blacklists.

**Compilation complexity:** O(|N| + |E_v|) where N is the number of nodes and E_v is the number of verification-relevant edges. Each node is visited exactly once for tokenization. Each verification edge is visited once for policy compilation. On the 73-node frontend-design knowledge graph, compilation completes in 0.62ms, producing 73 detectors, 5 blacklist tokens, and 12 edge policies.

### 5.3 Layer 1: Compiled Pattern Matching

Layer 1 is entirely deterministic. No LLM call. It resolves the majority of statements.

For each statement in the response:
1. **Tokenize** the statement into content words, excluding the same stopword set used during compilation.
2. **Blacklist check.** Compute `statement_tokens ∩ blacklist`. If non-empty, the statement is immediately classified as **ungrounded** with the matching AntiPattern as evidence. This is the fastest check — O(1) per token via set membership.
3. **Detector scan.** For each compiled detector, compute `coverage = |statement_tokens ∩ detector.patterns| / |detector.patterns|`. If coverage exceeds the detector's type-specific threshold, the statement is **grounded** against that node. The best match (highest coverage) is selected.
4. **Ambiguous range.** If no detector exceeds its threshold but at least one exceeds half the threshold, the statement and its top candidates are tagged for Layer 2 evaluation. Additionally, Sørensen-Dice coefficient (bigram similarity) is computed as a secondary signal for candidates in this range.

*Running example: Statement "Use CSS variables for consistency" → tokens: {css, variables, consistency}. Detector for `rule:use_css_variables` has patterns: {css, variables, consistency, centralized}. Coverage: 3/4 = 0.75. Rule threshold: 0.50. Match. Grounded.*

*Running example: Statement "Use Inter for body text" → tokens: {inter, body, text}. "inter" ∈ blacklist. Immediately classified as ungrounded. AntiPattern violation: `antipattern:overused_fonts`.*

### 5.4 Layer 2: Type-Driven LLM Verification

Layer 2 activates only when Layer 1 is inconclusive — the statement has partial overlap with detectors but doesn't meet the threshold — and an LLM function is available. It makes at most 3 LLM calls per response.

The key mechanism is the **Type Operator Registry**: the node's `@type` determines which verification question to ask.

| Node Type | Verification Question | Classifications |
|-----------|---------------------|-----------------|
| `Rule` | "Does this statement FOLLOW, VIOLATE, or have NO RELATION to this rule?" | FOLLOW → grounded, VIOLATE → ungrounded |
| `AntiPattern` | "Does this statement USE what the pattern forbids, or is it CLEAN?" | VIOLATE → ungrounded, CLEAN → grounded |
| `Technique` | "Does this statement APPLY or REFERENCE this technique?" | APPLY → grounded, REFERENCE → grounded |

Concepts, Tools, and Traits do not receive Layer 2 verification — they are handled by Layer 1's lower thresholds or classified as persona.

Each prompt includes a **generosity guard**: "If the statement is merely good advice but not explicitly supported by this node, classify as UNRELATED." This prevents the LLM from inflating compliance scores through generous interpretation.

The LLM is forced to output structured JSON: `{"classification": "FOLLOW|VIOLATE|UNRELATED", "reasoning": "..."}`. The first grounded or ungrounded classification terminates the search for that statement. Remaining candidates are skipped.

*Running example: Statement "Choose Playfair Display for headlines." Layer 1: no detector exceeds threshold (Playfair Display doesn't appear in any node label). Layer 2 activates. Top candidate: `rule:avoid_generic_fonts` (partial overlap on "choose" and "fonts" context). LLM prompt: "Does 'Choose Playfair Display for headlines' FOLLOW, VIOLATE, or have NO RELATION to the rule 'Avoid generic fonts like Arial and Inter'?" LLM classifies: FOLLOW (Playfair Display is not a generic font). Statement grounded via type-driven compliance check.*

### 5.5 Layer 3: Edge Policy Traversal

Layer 3 addresses compositional violations — statements that match one node but violate a policy encoded in the edges connecting that node to others. It runs after Layer 1 and Layer 2, only for statements that have been matched to a node.

For each matched node, Layer 3 checks all outgoing verification edges:

**avoids:** If statement matched node A, and A avoids node B, and `statement_tokens ∩ B.blacklist ≠ ∅` → **violation**. The statement addresses the right topic but includes something that topic forbids.

**contradicts:** If statement matched both node A and node B, and A contradicts B → **contradiction**. The statement references two mutually exclusive concepts.

**requires:** Informational in v1. If statement matched node A, and A requires node B, the system logs whether B appears in the full response. Not scored — future work will incorporate this as a completeness check.

Edge traversal is limited to one hop — source to immediate target. Multi-hop verification is discussed in Section 10 as future work. All traversal is deterministic. Zero LLM calls. Processing time: <0.5ms per statement.

*Running example: Statement "For typography, I recommend the clean Inter font." Layer 1 matches `concept:typography` (tokens {typography} overlap patterns). Layer 3 fires: `concept:typography → avoids → antipattern:overused_fonts`. Target blacklist contains {inter, roboto, arial}. Statement tokens contain "inter". Violation detected via graph path: "Statement addresses 'Typography' but contains 'inter' which is avoided per 'Overused fonts (Inter, Roboto, Arial)'."*

This is a violation that neither Layer 1 nor Layer 2 would catch independently. Layer 1 matched the topic (typography). Layer 3 followed the edge and found the forbidden token. The graph structure encodes the policy that connects them.

### 5.6 Scoring

After all three layers process every statement, the scoring formula from Definition 5 applies:

```
score = |grounded| / (|grounded| + |ungrounded|)
```

Persona statements — those with no verifiable content in any layer — are excluded from both numerator and denominator. If all statements are persona (no verifiable content detected), the score defaults to 1.0 (all-persona pass).

The default threshold is 0.80. This reflects an 80/20 design principle: at least 80% of the verifiable content must be traceable to the agent's knowledge graph. The remaining 20% allows for legitimate LLM contributions: synthesis, contextual framing, and reasonable inference from provided facts.

When a response scores below the threshold, the system produces:
1. The numerical score
2. A per-statement breakdown with category, method, and matched node for each statement
3. A structured gap list: the specific ungrounded claims and their violation details

The gap list is not just a diagnostic. It is the input specification for the self-education loop (Section 6). Every AEC failure carries the precise blueprint for its own remediation.

### 5.7 Performance

All measurements taken on standard consumer hardware (Apple M-series equivalent, single-threaded Python, no GPU):

| Operation | Time | Notes |
|-----------|------|-------|
| compile_kg() — 73 nodes | 0.62ms | Runs once at capsule load |
| Layer 1 — per statement | 0.1-0.3ms | Set intersection against all detectors |
| Layer 1 — blacklist check | <0.05ms | Single set intersection |
| Layer 2 — per statement | 2-8 seconds | LLM API call (external latency) |
| Layer 3 — per statement | <0.5ms | Edge policy traversal |
| Full verification — 6 statements, no Layer 2 | <2ms | Layers 1+3 only |
| Full verification — 6 statements, with Layer 2 | 8-20 seconds | Dominated by LLM calls |
| Distill stage | <0.1ms | Regex only |
| Augment stage | 0.1-0.5ms | KB scoring + KG matching |
| Total framework overhead (excluding LLM) | <3ms | All four DAGR stages |

The verification architecture is designed so that the deterministic layers (1 and 3) resolve as many statements as possible before the expensive Layer 2 fires. In practice, Layer 2 activates for 0-3 statements per response. The majority of verification is sub-millisecond.
