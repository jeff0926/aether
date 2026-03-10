"""
AETHER Exhaustive System Test
Runs all testable surfaces and produces diagnostic report.
"""

import sys
import os
import json
import re
import tempfile
import traceback
import io
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Track all test results
RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "modules": {},
    "aec": {},
    "kg": {},
    "capsule": {},
    "stamper": {},
    "education": {},
    "habitat": {},
    "llm": {},
    "report": {},
    "integration": {},
    "known_issues": {},
    "capsule_inventory": {},
    "metrics": {},
}

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

def test(name: str, expected, actual, compare_fn=None):
    """Record test result."""
    if compare_fn:
        passed = compare_fn(expected, actual)
    else:
        passed = expected == actual
    status = PASS if passed else FAIL
    return {"name": name, "expected": str(expected)[:100], "actual": str(actual)[:100], "status": status}


# =============================================================================
# 1. MODULE IMPORT & SELF-TEST
# =============================================================================

def test_module_imports():
    """Test all modules import cleanly."""
    results = []
    modules = ["aec", "aether", "cli", "education", "habitat", "kg", "llm", "report", "stamper"]

    for mod_name in modules:
        try:
            mod = __import__(mod_name)
            results.append({"module": mod_name, "import": PASS, "self_test": "N/A", "notes": ""})
        except Exception as e:
            results.append({"module": mod_name, "import": FAIL, "self_test": "N/A", "notes": str(e)[:100]})

    RESULTS["modules"] = results
    return results


# =============================================================================
# 2. AEC VERIFICATION
# =============================================================================

def test_aec():
    """Comprehensive AEC tests."""
    from aec import verify, split_statements, _extract_values, deterministic_gate

    results = []

    # 2.1 Statement splitting
    r = split_statements("First sentence. Second sentence. Third sentence.")
    results.append(test("split_basic", 3, len(r)))

    r = split_statements("Mr. Smith went to Washington. He met Dr. Jones.")
    results.append(test("split_abbreviations", 2, len(r)))

    r = split_statements("")
    results.append(test("split_empty", [], r))

    r = split_statements("Hi.")
    results.append(test("split_short", [], r))

    # 2.2 Value extraction
    r = _extract_values("The cost was 1,743 dollars")
    found_1743 = any(v[1] == 1743.0 for v in r if v[2] == "number")
    results.append(test("extract_numbers", True, found_1743))

    r = _extract_values("Born in 1743")
    found_year = any(v[1] == "1743" and v[2] == "date" for v in r)
    results.append(test("extract_year", True, found_year))

    r = _extract_values("Born on April 13, 1743")
    found_date = any("1743-04-13" in str(v[1]) for v in r)
    results.append(test("extract_full_date", True, found_date))

    r = _extract_values("Growth was 19.8%")
    found_pct = any(isinstance(v[1], (int, float)) and abs(v[1] - 19.8) < 0.01 and v[2] == "percentage" for v in r)
    results.append(test("extract_percentage", True, found_pct))

    r = _extract_values("Thomas Jefferson was president")
    found_name = any("Thomas Jefferson" in str(v[0]) for v in r)
    results.append(test("extract_name", True, found_name))

    # Magnitude extraction (known issue 5.6)
    r = _extract_values("Revenue was $25 million")
    found_25m = any(abs(v[1] - 25000000) < 1 for v in r if isinstance(v[1], (int, float)))
    results.append(test("extract_magnitude_million", True, found_25m))
    RESULTS["known_issues"]["magnitude_million"] = {"expected": 25000000, "actual": [v for v in r], "status": PASS if found_25m else FAIL}

    r = _extract_values("Market cap is $373.3 billion")
    found_373b = any(abs(v[1] - 373300000000) < 1e6 for v in r if isinstance(v[1], (int, float)))
    results.append(test("extract_magnitude_billion", True, found_373b))
    RESULTS["known_issues"]["magnitude_billion"] = {"expected": 373300000000, "actual": [v for v in r], "status": PASS if found_373b else FAIL}

    # 2.3 Deterministic gate
    r = deterministic_gate("Jefferson was born in 1743", [
        {"@id": "person:jefferson", "birth_year": 1743}
    ])
    results.append(test("gate_match", True, r["matched"]))

    r = deterministic_gate("Jefferson was born in 1750", [
        {"@id": "person:jefferson", "birth_year": 1743}
    ])
    results.append(test("gate_no_match", False, r["matched"]))

    r = deterministic_gate("He was a brilliant thinker", [
        {"@id": "person:jefferson", "birth_year": 1743}
    ])
    results.append(test("gate_no_values", "no_values", r["method"]))

    r = deterministic_gate("Born in 1743", [])
    results.append(test("gate_empty_kg", "no_input", r["method"]))

    # 2.4 Full verify
    r = verify(
        "Thomas Jefferson was born on April 13, 1743 in Virginia. He authored the Declaration of Independence in 1776.",
        [
            {"@id": "person:jefferson", "rdfs:label": "Thomas Jefferson", "birth_year": 1743, "birth_date": "1743-04-13"},
            {"@id": "doc:declaration", "year": 1776, "author": "Thomas Jefferson"},
        ]
    )
    results.append(test("verify_grounded_score", True, r["score"] >= 0.5))
    results.append(test("verify_grounded_passed", True, r["passed"]))

    r = verify(
        "Jefferson was born in 1743. He was a brilliant thinker. He died in 1850.",
        [{"@id": "person:jefferson", "birth_year": 1743, "death_year": 1826}]
    )
    results.append(test("verify_mixed_has_ungrounded", True, r["ungrounded_statements"] > 0))

    r = verify(
        "He was a brilliant thinker and visionary leader who inspired millions.",
        [{"@id": "person:jefferson", "birth_year": 1743}]
    )
    results.append(test("verify_all_persona_passes", True, r["passed"]))
    results.append(test("verify_all_persona_score", 1.0, r["score"]))

    r = verify("", [{"@id": "test"}])
    results.append(test("verify_empty_response", False, r["passed"]))

    # Numeric tolerance
    r = verify("The value was 99.5", [{"@id": "test", "value": 100}])
    results.append(test("verify_numeric_tolerance", True, r["grounded_statements"] > 0))
    RESULTS["known_issues"]["numeric_tolerance"] = {"expected": "99.5 matches 100 within 1%", "actual": f"grounded={r['grounded_statements']}", "status": PASS if r['grounded_statements'] > 0 else FAIL}

    RESULTS["aec"] = results
    return results


