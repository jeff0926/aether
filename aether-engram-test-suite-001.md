# AETHER Test Suite Documentation
**Suite ID:** aether-engram-test-suite-001
**Run Date:** 2026-03-26 23:15
**Runner:** pytest 9.0.2
**Python:** 3.13.7 (Windows)
**Result:** 49 passed, 12 warnings, 0 failed
**Duration:** 4.69s

---

## Summary

| Test File | Tests | Passed | Failed | Coverage Area |
|-----------|-------|--------|--------|---------------|
| `test_aec_standalone.py` | 10 | 10 | 0 | AEC verification engine |
| `test_dai_pulse.py` | 13 | 13 | 0 | DAI pulse/heartbeat system |
| `test_engram.py` | 14 | 14 | 0 | Engram working memory |
| `test_exhaustive.py` | 12 | 12 | 0 | Module integration |
| **Total** | **49** | **49** | **0** | |

---

## Test File: `test_aec_standalone.py`

**Purpose:** Validates the Autonomous Epistemic Closure (AEC) verification engine that grounds LLM responses against the knowledge graph.

| # | Test Name | Description |
|---|-----------|-------------|
| 1 | `test_1_perfect_grounding` | Response fully grounded in KG returns score 1.0 |
| 2 | `test_2_complete_failure` | Response with no KG support returns score 0.0 |
| 3 | `test_3_mixed_grounding` | Partial grounding returns proportional score |
| 4 | `test_4_all_persona` | Persona-only statements handled correctly |
| 5 | `test_5_numeric_tolerance` | Numbers within tolerance match (e.g., 99 vs 100) |
| 6 | `test_6_date_normalization` | Date formats normalized before comparison |
| 7 | `test_7_empty_response` | Empty response handled gracefully |
| 8 | `test_8_empty_kg` | Empty KG returns appropriate score |
| 9 | `test_9_large_kg_single_match` | Single match in large KG works correctly |
| 10 | `test_10_formatted_numbers` | Formatted numbers ($1,000,000) parsed correctly |

---

## Test File: `test_dai_pulse.py`

**Purpose:** Validates the DAI (Deliberative AI) pulse system that tracks agent processing phases and emits heartbeat events.

| # | Test Name | Description |
|---|-----------|-------------|
| 1 | `test_phase_transitions` | Valid phase transitions accepted |
| 2 | `test_sequence_increments` | Sequence numbers increment correctly |
| 3 | `test_heartbeat_empty_vars` | Heartbeat works with empty CSS variables |
| 4 | `test_reconnect_state_snapshot` | State preserved on reconnect |
| 5 | `test_ghost_transition_reason` | GHOST state includes reason field |
| 6 | `test_recovery_transition` | Recovery from GHOST state works |
| 7 | `test_unknown_phase_raises` | Unknown phase raises exception |
| 8 | `test_alive_phase_blocked` | Direct transition to ALIVE blocked |
| 9 | `test_min_phase_duration` | Minimum phase duration enforced |
| 10 | `test_event_id_format` | Event IDs follow expected format |
| 11 | `test_timestamp_present` | All events include timestamps |
| 12 | `test_custom_pulse_map` | Custom pulse maps accepted |
| 13 | `test_all_phases_have_vars` | All phases have CSS variable definitions |

---

## Test File: `test_engram.py`

**Purpose:** Validates the engram working memory system that manages node salience, subgraph extraction, and session persistence.

### Class: `TestScoreSalience`

| # | Test Name | Description |
|---|-----------|-------------|
| 1 | `test_score_salience_direct_mention` | Direct mention scores 1.0 |
| 2 | `test_score_salience_inferred` | 1-hop neighbor scores 0.6 |
| 3 | `test_score_salience_decay` | Score decreases with turn_count |
| 4 | `test_score_salience_deprecated_excluded` | Deprecated nodes always score 0.0 |

### Class: `TestExtractSubgraph`

| # | Test Name | Description |
|---|-----------|-------------|
| 5 | `test_extract_subgraph_max_hop` | Nodes beyond max_hop excluded |
| 6 | `test_extract_subgraph_max_nodes` | Result never exceeds max_nodes |

### Class: `TestBuildManifest`

| # | Test Name | Description |
|---|-----------|-------------|
| 7 | `test_build_manifest_schema` | All required JSON-LD fields present |

### Class: `TestSaveLoadManifest`

