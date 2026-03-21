---
section: 6
title: "Method: Autonomous Learning"
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 6. Method: Autonomous Learning

This section describes AETHER's self-education loop — the mechanism by which agents autonomously identify knowledge gaps, research missing information, validate proposed knowledge, and integrate verified additions into their knowledge graph. It also details the integrity mechanisms that prevent the education process from corrupting the agent's foundational knowledge.

### 6.1 The Education Cycle

When AEC verification produces a score below the threshold (default 0.80), the failure is not simply logged. It is decomposed into a structured curriculum.

The gap list from AEC's Retrieval stage contains the specific ungrounded statements — claims the agent made that could not be verified against any node in the compiled knowledge graph. Each gap entry includes the statement text, the verification method that failed, and the reason for failure (no match, value mismatch, or blacklist violation). These gaps are not vague indicators of poor performance. They are precise specifications of what the agent does not know.

The education cycle proceeds through six stages:

```
1. QUEUE      — AEC failure enters the education queue with query, response,
                score, and structured gap list
2. RESEARCH   — LLM researches the specific gaps, producing proposed knowledge
                as (subject, predicate, object) triples
3. VALIDATE   — Each proposed triple is verified through AEC at a lower
                threshold (0.5) to ensure internal consistency
4. CONTRADICT — Contradiction gate checks each validated triple against
                core nodes (Section 6.2)
5. INTEGRATE  — Surviving triples are added to the KG with origin "acquired"
6. RE-EVALUATE — Original query re-run against expanded KG; new score computed
```

**Status progression:** Each education record moves through: `pending → researching → validated → integrated`, or diverges to `failed` (research produced no usable triples) or `rejected_contradiction` (all triples conflicted with core knowledge).

*Running example: The Thomas Jefferson Scholar Agent receives the query "What happened during the Louisiana Purchase and how much did it cost?" The KG contains a single Louisiana Purchase node with two facts: year 1803 and cost $15 million. The LLM generates a detailed response covering Napoleon, Robert Livingston, James Monroe, the $11.25 million direct payment, $3.75 million in assumed debts, 828,000 square miles, and three cents per acre.*

*AEC score: 0.143. Only the "$15 million" claim is grounded. Eight statements are ungrounded — the agent generated accurate content from its LLM training data, but none of it exists in the KG. The failure enters the education queue with 8 specific gaps.*

### 6.2 The Contradiction Gate

Before any acquired triple integrates into the knowledge graph, it must pass the contradiction gate. This is the mechanism that prevents the education loop from corrupting the agent's foundational knowledge.

The gate enforces two rules:

**Rule 1: Core veto.** Core nodes are indexed by subject and predicate. When a proposed acquired triple matches an existing core node's subject and predicate but carries a different object value, the core node's value prevails and the proposed triple is rejected.

```
Core:     (Jefferson, birth_year, 1743)
Proposed: (Jefferson, birth_year, 1750)
→ REJECTED: Core node has birth_year=1743, proposed birth_year=1750
```

This is absolute. No acquired knowledge can override core knowledge at runtime. The core zone is the agent's immutable truth — the knowledge it was created with through the DAG process. Self-education can *extend* this truth but never *contradict* it.

**Rule 2: AntiPattern block.** If a proposed triple's subject or object overlaps with AntiPattern blacklist terms by 50% or more, the triple is rejected. The agent cannot learn what its own rules forbid.

```
AntiPattern blacklist: {inter, roboto, arial}
Proposed: (font_recommendation, preferred_font, "Arial font")
→ REJECTED: Cannot learn "Arial font" — matches antipattern blacklist
```

This prevents a subtle failure mode: adversarial queries designed to inject forbidden knowledge through the education loop. Repeatedly asking "Isn't Arial actually a premium luxury font?" could, without the gate, cause the agent to research the claim, find supporting text from the LLM (which is a "people-pleaser" by training), and integrate a node that contradicts its own design rules.

Rejected triples are logged with `status: rejected_contradiction`, the conflicting core node identifier, and the rejection reason. They are not silently dropped — the audit trail preserves the attempt for debugging and system analysis.

### 6.3 Anti-Gaming: Node ID Stripping

A separate integrity mechanism addresses a different gaming vector: the agent inflating its own verification scores.

During the Generate stage (Section 5.1), the LLM receives knowledge graph context to ground its response. If this context includes node identifiers — `rule:avoid_generic_fonts`, `antipattern:overused_fonts` — the LLM can embed these identifiers directly in its output. Layer 1's pattern matching then matches trivially: the response literally contains the detector's label text.