# =============================================================================
# 3. KNOWLEDGE GRAPH
# =============================================================================

def test_kg():
    """Knowledge graph tests."""
    from kg import load_kg, get_nodes, query_nodes, add_knowledge, add_acquired
    from kg import mark_deprecated, mark_updated, get_nodes_by_origin, save_kg, stats, EMPTY_KG, ORIGIN_TYPES

    results = []

    # 3.1 Load/create
    r = load_kg("nonexistent_path_12345.jsonld")
    results.append(test("load_nonexistent", True, "@graph" in r))

    # 3.2 Add knowledge with all 5 origin types
    kg = {"@context": EMPTY_KG["@context"].copy(), "@graph": [
        {"@id": "test:core1", "rdfs:label": "Core Node", "value": 100}
    ]}
    kg = add_knowledge(kg, {"subject": "Fact A", "predicate": "relates_to", "object": "X", "confidence": 0.9}, origin="acquired")
    kg = add_knowledge(kg, {"subject": "Source Doc", "predicate": "url", "object": "http://example.com"}, origin="provenance")
    s = stats(kg)
    results.append(test("stats_core", 1, s["core"]))
    results.append(test("stats_acquired", 1, s["acquired"]))
    results.append(test("stats_provenance", 1, s["provenance"]))

    # 3.3 Mark operations
    kg = mark_deprecated(kg, "test:core1", reason="outdated")
    deprecated = get_nodes_by_origin(kg, "deprecated")
    results.append(test("mark_deprecated", 1, len(deprecated)))

    # After deprecation, stats changes
    s = stats(kg)
    results.append(test("stats_deprecated", 1, s["deprecated"]))

    kg = mark_updated(kg, "test:core1", {"value": 150})
    updated_node = [n for n in get_nodes(kg) if n.get("@id") == "test:core1"][0]
    results.append(test("mark_updated_value", 150, updated_node["value"]))

    # 3.4 Query nodes
    kg2 = {"@context": {}, "@graph": [{"@id": "test", "rdfs:label": "Core Node Test"}]}
    r = query_nodes(kg2, ["Core"])
    results.append(test("query_nodes", True, len(r) > 0))

    r = query_nodes(kg2, [])
    results.append(test("query_empty", [], r))

    # 3.5 Invalid origin
    try:
        add_knowledge(kg, {"subject": "X", "predicate": "Y", "object": "Z"}, origin="invalid")
        results.append(test("invalid_origin", "ValueError", "No exception"))
    except ValueError:
        results.append(test("invalid_origin", "ValueError", "ValueError"))

    # 3.6 Save and reload
    with tempfile.NamedTemporaryFile(suffix=".jsonld", delete=False, mode='w') as f:
        temp_path = f.name
    try:
        save_kg(kg, temp_path)
        reloaded = load_kg(temp_path)
        results.append(test("save_reload", len(get_nodes(kg)), len(get_nodes(reloaded))))
    finally:
        os.unlink(temp_path)

    RESULTS["kg"] = results
    return results


