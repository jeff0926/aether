# AETHER Deferred Topics Tracker

**Last Updated:** 2026-03-26
**Maintainer:** Claude Code Sessions

---

## Overview

This file tracks features, enhancements, and ideas that have been identified but deferred from initial implementation. Each topic includes context, rationale for deferral, and implementation notes for future sessions.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| `DEFERRED` | Identified, not started, waiting for prioritization |
| `PLANNED` | Scheduled for upcoming work |
| `IN_PROGRESS` | Actively being worked on |
| `BLOCKED` | Waiting on dependency or decision |
| `COMPLETE` | Done, can be removed from tracker |

---

## Engram Module (engram.py)

### 1. A2A Receiver Logic
- **Status:** `DEFERRED`
- **Source:** ENGRAM_FEATURE_BRICK_SPEC.md Section 8
- **Description:** Load and process engram manifests from other capsules for cross-agent memory sharing
- **Rationale:** Needs A2A protocol finalization; schema is already A2A-ready with `engram:source_capsule`
- **Dependencies:** A2A v2 protocol spec
- **Implementation Notes:**
  - `warm_context()` could accept optional `source_capsule_path` parameter
  - Merge foreign engram nodes with local KG, mark provenance
  - Handle node ID collisions between capsules
- **Effort Estimate:** Medium
- **Priority:** High (enables agent collaboration)

---

### 2. NLI-Based Conflict Detection
- **Status:** `DEFERRED`
- **Source:** ENGRAM_FEATURE_BRICK_SPEC.md Section 8
- **Description:** Replace lightweight verb pattern matching with proper Natural Language Inference
- **Rationale:** v1 uses simple verb patterns (`sold`, `no longer`, `deleted`, etc.) which has false negatives
- **Current Implementation:** `detect_conflict()` in engram.py lines 200-240
- **Dependencies:** NLI model selection (local vs API)
- **Implementation Notes:**
  - Consider sentence-transformers for local inference
  - Or Claude API call for high-stakes conflicts
  - Cache conflict checks to reduce API costs
  - Threshold tuning needed for precision/recall balance
- **Effort Estimate:** Medium-High
- **Priority:** Medium

---

### 3. Multi-Session Decay Accumulation
- **Status:** `DEFERRED`
- **Source:** ENGRAM_FEATURE_BRICK_SPEC.md Section 8
- **Description:** Track salience decay across sessions, not just within a single session
- **Rationale:** v1 resets salience each session; nodes don't "fade" over multiple sessions
- **Current Implementation:** `score_salience()` uses `turn_count` within session only
- **Dependencies:** None
- **Implementation Notes:**
  - Store `last_session_salience` in engram.jsonld
  - On `warm_context()`, apply cross-session decay based on time delta
  - Add `session_count` or `days_since_access` to decay formula
  - Consider exponential vs linear decay curves
- **Effort Estimate:** Low-Medium
- **Priority:** Medium

---

### 4. Engram Merge (Shared Memory Model)
- **Status:** `DEFERRED`
- **Source:** ENGRAM_FEATURE_BRICK_SPEC.md Section 8
- **Description:** Allow two capsules to share/merge engram manifests for collaborative memory
- **Rationale:** Future shared memory model for agent teams
- **Dependencies:** A2A protocol, conflict resolution strategy
- **Implementation Notes:**
  - Define merge semantics (union, intersection, weighted)
  - Handle salience conflicts (same node, different scores)
  - Provenance tracking for merged nodes
  - Consider "engram channels" for topic-based sharing
- **Effort Estimate:** High
- **Priority:** Low (future capability)

---

### 5. Engram Diff / Changelog
- **Status:** `DEFERRED`
- **Source:** ENGRAM_FEATURE_BRICK_SPEC.md Section 8
- **Description:** Track changes between engram sessions for debugging and analysis
- **Rationale:** Useful for understanding memory evolution, but not critical for v1
- **Dependencies:** None
- **Implementation Notes:**
  - Store previous engram as `engram.prev.jsonld` or embed diff in manifest
  - Track: nodes added, nodes dropped, salience changes
  - Could enable "memory replay" for debugging
