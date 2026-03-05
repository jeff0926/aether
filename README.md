# AETHER

**Adaptive Embodied Thinking Holistic Evolutionary Runtime**

A minimal agent framework in 1,147 lines of Python. No frameworks. Standard library only. The `anthropic` SDK is the only optional external dependency.

## What It Does

AETHER creates, runs, and improves **capsules** — self-contained agent definitions stored as folders with 5 files. Each capsule carries its own identity, knowledge, and behavioral configuration.

The framework runs a 4-stage pipeline on every query:

```
Input → Distill → Augment → Generate → Review → Output
```

1. **Distill**: Extract intent, entities, and constraints from input
2. **Augment**: Retrieve relevant context from KB (markdown) and KG (JSON-LD)
3. **Generate**: Build prompt with persona + context, call LLM
4. **Review**: Verify response against knowledge graph using deterministic gates

## Installation

```bash
git clone https://github.com/jeff0926/aether.git
cd aether

# Optional: Install anthropic SDK for LLM calls
pip install anthropic

# Set API key (optional - can use stub provider for testing)
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

**Requirements**: Python 3.11+ (uses `str | Path` union syntax)

## Quick Start

```bash
# Validate the example capsule
python cli.py validate examples/test-agent

# Get capsule info
python cli.py info examples/test-agent

# Run a query (uses stub LLM by default)
python cli.py run examples/test-agent "What is Aether?"

# Run with real LLM
python cli.py run examples/test-agent "What is Aether?" --provider anthropic

# Create a new empty capsule
python cli.py stamp "My Agent" --output ./capsules

# Create capsule from existing markdown knowledge base
python cli.py stamp "My Agent" --source knowledge.md --output ./capsules
```

## Capsule Structure

A capsule is a folder containing exactly 5 files. **Folder and file names follow the pattern:**

```
{slug}-v{version}-{uid8}/
```

Where:
- `slug`: Lowercase name with hyphens (e.g., "jefferson", "my-agent")
- `version`: Semver string (e.g., "1.0.0")
- `uid8`: First 8 chars of SHA256 hash for uniqueness

Example:
```
jefferson-v1.0.0-a3f7c2d1/
├── jefferson-v1.0.0-a3f7c2d1-manifest.json      # Identity
├── jefferson-v1.0.0-a3f7c2d1-definition.json    # Behavior
├── jefferson-v1.0.0-a3f7c2d1-persona.json       # Personality
├── jefferson-v1.0.0-a3f7c2d1-kb.md              # Knowledge Base
└── jefferson-v1.0.0-a3f7c2d1-kg.jsonld          # Knowledge Graph
```

### {id}-manifest.json
```json
{
  "id": "jefferson-v1.0.0-a3f7c2d1",
  "name": "Thomas Jefferson",
  "version": "1.0.0",
  "created": "2024-01-15T10:30:00"
}
```

### {name}-definition.json
```json
{
  "pipeline": {
    "distill": {"enabled": true},
    "augment": {"enabled": true},
    "generate": {"enabled": true},
    "review": {"enabled": true}
  },
  "review": {
    "threshold": 0.8,
    "min_length": 10,
    "max_length": 10000
  }
}
```

### {name}-persona.json
```json
{
  "tone": "professional",
  "style": "concise",
  "constraints": ["factual", "no-speculation"]
}
```

### {name}-kb.md
Markdown document containing the agent's knowledge. Paragraphs are searched during augmentation and matched to query entities.

### {name}-kg.jsonld
JSON-LD knowledge graph. Nodes are matched during augmentation and used for AEC verification.

```json
{
  "@context": {
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
  },
  "@graph": [
    {
      "@id": "entity:example",
      "rdfs:label": "Example Entity",
      "property": "value"
    }
  ]
}
```

## Architecture

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `aether.py` | 263 | Capsule class, pipeline runner |
| `aec.py` | 244 | Entailment checking, verification gate |
| `kg.py` | 145 | JSON-LD loader, core/acquired zones |
| `stamper.py` | 130 | Capsule folder factory |
| `habitat.py` | 134 | Capsule registry, message routing |
| `llm.py` | 103 | LLM wrapper, .env loading |
| `cli.py` | 128 | Command-line interface |

### AEC (Aether Entailment Check)

The verification gate that checks if generated responses are grounded in the knowledge graph.

**Statement Categories:**
- **Grounded**: Contains verifiable values (numbers, dates, names) that match KG
- **Ungrounded**: Contains verifiable values that don't match KG
- **Persona**: No verifiable values (qualitative statements)

**Scoring:**
```
score = grounded / (grounded + ungrounded)
```

Persona statements are excluded from the ratio — they represent the expected interpretive contribution from the agent's personality.

**Extracted Values:**
- Numbers: `1743`, `3,000`, `99.5`
- Percentages: `50%`, `25 percent`
- Dates: `1776`, `April 13, 1743`
- Names: Capitalized words (excluding pronouns)

### Habitat

In-memory registry for capsules with topic-based routing.

```python
from habitat import Habitat