# =============================================================================
# 4. CAPSULE & PIPELINE
# =============================================================================

def test_capsule():
    """Capsule and pipeline tests."""
    from aether import Capsule, validate_folder, generate_id, get_required_files
    from llm import make_llm_fn

    results = []
    capsule_dirs = []

    # Find all example capsules
    examples_dir = Path(__file__).parent.parent / "examples"
    if examples_dir.exists():
        capsule_dirs = [d for d in examples_dir.iterdir() if d.is_dir()]

    # 4.1 Validate all example capsules
    for capsule_dir in capsule_dirs:
        missing = validate_folder(capsule_dir)
        results.append(test(f"validate_{capsule_dir.name}", [], missing))

        # Record inventory
        RESULTS["capsule_inventory"][capsule_dir.name] = {
            "path": str(capsule_dir),
            "valid": len(missing) == 0,
            "missing": missing,
        }

    # 4.2 Load each capsule
    for capsule_dir in capsule_dirs:
        try:
            cap = Capsule(capsule_dir)
            results.append(test(f"load_{capsule_dir.name}", True, cap.id is not None))
            RESULTS["capsule_inventory"][capsule_dir.name].update({
                "id": cap.id,
                "name": cap.name,
                "version": cap.version,
                "kb_size": len(cap.files["kb"]),
                "kg_nodes": len(cap.files["kg"].get("@graph", [])),
            })
        except Exception as e:
            results.append(test(f"load_{capsule_dir.name}", True, f"FAIL: {e}"))
            RESULTS["capsule_inventory"][capsule_dir.name]["load_error"] = str(e)

    # 4.3 Run pipeline with stub LLM
    stub_fn = make_llm_fn(provider="stub")

    test_queries = {
        "jefferson": "When was Thomas Jefferson born?",
        "scholar-buffett": "How much did Berkshire pay for See's Candies?",
        "test-agent-v1.0.0-24f8476e": "What is Aether?",
    }

    for capsule_name, query in test_queries.items():
        capsule_dir = examples_dir / capsule_name
        if not capsule_dir.exists():
            continue
        try:
            cap = Capsule(capsule_dir, llm_fn=stub_fn)
            ctx = cap.run(query)

            results.append(test(f"run_{capsule_name}_distill", True, "intent" in ctx["distilled"]))
            results.append(test(f"run_{capsule_name}_augment", True, "kb" in ctx["augmented"]))
            results.append(test(f"run_{capsule_name}_generate", True, len(ctx["generated"]) > 0))
            results.append(test(f"run_{capsule_name}_review", True, "aec" in ctx["review"]))
            results.append(test(f"run_{capsule_name}_telemetry", True, "total_ms" in ctx["telemetry"]))

            # Record detailed results
            RESULTS["capsule_inventory"][capsule_name].update({
                "aec_score": ctx["review"]["aec"]["score"],
                "aec_passed": ctx["review"]["aec"]["passed"],
                "grounded": ctx["review"]["aec"]["grounded_statements"],
                "ungrounded": ctx["review"]["aec"]["ungrounded_statements"],
                "persona": ctx["review"]["aec"]["persona_statements"],
                "telemetry_ms": ctx["telemetry"]["total_ms"],
            })
        except Exception as e:
            results.append(test(f"run_{capsule_name}", True, f"FAIL: {e}"))

    # 4.4 Validator capsule (generate disabled)
    validator_dir = examples_dir / "aether-validator-v1.0.0-d5a16071"
    if validator_dir.exists():
        try:
            cap = Capsule(validator_dir, llm_fn=stub_fn)
            ctx = cap.run("Validate this text")
            generate_enabled = cap.files["definition"].get("pipeline", {}).get("generate", {}).get("enabled", True)
            results.append(test("validator_generate_disabled", False, generate_enabled))
        except Exception as e:
            results.append(test("validator_capsule", True, f"FAIL: {e}"))

    # 4.5 generate_id format
    test_id = generate_id("Test Agent", "1.0.0")
    pattern = r'^[a-z0-9-]+-v\d+\.\d+\.\d+-[a-f0-9]{8}$'
    results.append(test("generate_id_format", True, bool(re.match(pattern, test_id))))

    RESULTS["capsule"] = results
    return results


