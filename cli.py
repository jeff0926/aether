"""
CLI - Command-line interface for Aether.
"""

import argparse
import json
import sys
import io
from pathlib import Path

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from aether import Capsule, validate_folder, get_required_files
from stamper import stamp_empty, stamp_from_source, validate_capsule, export_capsule
from llm import make_llm_fn
from kg import load_kg, stats as kg_stats
from education import queue_stats, get_pending, get_oldest_pending, educate, refine_session
from ingest import ingest_research, ingest_document, ingest_skill


def cmd_stamp(args):
    """Create a new capsule."""
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    psi = getattr(args, 'psi', False)

    if args.source:
        path = stamp_from_source(args.name, args.source, output, args.version, psi=psi)
        print(f"Stamped from source: {path}")
    else:
        path = stamp_empty(args.name, output, args.version, psi=psi)
        print(f"Stamped empty: {path}")

    validation = validate_capsule(path)
    print(f"Valid: {validation['valid']}")

    if psi:
        print(f"PSI enabled: {path.name}-psi.jsonld + pulse-map.json created")


def cmd_run(args):
    """Run a capsule with a query."""
    missing = validate_folder(args.capsule)
    if missing:
        print(f"Invalid capsule. Missing: {missing}")
        return

    llm_fn = make_llm_fn(provider=args.provider, model=args.model)
    capsule = Capsule(args.capsule, llm_fn=llm_fn)

    print(f"Running: {capsule}")
    print(f"Query: {args.query}\n")

    ctx = capsule.run(args.query)

    # AEC results come from pipeline review stage
    aec_result = ctx["review"]["aec"]

    print(f"Generated:\n{ctx['generated']}\n")
    print(f"AEC Score: {aec_result['score']} (threshold: {aec_result['threshold']})")
    print(f"AEC Passed: {aec_result['passed']}")
    print(f"Statements: {aec_result['grounded_statements']}G / {aec_result['ungrounded_statements']}U / {aec_result['persona_statements']}P")

    # Print telemetry
    tel = ctx.get("telemetry", {})
    stages = tel.get("stages", {})
    print(f"\n--- Telemetry ---")
    print(f"Total: {tel.get('total_ms', 0):.1f}ms")

    if "distill" in stages:
        d = stages["distill"]
        print(f"  Distill:  {d['time_ms']:6.1f}ms | entities: {d['entities_extracted']}")

    if "augment" in stages:
        a = stages["augment"]
        print(f"  Augment:  {a['time_ms']:6.1f}ms | kb: {a['kb_matches']}, kg: {a['kg_matches']}")

    if "generate" in stages:
        g = stages["generate"]
        print(f"  Generate: {g['time_ms']:6.1f}ms | prompt: {g['prompt_chars']} chars")
        if g.get("tokens_in") or g.get("tokens_out"):
            print(f"            tokens: {g['tokens_in']} in, {g['tokens_out']} out")

    if "review" in stages:
        r = stages["review"]
        print(f"  Review:   {r['time_ms']:6.1f}ms")

    # Full report if requested
    if args.report == "full":
        from report import print_report
        print_report(ctx, aec_result, capsule)

    # PSI/CVP events if requested
    if args.psi:
        from psi import pipeline_to_psi, AetherEmitter
        print(f"\n--- PSI Events (DAI Pulse) ---")
        emitter = AetherEmitter(capsule.id, scope=f"#aether-{capsule.id}")
        events = pipeline_to_psi(ctx, emitter)
        for event in events:
            print(event)