- **Effort Estimate:** Low
- **Priority:** Low

---

## Knowledge Graph (kg.py)

### 6. Node Relationship Indexing
- **Status:** `DEFERRED`
- **Source:** Performance observation during engram implementation
- **Description:** Build adjacency index for faster neighbor lookups
- **Rationale:** Current BFS in `extract_subgraph()` scans all nodes for each edge lookup
- **Dependencies:** None
- **Implementation Notes:**
  - Build `{node_id: [neighbor_ids]}` index on KG load
  - Invalidate/rebuild on `add_knowledge()`, `mark_deprecated()`
  - Trade memory for speed on large KGs
- **Effort Estimate:** Low
- **Priority:** Low (optimize when needed)

---

### 7. KG Compaction / Garbage Collection
- **Status:** `DEFERRED`
- **Source:** Identified during engram design
- **Description:** Remove deprecated nodes after configurable retention period
- **Rationale:** Deprecated nodes accumulate; never cleaned up currently
- **Dependencies:** None
- **Implementation Notes:**
  - Add `compact_kg(kg, max_age_days=30)` function
  - Only remove deprecated nodes older than threshold
  - Preserve nodes referenced by non-deprecated nodes
- **Effort Estimate:** Low
- **Priority:** Low

---

## Stamper (stamper.py)

### 8. Engram Export in All Formats
- **Status:** `DEFERRED`
- **Source:** Identified during stamper modification
- **Description:** Include engram summary in `claude-md`, `github-agent-md`, `a2a-agent-card` exports
- **Rationale:** Exports currently don't reflect session memory state
- **Dependencies:** engram.py complete (DONE)
- **Implementation Notes:**
  - Add "Recent Context" or "Working Memory" section to exports
  - Include top-N salient nodes with labels
  - Truncate for token limits in skill exports
- **Effort Estimate:** Low
- **Priority:** Medium

---

## UI / Visualization

### 9. Engram Subgraph Visualization
- **Status:** `DEFERRED`
- **Source:** Diary entry 2026-03-26
- **Description:** Visual display of active subgraph in UI
- **Rationale:** Helps users understand what the agent is "thinking about"
- **Dependencies:** UI framework decisions
- **Implementation Notes:**
  - Graph visualization (D3.js, vis.js, or similar)
  - Node size = salience, color = hop depth
  - Click node to see full KG entry
  - Animate salience decay in real-time
- **Effort Estimate:** Medium-High
- **Priority:** Medium (UX improvement)

---

## Ideas Backlog

*Unrefined ideas captured for future consideration:*

| Idea | Source | Notes |
|------|--------|-------|
| Salience-weighted RAG retrieval | Session 2026-03-26 | Use engram salience to boost/demote RAG results |
| Engram compression | - | Delta-encode engrams to reduce storage |
| Cross-capsule node linking | - | Reference nodes from other capsules by URI |
| Temporal engram snapshots | - | Keep N historical engrams for "memory replay" |
| Forgetting curve customization | - | Per-capsule decay curves (aggressive vs persistent) |

---

## Completed Items

*Move items here when done, with completion date:*

| Topic | Completed | Notes |
|-------|-----------|-------|
| Engram v1 Implementation | 2026-03-26 | engram.py with 8 public API functions |
| KG touch_node() helper | 2026-03-26 | Added to kg.py |
| Stamper OPTIONAL_CAPSULE_FILES | 2026-03-26 | engram.jsonld included in restamp |

---

## How to Use This File

1. **Adding new topics:** Copy a template section, fill in all fields
2. **Updating status:** Change status field, add notes with date
3. **Starting work:** Change to `IN_PROGRESS`, reference in diary entry
4. **Completing:** Move to Completed Items table with date
5. **Ideas:** Quick capture in Ideas Backlog, promote to full topic when refined

---

*End of deferred topics tracker*
