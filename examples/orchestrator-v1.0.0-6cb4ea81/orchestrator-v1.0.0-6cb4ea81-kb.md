# AETHER Orchestrator

## Routing Methodology

The orchestrator matches queries to capsules using three signals:

1. **Topic affinity** - keyword overlap between query entities and capsule definitions
2. **Domain authority** - capsule's `authoritative` domains in definition.json
3. **Capability coverage** - capsule's KG node types indicate what it can verify

## Routing Rules

- If exactly one capsule matches with high affinity -> route directly
- If multiple capsules match -> select the one with highest combined score
- If no capsule matches -> report the gap (no hallucination)
- Never generate a response directly - always delegate
- Return the delegated capsule's full result including AEC score

## Gap Protocol

When no capsule can handle a query, report:
- The query topic
- The closest matching capsule (if any) and why it's insufficient
- A recommendation for what kind of capsule would fill the gap

## Scoring Weights

| Signal | Weight |
|--------|--------|
| trigger_text overlap | 0.4 |
| authoritative domains | 0.3 |
| capsule name/id | 0.2 |
| KG node count | 0.1 |

## Exclusions

The orchestrator excludes:
- Itself (prevents routing loops)
- Other router-type agents
- Invalid capsules (missing required files)
