# Project Summary Prompt

Analyze any codebase and produce a structured PROJECT_SUMMARY.md.

## Usage

Run this prompt in Claude Code or Gemini CLI pointed at any repo.

## Prompt

Analyze this entire project and produce a structured summary
document saved as PROJECT_SUMMARY.md with:

1. Directory tree with descriptions (2 levels deep)
2. Core components (purpose, inputs, outputs, connections)
3. Architecture pattern and data flow
4. Key abstractions and design patterns
5. Configuration and manifest files
6. External dependencies with versions
7. Current state (working / in-progress / planned)
8. Known issues or gaps
9. How to run (prerequisites, setup, commands)
10. File inventory (path, line count, purpose)

Format as clean markdown with tables. Be comprehensive but concise.
Focus on what a new developer needs to understand the codebase
in 10 minutes.