def cmd_validate(args):
    """Validate a capsule folder."""
    result = validate_capsule(args.capsule)
    print(f"Path: {args.capsule}")
    print(f"Valid: {result['valid']}")
    if result["missing"]:
        print(f"Missing: {result['missing']}")
    if result["errors"]:
        print(f"Errors: {result['errors']}")

    # PSI IRI cross-reference validation (warnings only)
    capsule_path = Path(args.capsule)
    prefix = capsule_path.name
    psi_path = capsule_path / f"{prefix}-psi.jsonld"

    if psi_path.exists():
        try:
            with open(psi_path, "r", encoding="utf-8") as f:
                psi_data = json.load(f)

            # Load KG for cross-reference
            kg_path = capsule_path / f"{prefix}-kg.jsonld"
            kg_ids = set()
            kg_deprecated = {}  # id -> replacedBy (if any)

            if kg_path.exists():
                with open(kg_path, "r", encoding="utf-8") as f:
                    kg_data = json.load(f)
                for node in kg_data.get("@graph", []):
                    node_id = node.get("@id", "")
                    kg_ids.add(node_id)
                    if node.get("aether:status") == "deprecated":
                        kg_deprecated[node_id] = node.get("aether:replacedBy")

            # Check PSI projections for orphaned IRIs
            projections = psi_data.get("psi:projections", [])
            orphaned = []
            deprecated_refs = []
            valid_count = 0

            for proj in projections:
                binds_to = proj.get("psi:binds_to_kg", "")
                if binds_to:
                    if binds_to not in kg_ids:
                        orphaned.append(binds_to)
                    elif binds_to in kg_deprecated:
                        replacement = kg_deprecated[binds_to]
                        deprecated_refs.append((binds_to, replacement))
                    else:
                        valid_count += 1

            # Print PSI validation results
            if orphaned:
                print(f"\n\u26a0 psi.jsonld \u2014 {len(orphaned)} orphaned IRIs:")
                for iri in orphaned:
                    print(f"    {iri} \u2192 not found in kg.jsonld")

            if deprecated_refs:
                for iri, replacement in deprecated_refs:
                    if replacement:
                        print(f"    {iri} \u2192 deprecated (see {replacement})")
                    else:
                        print(f"    {iri} \u2192 deprecated")

            if valid_count > 0 or (not orphaned and not deprecated_refs and projections):
                print(f"\u2713 psi.jsonld \u2014 {len(projections)} projections valid")
            elif not projections:
                print(f"\u2713 psi.jsonld \u2014 empty projection graph")

        except (json.JSONDecodeError, IOError) as e:
            print(f"\u26a0 psi.jsonld \u2014 could not parse: {e}")


def cmd_info(args):
    """Show capsule information."""
    missing = validate_folder(args.capsule)
    if missing:
        print(f"Invalid capsule. Missing: {missing}")
        return

    capsule_path = Path(args.capsule)
    capsule = Capsule(capsule_path)
    files = get_required_files(capsule_path.name)
    kg = load_kg(capsule_path / files["kg"])

    print(f"ID: {capsule.id}")
    print(f"Name: {capsule.name}")
    print(f"Version: {capsule.version}")
    print(f"Path: {capsule.path}")
    print(f"\nKG Stats: {kg_stats(kg)}")
    print(f"KB Size: {len(capsule.files['kb'])} chars")

    # File sizes
    print("\nFiles:")
    for key, filename in files.items():
        size = (capsule_path / filename).stat().st_size
        print(f"  {filename}: {size} bytes")


def cmd_queue(args):
    """Show education queue stats and pending items."""
    capsule_path = Path(args.capsule)
    if not capsule_path.is_dir():
        print(f"Invalid capsule path: {args.capsule}")
        return

    stats = queue_stats(capsule_path)
    print(f"Education Queue: {capsule_path.name}")
    print(f"  Total:       {stats['total']}")
    print(f"  Pending:     {stats['pending']}")
    print(f"  Researching: {stats['researching']}")
    print(f"  Validated:   {stats['validated']}")
    print(f"  Integrated:  {stats['integrated']}")
    print(f"  Failed:      {stats['failed']}")

    pending = get_pending(capsule_path)
    if pending:
        print(f"\nPending items ({len(pending)}):")
        for item in pending[:10]:  # Show first 10
            query = item.get("query", "")[:50]
            score = item.get("aec_score", 0)
            print(f"  [{item['id']}] score={score:.2f} | {query}...")
        if len(pending) > 10:
            print(f"  ... and {len(pending) - 10} more")
    else:
        print("\nNo pending items.")