# =============================================================================
# 5. STAMPER
# =============================================================================

def test_stamper():
    """Stamper tests."""
    from stamper import stamp_empty, stamp_from_source, validate_capsule, restamp

    results = []

    with tempfile.TemporaryDirectory() as tmp:
        # 5.1 Stamp empty capsule
        path = stamp_empty("Test Agent", tmp)
        validation = validate_capsule(path)
        results.append(test("stamp_empty_valid", True, validation["valid"]))

        # 5.2 Verify file naming convention
        files = [f.name for f in path.iterdir()]
        all_prefixed = all(f.startswith(path.name) for f in files)
        results.append(test("files_prefixed", True, all_prefixed))

        # 5.3 Stamp from markdown source
        md_file = Path(tmp) / "test_kb.md"
        md_file.write_text("# Test Knowledge\n\nSome content here.")
        path2 = stamp_from_source("KB Agent", str(md_file), tmp)
        kb_content = (path2 / f"{path2.name}-kb.md").read_text()
        results.append(test("stamp_from_md", True, "Some content here" in kb_content))

        # 5.4 Stamp from JSON-LD source
        jsonld_file = Path(tmp) / "test_kg.jsonld"
        jsonld_file.write_text('{"@context": {}, "@graph": [{"@id": "test"}]}')
        path3 = stamp_from_source("KG Agent", str(jsonld_file), tmp)
        kg_content = json.loads((path3 / f"{path3.name}-kg.jsonld").read_text())
        results.append(test("stamp_from_jsonld", True, len(kg_content.get("@graph", [])) > 0))

        # 5.5 Restamp with lineage
        path4 = restamp(path, "1.1.0")
        manifest = json.loads((path4 / f"{path4.name}-manifest.json").read_text())
        has_lineage = "previous_id" in manifest and "previous_version" in manifest
        results.append(test("restamp_lineage", True, has_lineage))

        # 5.6 Validate invalid folder
        validation = validate_capsule(Path(tmp) / "nonexistent")
        results.append(test("validate_invalid", False, validation["valid"]))

    RESULTS["stamper"] = results
    return results


# =============================================================================
# 6. EDUCATION QUEUE
# =============================================================================

def test_education():
    """Education queue tests."""
    from education import queue_failure, get_queue, get_pending, update_status
    from education import queue_stats, get_oldest_pending, _parse_json_response, _build_research_prompt

    results = []

    with tempfile.TemporaryDirectory() as tmp:
        capsule = Path(tmp) / "test-capsule"
        capsule.mkdir()

        # 6.1 Queue a failure
        aec_result = {
            "score": 0.4, "threshold": 0.8, "passed": False,
            "gaps": [{"text": "Wrong date", "reason": "values_not_in_kg"}]
        }
        record = queue_failure(capsule, "Test query", "Test response", aec_result)
        results.append(test("queue_failure_status", "pending", record["status"]))
        results.append(test("queue_failure_score", 0.4, record["aec_score"]))

        # 6.2 Get pending
        pending = get_pending(capsule)
        results.append(test("get_pending", 1, len(pending)))

        # 6.3 Update status
        update_status(capsule, record["id"], "researching")
        queue = get_queue(capsule)
        results.append(test("update_status", "researching", queue[0]["status"]))

        # 6.4 Queue stats
        stats = queue_stats(capsule)
        results.append(test("queue_stats_total", 1, stats["total"]))
        results.append(test("queue_stats_researching", 1, stats["researching"]))

        # 6.5 Get oldest pending
        queue_failure(capsule, "Query 2", "Response 2", aec_result)
        oldest = get_oldest_pending(capsule)
        results.append(test("get_oldest_pending", True, oldest is not None))

        # 6.6 Parse JSON response
        parsed = _parse_json_response('[{"subject": "A", "predicate": "B", "object": "C"}]')
        results.append(test("parse_json_clean", True, len(parsed) == 1))

        parsed = _parse_json_response('```json\n[{"subject": "A", "predicate": "B", "object": "C"}]\n```')
        results.append(test("parse_json_markdown", True, len(parsed) == 1))

        try:
            _parse_json_response("This is not JSON at all")
            results.append(test("parse_json_garbage", "exception", "no exception"))
        except:
            results.append(test("parse_json_garbage", "exception", "exception"))

        # 6.7 Build research prompt
        prompt = _build_research_prompt([{"text": "Jefferson was born in 1750"}])
        results.append(test("build_research_prompt", True, "Jefferson" in prompt and "JSON" in prompt))

    RESULTS["education"] = results
    return results