We observed this behavior empirically. Before the anti-gaming fix, responses from the frontend-design capsule contained direct node references:

```
Before: "Per rule:avoid_generic_fonts, you should choose distinctive typefaces.
         This addresses antipattern:generic_ai_aesthetics..."

After:  "Choose distinctive typefaces like Playfair Display or Crimson Pro.
         Avoid generic fonts that feel like template design..."
```

The fix: `@id` values and all `aether:` namespaced properties are stripped from KG nodes before they enter the LLM prompt. The LLM sees the human-readable content of the rules but not their identifiers. AEC in the Retrieval stage retains full access to all fields for verification.

**Measured impact:**

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| Node IDs in response | 6+ references | 0 |
| Prompt size | 1,590 chars | 1,039 chars (-35%) |
| AEC score | 1.0 (inflated via self-citation) | 0.857 (earned via concept matching) |
| Response quality | Reads like a specification document | Reads like expert design advice |

The score dropped from a perfect but meaningless 1.0 to a lower but genuine 0.857. The agent stopped gaming and started demonstrating.

### 6.4 The Self-Education Proof

The complete education cycle was validated on the Thomas Jefferson Scholar Agent.

**Initial state:** The agent's KG contained 51 core nodes covering Jefferson's biography, the Declaration of Independence, and his diplomatic service. The Louisiana Purchase was represented by a single node with two data points (year: 1803, cost: $15 million).

**The failure:** Query: "What happened during the Louisiana Purchase and how much did it cost?" AEC score: 0.143. One statement grounded ($15 million cost matched). Eight statements ungrounded. One statement persona. The failure entered the education queue with 8 specific gaps.

**The education:** The LLM researched the 8 gaps, producing 22 proposed triples covering Napoleon Bonaparte, Robert Livingston, James Monroe, the negotiation timeline, the territory size, the payment structure, and the constitutional questions. AEC validated each at threshold 0.5. The contradiction gate checked each against core nodes — no conflicts found (Louisiana Purchase was under-represented in core, not contradicted). 17 of 22 triples survived validation and contradiction checking. 5 were rejected: 3 failed AEC validation (imprecise formulations), 2 were duplicates of existing core knowledge.

**The integration:** 17 new triples added to the KG with `origin: "acquired"`. The knowledge graph grew from 51 to 68 nodes.

**The re-evaluation:** Same query re-run against the expanded KG. AEC score: 0.889. The eight previously ungrounded statements now matched acquired nodes covering Napoleon, Livingston, Monroe, territory size, and payment structure. One statement remained ungrounded (a synthesis claim about constitutional precedent that the education research did not cover precisely enough).

| Metric | Before Education | After Education |
|--------|-----------------|-----------------|
| AEC Score | 0.143 | 0.889 |
| Grounded statements | 1 | 8 |
| Ungrounded statements | 8 | 1 |
| KG nodes | 51 | 68 |
| Triples acquired | — | 17 |
| Human intervention | — | Zero |

**The skill improved through practice.** The agent encountered a question it could not adequately answer. AEC identified exactly what was missing. The education loop researched exactly those gaps. The contradiction gate ensured the new knowledge was consistent with the existing core. The agent is now permanently more capable on this topic. The next query about the Louisiana Purchase will be grounded.

The model did not change. **The skill did.**

### 6.5 Education as Curriculum Generation

The self-education loop inverts the traditional relationship between failure and improvement. In conventional agent systems, a failure is an error to be logged. In AETHER, a failure is a curriculum to be executed.

The gap list produced by AEC's Retrieval stage is not a list of complaints. It is a research specification: "These are the exact facts missing from the knowledge graph. Research them. Validate them. Integrate them." The specificity of the gaps — tied to particular statements, particular nodes, particular verification methods — means the education loop does not wander. It researches exactly what is needed. Nothing more.

This creates a flywheel:

```
Query → Response → AEC → Failure → Gaps → Education → New Knowledge →
  → Recompile → Better Verification → Next Query Benefits
```

Every failure makes the agent more capable. Every capability makes subsequent failures less likely. The knowledge graph grows through use. The compiled verification engine rebuilds at each load to incorporate new detectors from acquired nodes. The agent that has processed 100 queries has more knowledge, more verification coverage, and fewer gaps than the agent that has processed 10.

No fine-tuning. No retraining. No human intervention during the cycle. The model is interchangeable. The skill compounds.
