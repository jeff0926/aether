---
section: 8
title: Experiments
paper: AETHER — Self-Educating Agent Skills through Compiled Knowledge Graph Verification
status: draft
last_updated: 2026-03-20
---

# 8. Experiments

This section presents experimental results across three evaluation dimensions: factual grounding discrimination, skill verification effectiveness, and self-education improvement. All experiments use the published codebase and can be reproduced using the commands provided.

### 8.1 Experimental Setup

**Hardware:** Standard consumer laptop, Apple M-series equivalent, single-threaded Python. No GPU. No vector database. No external services beyond the LLM API.

**LLM Provider:** Anthropic Claude Sonnet for all generation and Layer 2 verification calls. Temperature: default (model-controlled). No custom sampling parameters.

**Capsules Under Test:**
- Thomas Jefferson Scholar Agent: 51 core KG nodes, 28,810 bytes KB, 43 graph nodes with 37 triples across 13 entity types.
- Frontend-design Skill Agent: 73 core KG nodes (22 Rules, 22 Techniques, 14 Concepts, 6 AntiPatterns, 5 Traits, 4 Tools), 3,956 bytes KB, 180 triples.
- 8 Executive Advisor capsules: 45-55 KG nodes each, created via DAG from Gemini-generated research.

**Evaluation Protocol:** Each experiment reports AEC score, per-statement breakdown (grounded/ungrounded/persona), verification method per statement, and timing. LLM responses vary between runs; reported scores represent single runs with the specific response text available in the repository for verification.

### 8.2 Experiment 1: Factual Grounding Discrimination

**Hypothesis:** AEC correctly discriminates between fully grounded, partially grounded, and severely ungrounded responses on factual content.

**Design:** Three queries selected to exercise the full spectrum of knowledge coverage against the Jefferson capsule:

| Query | KG Coverage | Rationale |
|-------|------------|-----------|
| "When was Thomas Jefferson born?" | Full (birth date, location, name all in KG) | All verifiable claims should ground |
| "Jefferson vs Hamilton disagreements?" | Partial (Hamilton absent from KG) | Jefferson claims ground; Hamilton claims don't |
| "Louisiana Purchase details and cost?" | Minimal (1 node, 2 facts) | Most claims will be LLM-generated |

**Results:**

| Query | AEC Score | G | U | P | Input Tokens | Result |
|-------|-----------|---|---|---|-------------|--------|
| Birth | 1.000 | 4 | 0 | 0 | 847 | PASS |
| Hamilton | 0.600 | 3 | 2 | 0 | 189 | FAIL |
| Louisiana | 0.143 | 1 | 8 | 1 | 46 | FAIL |

**Analysis:** The scores correlate directly with input token count — a proxy for how much grounding context the Augment stage found. Full coverage (847 tokens) produces a perfect score. Partial coverage (189 tokens) produces a proportional score — exactly 3 of 5 verifiable claims are grounded, reflecting the fact that Jefferson-related content exists in the KG but Hamilton-related content does not. Minimal coverage (46 tokens) produces a near-zero score — only the "$15 million" cost claim matched the single Louisiana Purchase node.

**Significance:** AEC does not produce binary pass/fail. It produces proportional scores that reflect the precise knowledge coverage of the capsule. The gap list from the 0.143 failure (8 specific ungrounded claims about Napoleon, Livingston, Monroe, territory size, and payment structure) becomes the education curriculum validated in Experiment 3.

```bash
# Reproduce:
python cli.py run examples/jefferson "When was Jefferson born?" --provider anthropic --report full
```

### 8.3 Experiment 2: Skill Verification Effectiveness

**Hypothesis:** AEC concept layers produce meaningful verification scores on skill agents where factual AEC alone produces trivial scores.

**Design:** The frontend-design capsule (73 KG nodes) queried with "How should I approach typography for a luxury brand?" — a query that exercises Rules, Techniques, and AntiPatterns simultaneously.

**Condition A — Factual AEC only (concept layers disabled):**

| Metric | Value |
|--------|-------|
| AEC Score | 1.000 |
| Grounded | 0 |
| Ungrounded | 0 |
| Persona | 2 |
| Verdict | Trivially perfect — nothing verified |

All statements classified as Persona. No numbers, dates, or names to extract. AEC's factual gate has no purchase on skill content. The score is meaningless.

**Condition B — Full AEC with concept layers:**

| Metric | Value |
|--------|-------|
| AEC Score | 0.857 |
| Grounded | 6 |
| Ungrounded | 1 |
| Persona | 1 |
| Verdict | Meaningful — rules checked, violation caught |

Six statements grounded via compiled pattern matching (Layer 1) and type-driven verification (Layer 2) against Rules and Techniques. One statement flagged as ungrounded: anti-pattern violation (the word "Inter" detected in the compiled blacklist). One statement classified as Persona (genuine opinion with no KG match).

**Condition C — Without anti-gaming fix:**

| Metric | Value |
|--------|-------|
| AEC Score | 1.000 |
| Grounded | 4 |
| Ungrounded | 0 |
| Persona | 0 |
| Prompt size | 1,590 chars |
| Node IDs in response | 6+ |
| Verdict | Inflated — agent self-cited to game verification |