# =============================================================================
# 7. HABITAT
# =============================================================================

def test_habitat():
    """Habitat tests."""
    from habitat import Habitat

    results = []

    h = Habitat()

    # 7.1 Register capsules
    h.register("agent-001", {"name": "Agent One", "scent_subscriptions": ["topic.a", "topic.b"]})
    h.register("agent-002", {"name": "Agent Two", "scent_subscriptions": ["topic.b", "topic.c*"]})
    results.append(test("register_count", 2, len(h.list_capsules())))

    # 7.2 Exact route
    r = h.route("topic.a")
    results.append(test("route_exact", ["agent-001"], r))

    # 7.3 Wildcard route
    r = h.route("topic.cats")
    results.append(test("route_wildcard", ["agent-002"], r))

    # 7.4 Multi-match route
    r = h.route("topic.b")
    results.append(test("route_multi", 2, len(r)))

    # 7.5 No match
    r = h.route("unknown.topic")
    results.append(test("route_none", [], r))

    # 7.6 Gap detection
    r = h.detect_gaps("unknown.topic")
    results.append(test("detect_gap", True, r))

    # 7.7 Broadcast
    result = h.broadcast("topic.a", {"data": "test"})
    results.append(test("broadcast", True, len(result["recipients"]) > 0))

    # 7.8 Stats
    s = h.stats()
    results.append(test("stats_capsules", 2, s["capsules"]))

    # 7.9 Unregister
    h.unregister("agent-001")
    results.append(test("unregister", 1, len(h.list_capsules())))

    # 7.10 Log
    results.append(test("log", True, len(h.get_log()) > 0))

    RESULTS["habitat"] = results
    return results


# =============================================================================
# 8. LLM
# =============================================================================

def test_llm():
    """LLM tests."""
    from llm import call_llm, make_llm_fn, estimate_cost

    results = []

    # 8.1 Stub provider
    r = call_llm("Hello world", provider="stub")
    results.append(test("stub_text", True, "text" in r))
    results.append(test("stub_cost", 0.0, r["cost"]))

    # 8.2 make_llm_fn
    fn = make_llm_fn(provider="stub")
    r = fn("Test prompt")
    results.append(test("make_llm_fn", True, isinstance(r, dict) and "text" in r))

    # 8.3 Unknown provider
    r = call_llm("Hello", provider="fake_provider")
    results.append(test("unknown_provider", True, "Unknown" in r["text"] or "Error" in r["text"]))

    # 8.4 Cost estimation
    cost = estimate_cost("claude-sonnet-4-20250514", 1000, 500)
    results.append(test("estimate_cost", True, cost > 0))

    # 8.5 API key error handling (don't call real API)
    # Tested via stub - real API tests skipped to avoid costs

    RESULTS["llm"] = results
    return results


# =============================================================================
# 9. REPORT
# =============================================================================

def test_report():
    """Report generator tests."""
    results = []

    try:
        from report import print_report

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        # Mock data
        mock_ctx = {
            "input": "What is Aether?",
            "distilled": {"intent": "query", "entities": ["Aether"], "brevity": False, "format": None},
            "augmented": {"kb": ["Test para"], "kg": [{"@id": "test", "rdfs:label": "Test"}]},
            "generated": "Aether is a framework.",
            "review": {"passed": True, "aec": {"score": 0.85, "threshold": 0.8, "passed": True,
                       "grounded_statements": 2, "ungrounded_statements": 0, "persona_statements": 1}},
            "telemetry": {"total_ms": 1234.5, "stages": {
                "distill": {"time_ms": 0.5, "entities_extracted": 1},
                "augment": {"time_ms": 1.2, "kb_matches": 1, "kg_matches": 1},
                "generate": {"time_ms": 1230.0, "prompt_chars": 150, "tokens_in": 50, "tokens_out": 100},
                "review": {"time_ms": 0.3},
            }}
        }
        mock_aec = mock_ctx["review"]["aec"]

        class MockCapsule:
            id = "test-agent-v1.0.0-abc12345"
            name = "Test Agent"
            version = "1.0.0"
            files = {
                "manifest": {"id": "test-agent", "name": "Test Agent", "version": "1.0.0"},
                "persona": {"tone": "professional", "style": "concise"},
                "definition": {"review": {"threshold": 0.8}},
                "kb": "# Test\n\nContent.",
                "kg": {"@graph": [{"@id": "test", "rdfs:label": "Test"}]},
            }

        print_report(mock_ctx, mock_aec, MockCapsule())

        report_output = buffer.getvalue()
        sys.stdout = old_stdout

        results.append(test("report_no_crash", True, True))
        results.append(test("report_has_header", True, "AETHER" in report_output))
        results.append(test("report_has_score", True, "Score" in report_output or "score" in report_output or "0.85" in report_output))
        results.append(test("report_length", True, len(report_output) > 100))

    except Exception as e:
        sys.stdout = old_stdout if 'old_stdout' in dir() else sys.stdout
        results.append(test("report_no_crash", True, f"FAIL: {e}"))

    RESULTS["report"] = results
    return results