def cmd_educate(args):
    """Run self-education on a pending failure."""
    capsule_path = Path(args.capsule)
    if not capsule_path.is_dir():
        print(f"Invalid capsule path: {args.capsule}")
        return

    # Get record ID - either specified or oldest pending
    if args.record_id:
        record_id = args.record_id
    else:
        oldest = get_oldest_pending(capsule_path)
        if not oldest:
            print("No pending failures to educate.")
            return
        record_id = oldest["id"]

    print(f"Educating: {record_id}")
    print(f"Capsule: {capsule_path.name}")

    # Create LLM function
    llm_fn = make_llm_fn(provider=args.provider, model=args.model)

    # Run education
    result = educate(capsule_path, record_id, llm_fn)

    print(f"\n--- Education Result ---")
    print(f"Status: {result['status']}")
    print(f"Original Score: {result['original_score']:.2f}")
    print(f"New Score: {result['new_score']:.2f}")
    print(f"Triples Added: {result['triples_added']}")
    if result.get("research_tokens"):
        tokens = result["research_tokens"]
        print(f"Research Tokens: {tokens.get('in', 0)} in, {tokens.get('out', 0)} out")
    if result.get("reason"):
        print(f"Reason: {result['reason']}")


def cmd_verify(args):
    """Run standalone AEC verification."""
    from aec import verify
    from kg import get_nodes
    from aec_concept import compile_kg, has_typed_nodes

    # Load text (from arg or file)
    text = args.text
    if Path(text).exists():
        text = Path(text).read_text(encoding="utf-8")

    # Load reference KG
    kg = load_kg(args.reference)
    nodes = get_nodes(kg)

    # Compile KG for concept matching if it has typed nodes
    compiled_kg = compile_kg(nodes) if has_typed_nodes(nodes) else None

    # Create LLM function for Layer 2 if provider is not stub
    llm_fn = None
    if args.provider != "stub":
        llm_fn = make_llm_fn(provider=args.provider, model=args.model)

    threshold = args.threshold or 0.8
    result = verify(text, nodes, threshold, compiled_kg=compiled_kg, llm_fn=llm_fn)

    print(f"AEC Score: {result['score']} (threshold: {result['threshold']})")
    print(f"Passed: {result['passed']}")
    print(f"Statements: {result['grounded_statements']}G / {result['ungrounded_statements']}U / {result['persona_statements']}P")
    print(f"Persona Ratio: {result['persona_ratio']}")
    if result.get('concept_applied'):
        print("Concept matching: applied")
    if llm_fn:
        print("Layer 2 LLM: enabled")
    if result['gaps']:
        print(f"\nGaps ({len(result['gaps'])}):")
        for g in result['gaps']:
            print(f"  - {g['text'][:80]}...")


def cmd_ingest_research(args):
    """Ingest deep research output into a capsule."""
    source = Path(args.source)
    if not source.exists():
        print(f"Source not found: {source}")
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    path = ingest_research(source, output, args.name, args.version)
    print(f"Ingested: {path}")
    from stamper import validate_capsule
    print(f"Valid: {validate_capsule(path)['valid']}")


def cmd_ingest(args):
    """Ingest any document into a capsule with LLM extraction."""
    source = Path(args.source)
    if not source.exists():
        print(f"Source not found: {source}")
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    llm_fn = make_llm_fn(provider=args.provider, model=args.model) if args.provider != "stub" else None
    path = ingest_document(source, output, args.name, agent_type=args.agent_type,
                           version=args.version, llm_fn=llm_fn)
    print(f"Ingested: {path}")
    from stamper import validate_capsule
    print(f"Valid: {validate_capsule(path)['valid']}")


def cmd_ingest_skill(args):
    """Ingest a SKILL.md file with YAML frontmatter into a capsule."""
    source = Path(args.source)
    if not source.exists():
        print(f"Source not found: {source}")
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    llm_fn = make_llm_fn(provider=args.provider, model=args.model) if args.provider != "stub" else None
    path = ingest_skill(source, output, version=args.version, llm_fn=llm_fn)
    print(f"Ingested skill: {path}")
    from stamper import validate_capsule
    result = validate_capsule(path)
    print(f"Valid: {result['valid']}")
    if not result['valid']:
        print(f"Errors: {result.get('errors', [])}")


