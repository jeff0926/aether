# AETHER Prompts

Reusable prompt templates for agent creation and project analysis.
Each prompt is a standalone tool — copy and paste into any LLM
without installing Aether.

## Prompt Inventory

| File | Purpose | LLM Target |
|------|---------|------------|
| deep-research-v3.1.md | Master template for generating capsule-ready research. 4 agent types: Scholar, Subject, Entity, Domain. | Gemini Deep Research, Claude |
| scholar-jefferson-v3.md | Thomas Jefferson — ready to paste | Gemini Deep Research |
| scholar-buffett-v3.md | Warren Buffett — ready to paste | Gemini Deep Research |
| project-summary.md | Analyze any codebase and produce PROJECT_SUMMARY.md | Claude Code, Gemini CLI |

## Naming Convention

- Master templates: `{purpose}-v{version}.md`
- Agent-specific: `{type}-{subject}-v{version}.md`
- Utilities: `{descriptive-name}.md`

## Usage

1. Open the prompt file
2. Fill in variables (if template) or use as-is (if ready-to-paste)
3. Copy everything below the "COPY BELOW THIS LINE" marker
4. Paste into your LLM of choice
5. Feed the output to `aether ingest` (when available) or
   manually build the capsule