# =============================================================================
# 10. CAPSULE FILE INTEGRITY
# =============================================================================

def test_capsule_integrity():
    """Detailed capsule file integrity checks."""
    results = []
    examples_dir = Path(__file__).parent.parent / "examples"

    if not examples_dir.exists():
        return results

    for capsule_dir in examples_dir.iterdir():
        if not capsule_dir.is_dir():
            continue

        prefix = capsule_dir.name

        # Check all 5 files exist
        manifest_path = capsule_dir / f"{prefix}-manifest.json"
        definition_path = capsule_dir / f"{prefix}-definition.json"
        persona_path = capsule_dir / f"{prefix}-persona.json"
        kb_path = capsule_dir / f"{prefix}-kb.md"
        kg_path = capsule_dir / f"{prefix}-kg.jsonld"

        all_exist = all(p.exists() for p in [manifest_path, definition_path, persona_path, kb_path, kg_path])
        results.append(test(f"{prefix}_files_exist", True, all_exist))

        if not all_exist:
            continue

        # Check manifest
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            results.append(test(f"{prefix}_manifest_id", True, "id" in manifest))
            results.append(test(f"{prefix}_manifest_version", True, "version" in manifest))
        except:
            results.append(test(f"{prefix}_manifest_parse", True, False))

        # Check definition
        try:
            definition = json.loads(definition_path.read_text(encoding="utf-8"))
            results.append(test(f"{prefix}_definition_pipeline", True, "pipeline" in definition))
        except:
            results.append(test(f"{prefix}_definition_parse", True, False))

        # Check persona
        try:
            persona = json.loads(persona_path.read_text(encoding="utf-8"))
            results.append(test(f"{prefix}_persona_parse", True, isinstance(persona, dict)))
        except:
            results.append(test(f"{prefix}_persona_parse", True, False))

        # Check KB
        kb_content = kb_path.read_text(encoding="utf-8")
        results.append(test(f"{prefix}_kb_nonempty", True, len(kb_content) > 0))

        # Check KG
        try:
            kg = json.loads(kg_path.read_text(encoding="utf-8"))
            results.append(test(f"{prefix}_kg_graph", True, "@graph" in kg or "@id" in kg))
        except:
            results.append(test(f"{prefix}_kg_parse", True, False))

    return results


# =============================================================================
# 11. CROSS-MODULE INTEGRATION
# =============================================================================

def test_integration():
    """Cross-module integration tests."""
    results = []

    # 11.1 Full pipeline flow
    try:
        from aether import Capsule
        from llm import make_llm_fn
        from education import get_queue

        examples_dir = Path(__file__).parent.parent / "examples"
        jefferson_dir = examples_dir / "jefferson"

        if jefferson_dir.exists():
            stub_fn = make_llm_fn(provider="stub")
            cap = Capsule(jefferson_dir, llm_fn=stub_fn)
            ctx = cap.run("When was Jefferson born?")

            results.append(test("integration_pipeline_runs", True, ctx is not None))
            results.append(test("integration_aec_in_review", True, "aec" in ctx["review"]))
            results.append(test("integration_telemetry", True, ctx["telemetry"]["total_ms"] > 0))
    except Exception as e:
        results.append(test("integration_pipeline", True, f"FAIL: {e}"))

    # 11.2 Stamp → Load → Run cycle
    try:
        from stamper import stamp_empty
        from aether import Capsule
        from llm import make_llm_fn

        with tempfile.TemporaryDirectory() as tmp:
            path = stamp_empty("Integration Test", tmp)
            cap = Capsule(path, llm_fn=make_llm_fn(provider="stub"))
            ctx = cap.run("Test query")
            results.append(test("integration_stamp_load_run", True, ctx is not None))
    except Exception as e:
        results.append(test("integration_stamp_load_run", True, f"FAIL: {e}"))

    # 11.3 Habitat routing
    try:
        from habitat import Habitat

        h = Habitat()
        h.register("test-001", {"name": "Test", "scent_subscriptions": ["test.*"]})
        matched = h.route("test.query")
        results.append(test("integration_habitat_route", True, len(matched) > 0))
    except Exception as e:
        results.append(test("integration_habitat_route", True, f"FAIL: {e}"))

    RESULTS["integration"] = results
    return results