def cmd_refine(args):
    """Analyze education queue and surface KG improvement candidates."""
    # Validate capsule exists
    missing = validate_folder(args.capsule)
    if missing:
        print(f"Invalid capsule. Missing: {missing}")
        return

    # Check queue exists
    capsule_path = Path(args.capsule)
    queue_file = capsule_path / "education-queue.json"
    if not queue_file.exists():
        print("No education queue found for this capsule. Run some queries first.")
        return

    # Run refine session
    result = refine_session(args.capsule, n=args.n, auto_queue=args.auto_queue)

    # Get capsule name for display
    capsule = Capsule(capsule_path)

    # Print report
    print(f"\nAETHER Refine — {capsule.name}")
    print("─" * 45)
    print(f"Analyzed:    {result['analyzed']} records")
    print(f"Filtered:    {result['persona_gaps_filtered']} persona gaps (not KG-groundable)")
    print(f"Factual:     {result['factual_gaps_found']} factual gap statements found")
    print(f"Candidates:  {len(result['candidates'])} subjects identified")
    print("─" * 45)

    # KG Candidates
    if result["candidates"]:
        print("\nKG CANDIDATES (by priority):\n")
        for candidate in result["candidates"]:
            priority = candidate["priority"].upper()
            print(f"[{priority}] {candidate['subject']}  (appears in {candidate['frequency']} records)")
            print(f"  Gaps: {candidate['gap_texts'][0][:80]}...")
            if len(candidate["gap_texts"]) > 1:
                print(f"        {candidate['gap_texts'][1][:80]}...")
            print(f"  Records: {', '.join(r[:20] for r in candidate['records_affected'][:3])}")
            if len(candidate["records_affected"]) > 3:
                print(f"           ...and {len(candidate['records_affected']) - 3} more")
            print()
    else:
        print("\nNo KG candidates identified.\n")

    # Unresolved failures
    print("─" * 45)
    print(f"UNRESOLVED FAILURES: {len(result['unresolved_failures'])}")
    for failure in result["unresolved_failures"][:5]:
        truncated_id = failure["id"][:20] + "..." if len(failure["id"]) > 20 else failure["id"]
        print(f"  {truncated_id} | score: {failure['aec_score']:.3f} | {failure['reason']}")
    if len(result["unresolved_failures"]) > 5:
        print(f"  ...and {len(result['unresolved_failures']) - 5} more")

    print("\n" + "─" * 45)
    print(result["summary"])

    # Auto-queue status
    if result["auto_queued"] > 0:
        print(f"\nAuto-queued {result['auto_queued']} high-priority candidates for education.")
    elif result["candidates"] and not args.auto_queue:
        high_count = len([c for c in result["candidates"] if c["priority"] == "high"])
        if high_count > 0:
            print(f"\nRun with --auto-queue to queue {high_count} high-priority candidates for education.")


def cmd_export(args):
    """Export capsule to target platform format."""
    # Validate capsule first
    result = validate_capsule(args.capsule)
    if not result["valid"]:
        print(f"Invalid capsule: {args.capsule}")
        if result["missing"]:
            print(f"Missing: {result['missing']}")
        if result["errors"]:
            print(f"Errors: {result['errors']}")
        return

    try:
        output_file = export_capsule(args.capsule, args.format, args.output)
        # Get capsule name for message
        from aether import Capsule
        capsule = Capsule(args.capsule)
        print(f"Exported {capsule.name} → {output_file} (format: {args.format})")
    except ValueError as e:
        print(f"Error: {e}")
        print("Valid formats: claude-md, claude-skill, github-agent-md, a2a-agent-card")


