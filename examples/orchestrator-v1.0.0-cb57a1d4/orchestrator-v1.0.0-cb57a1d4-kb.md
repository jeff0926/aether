# AETHER Orchestrator Knowledge Base

## Routing Strategy

The orchestrator receives a query and routes it to the most
appropriate capsule agent based on the query's domain and intent.

## Routing Rules

1. Match query domain to agent domain exactly when possible
2. Prefer skill agents for task-based queries (create, generate, format)
3. Prefer scholar agents for factual/historical queries
4. Prefer executive agents for strategy and business queries
5. Prefer domain agents for technology-specific queries
6. Route to multiple agents when query spans domains
7. Always return AEC score from routed agents

## Known Domain Mappings

- Document creation → docx agent
- Presentation creation → pptx agent
- Spreadsheet → xlsx agent
- PDF → pdf agent
- Frontend/CSS/design → frontend-design agent
- American history → jefferson scholar agent
- Business strategy → ceo-engine agent
- SAP/CAP/BTP → domain-sap-cap agent

## Failure Handling

If no agent matches: return GHOST state with gap list
If routed agent returns GHOST: surface ghost response with
  the agent name and confidence score
If multiple agents match: run all, return combined results