# =============================================================================
# 12. KNOWN ISSUES VERIFICATION
# =============================================================================

def test_known_issues():
    """Verify status of known issues."""
    from aec import _extract_values, verify
    from kg import load_kg, get_nodes

    results = []

    # 12.1 Magnitude extraction
    r = _extract_values("$25 million revenue")
    found_25m = any(abs(v[1] - 25000000) < 1 for v in r if isinstance(v[1], (int, float)))
    results.append(test("known_magnitude_25m", True, found_25m))

    # 12.2 Name matching looseness
    r = _extract_values("Thomas wrote this")
    has_thomas = any("Thomas" in str(v[0]) for v in r)
    results.append(test("known_name_partial", True, has_thomas))

    # 12.3 Check education queues in example capsules
    examples_dir = Path(__file__).parent.parent / "examples"
    for capsule_dir in examples_dir.iterdir():
        if not capsule_dir.is_dir():
            continue
        queue_file = capsule_dir / "education-queue.json"
        if queue_file.exists():
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
            pending = [r for r in queue if r.get("status") == "pending"]
            RESULTS["known_issues"][f"{capsule_dir.name}_queue"] = {
                "total": len(queue),
                "pending": len(pending),
                "scores": [r.get("aec_score") for r in queue],
            }

    return results


# =============================================================================
# METRICS
# =============================================================================