def cmd_orchestrate(args):
    """Route query to best matching capsule and execute."""
    from habitat import orchestrate
    from llm import make_llm_fn

    # Build LLM function if not dry run
    llm_fn = None
    if not args.dry_run:
        llm_fn = make_llm_fn(provider=args.provider, model=args.model)

    result = orchestrate(
        query=args.query,
        registry_path=args.registry,
        llm_fn=llm_fn,
        dry_run=args.dry_run
    )

    # Output routing decision
    print(f"Routing: \"{args.query}\"")
    print()

    # Show candidates
    if result.get("candidates"):
        print("  Candidates:")
        for i, c in enumerate(result["candidates"][:5]):
            marker = " * SELECTED" if c["capsule_id"] == result.get("routed_to") else ""
            print(f"    {c['capsule_name']:<25} score={c['score']:.4f}{marker}")
        print()

    # Handle gap
    if result.get("gap"):
        gap = result["gap"]
        print(f"  GAP DETECTED")
        print(f"  Topic: {gap.get('topic', 'unknown')}")
        if gap.get("closest_capsule"):
            print(f"  Closest: {gap['closest_capsule']} (score={gap['closest_score']:.4f})")
        print(f"  {gap.get('recommendation', '')}")
        return

    # Handle dry run
    if args.dry_run:
        print(f"  Would dispatch to: {result['routed_name']} ({result['routed_to']})")
        print(f"  [dry-run mode - not executing]")
        return

    # Show execution
    print(f"  Dispatching to: {result['routed_name']} ({result['routed_to']})")
    print()

    pipeline_result = result.get("result", {})

    # Show response
    response = pipeline_result.get("generated", "")
    if response:
        print("─" * 60)
        print(response[:1000])
        if len(response) > 1000:
            print(f"... ({len(response)} chars total)")
        print("─" * 60)
        print()

    # Show AEC result
    review = pipeline_result.get("review", {})
    aec = review.get("aec", {})

    if aec:
        score = aec.get("score", 0)
        threshold = aec.get("threshold", 0.8)
        passed = aec.get("passed", False)

        print(f"  AEC Score: {score:.2f} (threshold: {threshold})")
        print(f"  AEC Passed: {passed}")

        if review.get("ghost"):
            print(f"  Status: GHOST (unverifiable)")
        elif review.get("self_corrected"):
            print(f"  Status: Self-corrected on retry")

    # Full report mode
    if args.report == "full" and aec:
        print()
        print("  AEC Details:")
        if aec.get("grounded"):
            print(f"    Grounded: {len(aec['grounded'])}")
        if aec.get("ungrounded"):
            print(f"    Ungrounded: {len(aec['ungrounded'])}")
        if aec.get("gaps"):
            print(f"    Gaps: {len(aec['gaps'])}")
            for gap in aec["gaps"][:3]:
                print(f"      - {gap.get('text', '')[:60]}...")


