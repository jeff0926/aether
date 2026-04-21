# Agent Construction Patterns

Knowledge base for the Domain Expert: Agent Builder capsule.
Primary knowledge is encoded in `domain-agent-builder-kb.dsl` as structured rules.

## Overview

This capsule encodes 12 progressive agent-building patterns from the
"Learn Claude Code" tutorial (Anthropic 2026). Rules are dependency-ordered:
each rule declares prerequisites that must be understood before proceeding.

## Session 1: Agent Loop (s01)

One tool + one loop = an agent. The fundamental cycle:
User sends messages to LLM, LLM responds. If stop_reason is tool_use,
execute the tool and loop back. Otherwise return the text response.
This is the foundation — every other pattern builds on this loop.

## Session 2: Tool Dispatch (s02)

Adding a tool means adding one handler. The loop stays the same.
New tools register into a dispatch map: tools = {name: handler_fn}.
Dispatch routes tool_name to the matching handler function.
Requires: s01.

## Session 3: Planning (s03)

An agent without a plan drifts. List the steps first, then execute.
Use LLM to generate a plan from the goal, then execute each step
in order. Completion rate doubles with explicit planning.
Requires: s01.

## Session 4: Task Decomposition (s04)

Break big tasks down. Each subtask gets a clean context.
Subagents use independent message arrays, keeping the main
conversation clean. Decompose the task, run each subtask
in a fresh context.
Requires: s01, s03.

## Session 5: Knowledge Injection (s05)

Load knowledge when you need it, not upfront. Inject context
via tool_result, not the system prompt. On a read_file tool call,
read the content and inject it as a tool result.
Requires: s01, s02.

## Session 6: Context Management (s06)

Context will fill up; you need a way to make room. Three-layer
compression strategy for infinite sessions:
Layer 1: summarize old messages.
Layer 2: compress to key facts.
Layer 3: archive to disk.
Requires: s01, s05.

## Session 7: Task Graph (s07)

Break big goals into small tasks, order them, persist to disk.
File-based task graph with dependencies: {id, description, depends_on[], status}.
Persist to tasks.json. Execute in dependency order.
Requires: s03, s04.

## Session 8: Background Execution (s08)

Run slow operations in the background; the agent keeps thinking.
Daemon threads run commands. On completion, inject a notification.
The agent continues processing without blocking.
Requires: s01, s02.

## Session 9: Multi-Agent Delegation (s09)

When the task is too big for one, delegate to teammates.
Persistent teammates with async mailboxes. Create agents for each role,
assign unassigned tasks to the best-fit teammate via mailbox.
Requires: s04, s07.

## Session 10: Communication Protocol (s10)

Teammates need shared communication rules. One request-response
pattern drives all negotiation: {request: task, response: result, status: enum}.
All communication conforms to this protocol.
Requires: s09.

## Session 11: Autonomous Claiming (s11)

Teammates scan the board and claim tasks themselves. No need for
the lead to assign each one. Each teammate filters for open tasks
matching their skills and claims the first match.
Requires: s09, s10.

## Session 12: Workspace Isolation (s12)

Each agent works in its own directory, no interference. Tasks manage
goals, worktrees manage directories, bound by task ID. Create a
worktree for each task, execute within it, merge on completion.
Requires: s11.