def collect_metrics():
    """Collect codebase metrics."""
    root = Path(__file__).parent.parent

    py_files = list(root.glob("*.py"))
    total_lines = 0
    file_lines = {}

    for f in py_files:
        lines = len(f.read_text(encoding="utf-8").splitlines())
        file_lines[f.name] = lines
        total_lines += lines

    # Add test files
    test_files = list((root / "tests").glob("*.py"))
    for f in test_files:
        lines = len(f.read_text(encoding="utf-8").splitlines())
        file_lines[f"tests/{f.name}"] = lines
        total_lines += lines

    RESULTS["metrics"] = {
        "total_python_files": len(py_files) + len(test_files),
        "total_lines": total_lines,
        "file_lines": file_lines,
        "external_deps": ["anthropic (optional)", "openai (optional)"],
        "python_version": "3.11+",
    }


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report():
    """Generate markdown report."""

    # Count results
    total = 0
    passed = 0
    failed = 0

    def count_results(data):
        nonlocal total, passed, failed
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "status" in item:
                    total += 1
                    if item["status"] == PASS:
                        passed += 1
                    else:
                        failed += 1

    for key in ["modules", "aec", "kg", "capsule", "stamper", "education", "habitat", "llm", "report", "integration"]:
        count_results(RESULTS.get(key, []))

    # Generate markdown
    lines = [
        "# AETHER System Diagnostic Report",
        f"## Generated: {RESULTS['timestamp']}",
        "## Framework Version: Phase 2",
        "",
        "---",
        "",
        "### Executive Summary",
        f"- **Total tests:** {total}",
        f"- **Passed:** {passed}",
        f"- **Failed:** {failed}",
        f"- **Pass rate:** {passed/total*100:.1f}%" if total > 0 else "- Pass rate: N/A",
        "",
        "---",
        "",
    ]

    # Module Health
    lines.extend([
        "### Module Health",
        "",
        "| Module | Import | Notes |",
        "|--------|--------|-------|",
    ])
    for m in RESULTS.get("modules", []):
        lines.append(f"| `{m['module']}` | {m['import']} | {m['notes'][:50]} |")
    lines.append("")

    # Helper to generate test tables
    def add_test_table(title, key):
        lines.extend(["", f"### {title}", "", "| Test | Expected | Actual | Status |", "|------|----------|--------|--------|"])
        for r in RESULTS.get(key, []):
            if isinstance(r, dict) and "name" in r:
                lines.append(f"| {r['name']} | {r['expected'][:30]} | {r['actual'][:30]} | {r['status']} |")
        lines.append("")

    add_test_table("AEC Verification Tests", "aec")
    add_test_table("Knowledge Graph Tests", "kg")
    add_test_table("Capsule & Pipeline Tests", "capsule")
    add_test_table("Stamper Tests", "stamper")
    add_test_table("Education Queue Tests", "education")
    add_test_table("Habitat Tests", "habitat")
    add_test_table("LLM Tests", "llm")
    add_test_table("Report Generator Tests", "report")
    add_test_table("Cross-Module Integration", "integration")

    # Known Issues
    lines.extend(["", "### Known Issues Status", "", "| Issue | Status | Details |", "|-------|--------|---------|"])
    for issue, data in RESULTS.get("known_issues", {}).items():
        status = data.get("status", "N/A")
        details = str(data)[:60]
        lines.append(f"| {issue} | {status} | {details} |")
    lines.append("")

    # Capsule Inventory
    lines.extend(["", "### Capsule Inventory", "", "| Capsule | Valid | KB Size | KG Nodes | AEC Score |", "|---------|-------|---------|----------|-----------|"])
    for name, data in RESULTS.get("capsule_inventory", {}).items():
        valid = "Yes" if data.get("valid", False) else "No"
        kb = data.get("kb_size", "N/A")
        kg = data.get("kg_nodes", "N/A")
        score = data.get("aec_score", "N/A")
        lines.append(f"| `{name}` | {valid} | {kb} | {kg} | {score} |")
    lines.append("")

    # Codebase Metrics
    metrics = RESULTS.get("metrics", {})
    lines.extend([
        "",
        "### Codebase Metrics",
        "",
        f"- **Total Python files:** {metrics.get('total_python_files', 'N/A')}",
        f"- **Total lines:** {metrics.get('total_lines', 'N/A')}",
        f"- **External dependencies:** {', '.join(metrics.get('external_deps', []))}",
        f"- **Python version:** {metrics.get('python_version', 'N/A')}",
        "",
        "#### Lines per file:",
        "",
        "| File | Lines |",
        "|------|-------|",
    ])
    for f, l in sorted(metrics.get("file_lines", {}).items(), key=lambda x: -x[1]):
        lines.append(f"| `{f}` | {l} |")

    # Recommendations
    lines.extend([
        "",
        "---",
        "",
        "### Recommendations",
        "",
    ])
    if failed > 0:
        lines.append(f"- **{failed} test(s) failed** - Review failed tests above")

    for key, data in RESULTS.get("known_issues", {}).items():
        if data.get("status") == FAIL:
            lines.append(f"- Known issue `{key}` is still failing")

    if failed == 0:
        lines.append("- All tests passed. System is healthy.")

    lines.extend([
        "",
        "---",
        "",
        "*Report generated by test_exhaustive.py*",
    ])

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("AETHER Exhaustive System Test")
    print("=" * 60)
    print()

    # Run all tests
    print("[1/12] Testing module imports...")
    test_module_imports()

    print("[2/12] Testing AEC verification...")
    test_aec()

    print("[3/12] Testing knowledge graph...")
    test_kg()

    print("[4/12] Testing capsule & pipeline...")
    test_capsule()

    print("[5/12] Testing stamper...")
    test_stamper()

    print("[6/12] Testing education queue...")
    test_education()

    print("[7/12] Testing habitat...")
    test_habitat()

    print("[8/12] Testing LLM...")
    test_llm()

    print("[9/12] Testing report generator...")
    test_report()

    print("[10/12] Testing capsule integrity...")
    integrity_results = test_capsule_integrity()
    RESULTS["capsule"].extend(integrity_results)

    print("[11/12] Testing cross-module integration...")
    test_integration()

    print("[12/12] Testing known issues...")
    test_known_issues()

    print()
    print("Collecting metrics...")
    collect_metrics()

    print("Generating report...")
    report = generate_report()

    # Save report
    report_dir = Path(__file__).parent.parent / "IGNORE" / "daily"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"AETHER_SYSTEM_REPORT_{datetime.now().strftime('%Y-%m-%d')}.md"
    report_path.write_text(report, encoding="utf-8")

    print()
    print("=" * 60)
    print(f"Report saved to: {report_path}")
    print("=" * 60)

    # Print summary
    total = sum(1 for key in ["modules", "aec", "kg", "capsule", "stamper", "education", "habitat", "llm", "report", "integration"]
                for item in RESULTS.get(key, []) if isinstance(item, dict) and "status" in item)
    passed = sum(1 for key in ["modules", "aec", "kg", "capsule", "stamper", "education", "habitat", "llm", "report", "integration"]
                 for item in RESULTS.get(key, []) if isinstance(item, dict) and item.get("status") == PASS)

    print()
    print(f"Total: {total} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