| # | Test Name | Description |
|---|-----------|-------------|
| 8 | `test_save_load_manifest_roundtrip` | Save then load returns equivalent manifest |

### Class: `TestWarmContext`

| # | Test Name | Description |
|---|-----------|-------------|
| 9 | `test_warm_context_cold_start` | warm=False when no engram.jsonld |
| 10 | `test_warm_context_warm_start` | warm=True, active_nodes populated |
| 11 | `test_warm_context_missing_ids` | missing_ids populated for stale nodes |

### Class: `TestDetectConflict`

| # | Test Name | Description |
|---|-----------|-------------|
| 12 | `test_detect_conflict_verb_pattern` | "I sold the car" conflicts "car" node |
| 13 | `test_detect_conflict_no_false_positive` | "I bought a car" does not conflict |

### Class: `TestCommitSession`

| # | Test Name | Description |
|---|-----------|-------------|
| 14 | `test_commit_session_writes_file` | engram.jsonld created in capsule_path |

---

## Test File: `test_exhaustive.py`

**Purpose:** Integration tests that verify all modules load correctly and work together.

| # | Test Name | Description |
|---|-----------|-------------|
| 1 | `test_module_imports` | All core modules import without error |
| 2 | `test_aec` | AEC module functions callable |
| 3 | `test_kg` | KG module CRUD operations work |
| 4 | `test_capsule` | Capsule loading and validation works |
| 5 | `test_stamper` | Stamper creates valid capsule structures |
| 6 | `test_education` | Education queue operations work |
| 7 | `test_habitat` | Habitat/environment detection works |
| 8 | `test_llm` | LLM provider abstraction works |
| 9 | `test_report` | Report generation works |
| 10 | `test_capsule_integrity` | Capsule files pass integrity checks |
| 11 | `test_integration` | End-to-end pipeline test |
| 12 | `test_known_issues` | Known issues documented and handled |

---

## Warnings (12)

All warnings are pre-existing in `test_exhaustive.py` and relate to test functions returning values instead of None. These are cosmetic and do not affect test validity.

```
PytestReturnNotNoneWarning: Test functions should return None, but
tests/test_exhaustive.py::test_* returned <class 'list'>.
```

**Affected tests:**
- `test_module_imports`
- `test_aec`
- `test_kg`
- `test_capsule`
- `test_stamper`
- `test_education`
- `test_habitat`
- `test_llm`
- `test_report`
- `test_capsule_integrity`
- `test_integration`
- `test_known_issues`

---

## How to Run

```bash
# Full suite
cd C:\Users\I820965\dev\aether
python -m pytest tests/ -v

# Individual test files
python -m pytest tests/test_engram.py -v
python -m pytest tests/test_aec_standalone.py -v
python -m pytest tests/test_dai_pulse.py -v
python -m pytest tests/test_exhaustive.py -v

# Single test
python -m pytest tests/test_engram.py::TestScoreSalience::test_score_salience_direct_mention -v

# With coverage (if pytest-cov installed)
python -m pytest tests/ -v --cov=. --cov-report=html
```

---

## Test Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.2 | Test runner |
| pytest-asyncio | 1.3.0 | Async test support |
| anyio | 4.12.0 | Async I/O |

---

## Coverage by Module

| Module | Test File | Coverage |
|--------|-----------|----------|
| `aec.py` | `test_aec_standalone.py` | Core verification logic |
| `kg.py` | `test_exhaustive.py`, `test_engram.py` | KG CRUD + touch_node |
| `engram.py` | `test_engram.py` | Full API coverage (8 functions) |
| `dai_pulse.py` | `test_dai_pulse.py` | Phase transitions, heartbeats |
| `stamper.py` | `test_exhaustive.py` | Capsule creation |
| `education.py` | `test_exhaustive.py` | Queue operations |
| `aether.py` | `test_exhaustive.py` | Capsule loading |

---

## Known Test Gaps

1. **engram.py edge cases:**
   - Large KG performance (>1000 nodes)
   - Concurrent session commits
   - Malformed engram.jsonld recovery

2. **Integration gaps:**
   - engram.py + aether.py integration (warm_context on capsule load)
   - engram.py + A2A cross-capsule memory

3. **Platform-specific:**
   - Linux/macOS path handling (tested on Windows only)

---

## Revision History

| Rev | Date | Changes |
|-----|------|---------|
| 001 | 2026-03-26 | Initial suite with engram.py tests added |

---

*Generated by Claude Code session 2026-03-26*