The LLM embedded KG node identifiers directly in the response (`"per rule:avoid_generic_fonts"`, `"antipattern:generic_ai_aesthetics"`). Layer 1 matched trivially. The score was perfect but the verification was meaningless — the agent was citing its own test answers.

**Condition D — With anti-gaming fix:**

| Metric | Value |
|--------|-------|
| AEC Score | 0.857 |
| Prompt size | 1,039 chars (-35%) |
| Node IDs in response | 0 |
| Response quality | Expert design advice, not specification document |
| Verdict | Earned — genuine concept matching |

**Compilation Performance:**

| Metric | Value |
|--------|-------|
| Nodes compiled | 73 |
| Detectors produced | 73 |
| Blacklist tokens | 5 |
| Edge policies | 12 |
| Compilation time | 0.62ms |

```bash
# Reproduce Condition B:
python cli.py run examples/frontend-design-v1.0.0-ff6ab491 \
  "How should I approach typography for a luxury brand?" \
  --provider anthropic --report full
```

### 8.4 Experiment 3: Self-Education Improvement

**Hypothesis:** The education loop autonomously improves agent knowledge when AEC detects gaps, without human intervention during the cycle.

**Design:** The Jefferson capsule's Louisiana Purchase failure from Experiment 1 (score 0.143, 8 ungrounded statements) is used as the education input.

**Education Process:**

| Stage | Metric | Value |
|-------|--------|-------|
| Queue | Gaps queued | 8 specific ungrounded claims |
| Research | Triples proposed | 22 |
| Validate | Triples passing AEC (threshold 0.5) | 19 |
| Contradict | Triples rejected (core conflict) | 0 |
| Contradict | Triples rejected (duplicate) | 2 |
| Integrate | Triples added to KG | 17 |
| KG growth | Nodes before | 51 |
| KG growth | Nodes after | 68 |

**Re-evaluation:**

| Metric | Before Education | After Education | Delta |
|--------|-----------------|-----------------|-------|
| AEC Score | 0.143 | 0.889 | +0.746 |
| Grounded | 1 | 8 | +7 |
| Ungrounded | 8 | 1 | -7 |
| Persona | 1 | 1 | 0 |

The single remaining ungrounded statement concerned constitutional precedent implications — a synthesis claim that the education research did not cover with sufficient specificity. The persona statement remained unchanged (interpretive commentary).

**Acquired Knowledge Sample:**

| Subject | Predicate | Object | Origin |
|---------|-----------|--------|--------|
| Louisiana Purchase | negotiated_by | Robert Livingston, James Monroe | acquired |
| Louisiana Purchase | seller | Napoleon Bonaparte / France | acquired |
| Louisiana Purchase | territory_size | approximately 828,000 square miles | acquired |
| Louisiana Purchase | payment_structure | $11.25M direct + $3.75M assumed debts | acquired |

**Integrity Verification:** No acquired triple contradicted any core node. The contradiction gate processed all 22 proposed triples; 0 were rejected for core conflict. 2 were rejected as duplicates of existing core knowledge (year: 1803 and cost: $15M already existed). 3 failed AEC validation at the 0.5 threshold (imprecise formulations).

**Human intervention during the cycle: Zero.** The gap list from AEC failure was the only input. The education loop conducted all research, validation, contradiction checking, integration, and re-evaluation autonomously.

```bash
# Reproduce (requires initial failure + education run):
python cli.py run examples/jefferson "Louisiana Purchase details and cost?" --provider anthropic
python cli.py educate examples/jefferson --item 0 --provider anthropic
```

### 8.5 Experiment 4: Orchestrator Routing

**Hypothesis:** The orchestrator correctly routes queries across three agent categories without human-specified agent selection.

**Design:** Four queries spanning different domains, routed via the orchestrator capsule against 21 production capsules.

| Query | Expected Target | Actual Target | Score | Correct? |
|-------|----------------|---------------|-------|----------|
| "When was Jefferson born?" | jefferson | jefferson | 0.21 | ✓ |
| "What is our strategic vision?" | CEO | CEO | 0.30 | ✓ |
| "How should I approach typography?" | frontend-design | frontend-design | 0.23 | ✓ |
| "Configure a Kubernetes cluster" | GAP | GAP (<0.15) | — | ✓ |

All four routing decisions correct. The Kubernetes gap detection demonstrates that the system does not force a bad match — it reports the absence of capability.

```bash
# Reproduce:
python cli.py orchestrate "When was Jefferson born?" --registry ./examples --dry-run
```

### 8.6 Framework Performance Summary

| Component | Metric | Value |
|-----------|--------|-------|
| compile_kg() — 73 nodes | Compilation time | 0.62ms |
| Layer 1 — per statement | Verification time | 0.1-0.3ms |
| Layer 1 — blacklist check | Violation detection | <0.05ms |
| Layer 2 — per LLM call | External latency | 2-8 seconds (external LLM API; AETHER overhead is prompt construction only) |
| Layer 3 — per statement | Edge traversal | <0.5ms |
| Full DAGR pipeline (excl. LLM) | Framework overhead | <3ms |
| Orchestrator routing | Query → dispatch | <60ms |
| Education cycle (1 round) | Full loop | 30-90 seconds |
| Total codebase | Python lines | ~4,700 |
| Dependencies | External | anthropic SDK (optional) |
