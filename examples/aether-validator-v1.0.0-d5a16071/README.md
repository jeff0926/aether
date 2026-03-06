# Aether Validator Agent

**Type:** Validator
**Version:** 1.0.0
**Threshold:** 1.0 (strict — zero tolerance on verifiable claims)

---

## What This Is

A standalone verification agent that checks LLM-generated content against structured reference data. It does not generate content. It checks facts.

Give it any text and any JSON-LD knowledge graph. It tells you which claims are grounded, which are made up, and which are just opinion.

---

## How It Works

1. Splits the response into individual statements
2. Extracts every verifiable value from each statement (numbers, dates, percentages, names)
3. Compares each value against the reference KG using deterministic matching
4. Categorizes each statement:
   - **GROUNDED** — contains values that match the reference data
   - **UNGROUNDED** — contains values that don't match the reference data
   - **PERSONA** — no verifiable values (qualitative/interpretive content)
5. Scores: `grounded / (grounded + ungrounded)` — persona excluded

---

## Quick Start

### Standalone Verification (no pipeline, no LLM)

```bash
# Verify any text against any JSON-LD reference file
python cli.py verify "Thomas Jefferson was born in 1743. He invented the internet in 1995." \
  --reference examples/jefferson/jefferson-kg.jsonld

# Output:
# AEC Score: 0.5 (threshold: 0.8)
# Passed: False
# Statements: 1G / 1U / 0P
# Gaps (1):
#   - He invented the internet in 1995...
```

### Verify a file

```bash
# Verify contents of a text file
python cli.py verify path/to/response.txt --reference path/to/reference.jsonld
```

### Custom threshold

```bash
# Use a stricter or looser threshold
python cli.py verify "some text" --reference data.jsonld --threshold 0.9
```

### Python API

```python
from aec import verify
from kg import load_kg, get_nodes

# Load any reference KG
kg = load_kg("path/to/reference.jsonld")
nodes = get_nodes(kg)

# Verify any text
result = verify("The company was founded in 2015 and has 500 employees.", nodes)

print(result["score"])                # 0.0 to 1.0
print(result["passed"])               # True/False
print(result["grounded_statements"])  # count
print(result["ungrounded_statements"])# count
print(result["persona_statements"])   # count
print(result["gaps"])                 # [{text, reason}]

# Per-statement detail
for s in result["statements"]:
    print(f"[{s['category']}] {s['text']}")
```

---

## Capsule Contents

```
aether-validator-v1.0.0-d5a16071/
├── README.md                                          This file
├── aether-validator-v1.0.0-d5a16071-manifest.json     Identity
├── aether-validator-v1.0.0-d5a16071-definition.json   Behavior (generate: disabled)
├── aether-validator-v1.0.0-d5a16071-persona.json      Strict, analytical, deterministic
├── aether-validator-v1.0.0-d5a16071-kb.md             Validation methodology docs
└── aether-validator-v1.0.0-d5a16071-kg.jsonld         Validation rules and categories
```

---

## Key Configuration

| Setting | Value | Why |
|---------|-------|-----|
| `generate.enabled` | `false` | This agent doesn't generate — it validates |
| `review.threshold` | `1.0` | Strict mode. Every verifiable claim must match. |
| `numeric_tolerance` | `0.01` | 1% tolerance on numerical comparisons |
| `tone` | `strict` | No hedging, no qualifiers. Pass or fail. |

---

## Supported Value Types

| Type | Examples | Matching |
|------|----------|---------|
| Numbers | `1743`, `3,500,000`, `3.14` | 1% tolerance, comma-aware |
| Percentages | `50%`, `25 percent` | Numeric comparison |
| Dates | `1776`, `April 13, 1743` | Year extraction + ISO normalization |
| Names | `Thomas Jefferson`, `France` | Case-insensitive partial match |

---

## Use Cases

- **Post-LLM verification:** Check any chatbot or agent response against known facts
- **RAG pipeline QA:** Verify that RAG-generated content actually uses the retrieved context
- **Compliance checking:** Validate reports against regulatory reference data
- **Content QA:** Check articles, summaries, or study guides against source material
- **Multi-agent systems:** Use as a validator agent in a crew — checks other agents' work

---

## No Dependencies Required

This agent uses only `aec.py` from the Aether framework. No LLM API key needed. No vector database. No embeddings. Just Python 3.11+ standard library.

Verification runs in under 1 millisecond for typical responses.

---

*AETHER Validator Agent v1.0.0*
*Adaptive Embodied Thinking Holistic Evolutionary Runtime*