h = Habitat()
h.register("analyst-001", {
    "name": "Market Analyst",
    "scent_subscriptions": ["market.*", "finance.stocks"]
})

# Find capsules for a topic
recipients = h.route("market.analysis")  # ['analyst-001']

# Check if any capsule handles a topic
gap = h.detect_gaps("sports.scores")  # True — no handler
```

Routing supports exact match and wildcard prefix (`market.*` matches `market.analysis`).

### Knowledge Graph Zones

The KG has two zones:

- **Core**: Original source knowledge. No `aether:origin` tag or `aether:origin: "core"`. Never modified by AEC.
- **Acquired**: Learned through self-education. Tagged with `aether:origin: "acquired"` plus provenance metadata (confidence, date, trigger).

```python
from kg import load_kg, add_acquired, get_core_nodes, get_acquired_nodes

kg = load_kg("jefferson/jefferson-kg.jsonld")

# Add learned knowledge
kg = add_acquired(kg, {
    "subject": "New Fact",
    "predicate": "rdfs:comment",
    "object": "Learned from user feedback",
    "confidence": 0.85,
    "aec_trigger": "verification_failure"
})

core = get_core_nodes(kg)      # Original knowledge
acquired = get_acquired_nodes(kg)  # Learned knowledge
```

## CLI Reference

```
aether stamp <name> [--source FILE] [--output DIR] [--version 1.0.0]
    Create a new capsule folder.
    --source: Use .md/.json/.jsonld as starting content
    --output: Target directory (default: ./capsules)

aether run <capsule_path> <query> [--provider PROVIDER] [--model MODEL]
    Run the 4-stage pipeline on a query.
    --provider: anthropic, openai, or stub (default: stub)
    --model: Override default model

aether validate <capsule_path>
    Check capsule has all required files and valid JSON.

aether info <capsule_path>
    Display manifest, KG stats, and file sizes.
```

## Python API

```python
from aether import Capsule
from llm import make_llm_fn

# Load capsule with LLM
llm_fn = make_llm_fn(provider="anthropic")
capsule = Capsule("path/to/capsule", llm_fn=llm_fn)

# Run pipeline
result = capsule.run("What is the capital of France?")

print(result["generated"])           # LLM response
print(result["distilled"]["intent"]) # query, instruction, comparison, creation, general
print(result["augmented"]["kb"])     # Matched KB paragraphs
print(result["augmented"]["kg"])     # Matched KG nodes
print(result["review"]["passed"])    # True/False

# Standalone AEC verification
from aec import verify
aec_result = verify(result["generated"], result["augmented"]["kg"])
print(aec_result["score"])           # 0.0 - 1.0
print(aec_result["grounded_statements"])
print(aec_result["persona_statements"])
```

## Design Principles

1. **Capsule is a folder.** The framework reads folders. That's it.
2. **Standard library first.** Only add a dependency when stdlib can't do the job.
3. **One file per concern.** No file exceeds 300 lines.
4. **No frameworks.** No Pydantic, no async, no CBOR. JSON and plain dicts.
5. **If it's not needed to create, stamp, run, or improve a capsule, it doesn't exist.**

## What's Not Included

- Async/await
- Vector databases
- Embedding models
- Web UI
- Database persistence
- Multi-turn conversation
- Tool use / function calling
- Streaming responses

These are layers that can be added on top. The core framework stays minimal.

## License

MIT