def main():
    parser = argparse.ArgumentParser(prog="aether", description="Aether Capsule Framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stamp
    p_stamp = subparsers.add_parser("stamp", help="Create a new capsule")
    p_stamp.add_argument("name", help="Capsule name")
    p_stamp.add_argument("--source", help="Source file (.md, .json, .jsonld)")
    p_stamp.add_argument("--output", default="./capsules", help="Output directory")
    p_stamp.add_argument("--version", default="1.0.0", help="Version string")
    p_stamp.add_argument("--psi", action="store_true",
        help="Create PSI projection files (psi.jsonld + pulse-map.json)")
    p_stamp.set_defaults(func=cmd_stamp)

    # run
    p_run = subparsers.add_parser("run", help="Run capsule with query")
    p_run.add_argument("capsule", help="Path to capsule folder")
    p_run.add_argument("query", help="Query to process")
    p_run.add_argument("--provider", default="stub", help="LLM provider")
    p_run.add_argument("--model", help="Model name")
    p_run.add_argument("--report", choices=["full"], help="Print execution report")
    p_run.add_argument("--psi", action="store_true",
        help="Print PSI/CVP events after normal output (DAI Pulse projection)")
    p_run.set_defaults(func=cmd_run)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate capsule")
    p_validate.add_argument("capsule", help="Path to capsule folder")
    p_validate.set_defaults(func=cmd_validate)

    # info
    p_info = subparsers.add_parser("info", help="Show capsule info")
    p_info.add_argument("capsule", help="Path to capsule folder")
    p_info.set_defaults(func=cmd_info)

    # queue
    p_queue = subparsers.add_parser("queue", help="Show education queue")
    p_queue.add_argument("capsule", help="Path to capsule folder")
    p_queue.set_defaults(func=cmd_queue)

    # educate
    p_educate = subparsers.add_parser("educate", help="Run self-education on pending failure")
    p_educate.add_argument("capsule", help="Path to capsule folder")
    p_educate.add_argument("--record-id", help="Specific failure record ID (default: oldest pending)")
    p_educate.add_argument("--provider", default="anthropic", help="LLM provider")
    p_educate.add_argument("--model", help="Model name")
    p_educate.set_defaults(func=cmd_educate)

    # verify
    p_verify = subparsers.add_parser("verify", help="Standalone AEC verification")
    p_verify.add_argument("text", help="Text to verify (or path to text file)")
    p_verify.add_argument("--reference", "-r", required=True, help="Reference KG file (.jsonld)")
    p_verify.add_argument("--threshold", "-t", type=float, default=0.8)
    p_verify.add_argument("--provider", default="stub", help="LLM provider for Layer 2 (default: stub)")
    p_verify.add_argument("--model", help="Model name for Layer 2")
    p_verify.set_defaults(func=cmd_verify)

    # ingest-research
    p_ingest_r = subparsers.add_parser("ingest-research", help="Ingest deep research output into capsule")
    p_ingest_r.add_argument("source", help="Path to deep research markdown file")
    p_ingest_r.add_argument("name", help="Agent name")
    p_ingest_r.add_argument("--output", default="./capsules", help="Output directory")
    p_ingest_r.add_argument("--version", default="1.0.0", help="Version string")
    p_ingest_r.set_defaults(func=cmd_ingest_research)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest any document into capsule (LLM-assisted)")
    p_ingest.add_argument("source", help="Path to markdown file")
    p_ingest.add_argument("name", help="Agent name")
    p_ingest.add_argument("--type", default="scholar", dest="agent_type", help="Agent type")
    p_ingest.add_argument("--output", default="./capsules", help="Output directory")
    p_ingest.add_argument("--version", default="1.0.0", help="Version string")
    p_ingest.add_argument("--provider", default="stub", help="LLM provider")
    p_ingest.add_argument("--model", help="Model name")
    p_ingest.set_defaults(func=cmd_ingest)

    # ingest-skill
    p_ingest_skill = subparsers.add_parser("ingest-skill", help="Ingest SKILL.md file into capsule")
    p_ingest_skill.add_argument("source", help="Path to SKILL.md file with YAML frontmatter")
    p_ingest_skill.add_argument("--output", default="./examples", help="Output directory")
    p_ingest_skill.add_argument("--version", default="1.0.0", help="Version string")
    p_ingest_skill.add_argument("--provider", default="stub", help="LLM provider (stub for no-LLM)")
    p_ingest_skill.add_argument("--model", help="Model name")
    p_ingest_skill.set_defaults(func=cmd_ingest_skill)

    # export
    p_export = subparsers.add_parser("export", help="Export capsule to target platform format")
    p_export.add_argument("capsule", help="Path to capsule folder")
    p_export.add_argument("--format", required=True,
        choices=["claude-md", "claude-skill", "github-agent-md", "a2a-agent-card"],
        help="Export format")
    p_export.add_argument("--output", default=None,
        help="Output path (default: capsule parent directory)")
    p_export.set_defaults(func=cmd_export)

    # refine
    p_refine = subparsers.add_parser("refine", help="Analyze queue and surface KG improvement candidates")
    p_refine.add_argument("capsule", help="Path to capsule folder")
    p_refine.add_argument("--n", type=int, default=50,
        help="Number of recent records to analyze (default: 50)")
    p_refine.add_argument("--auto-queue", action="store_true",
        help="Auto-queue high-priority candidates into education loop")
    p_refine.set_defaults(func=cmd_refine)

    # orchestrate
    p_orch = subparsers.add_parser("orchestrate", help="Route query to best capsule and execute")
    p_orch.add_argument("query", help="Query to route")
    p_orch.add_argument("--registry", default="./examples", help="Capsule registry directory")
    p_orch.add_argument("--provider", default="stub", help="LLM provider")
    p_orch.add_argument("--model", default=None, help="Model override")
    p_orch.add_argument("--report", choices=["full"], help="Show full AEC report")
    p_orch.add_argument("--dry-run", action="store_true", help="Show routing without executing")
    p_orch.set_defaults(func=cmd_orchestrate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
